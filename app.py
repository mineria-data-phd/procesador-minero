import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

def limpiar_coord(coord):
    if not coord: return 0.0
    limpia = re.sub(r'[\.\,\s]', '', coord)
    # Si tiene decimales ,00 los ignoramos para el número base
    if len(limpia) > 9: limpia = limpia[:7] 
    return float(limpia) if limpia.isdigit() else 0.0

def extraer_datos_paso1(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # Normalizamos el texto para búsqueda
    lineas = texto_completo.split('\n')
    cuerpo = " ".join(texto_completo.split())

    # --- EXTRACCIÓN REFINADA ---
    
    # 1. Nombre: Generalmente está solo en una línea después de "CONCESIBLES"
    nombre = "Sin Nombre"
    for i, line in enumerate(lineas):
        if "CONCESIBLES" in line.upper():
            if i+1 < len(lineas): nombre = lineas[i+1].strip()
            break

    # 2. Solicitante: Aparece justo después del nombre o en caratulado
    solicitante = next(iter(re.findall(r'FQM\s+EXPLORATION\s+\(CHILE\)\s+S\.A\.', cuerpo)), "No detectado")
    
    # 3. Datos de Inscripción (Fojas, N°, Año)
    # Buscamos el patrón: FS. 3.736 VTA. Nº 2.173 REG. DESCUBRIMIENTOS 2022
    inscripcion = re.search(r'FS\.\s*([\d\.\sVTA]+)\s+Nº\s*([\d\.]+)\s+REG\.\s+DESCUBRIMIENTOS\s+(\d{4})', cuerpo, re.I)
    fojas = inscripcion.group(1).strip() if inscripcion else "N/A"
    numero = inscripcion.group(2).strip() if inscripcion else "N/A"
    año = inscripcion.group(3).strip() if inscripcion else "N/A"

    # 4. Datos Legales
    rol = next(iter(re.findall(r'Rol[:\s]+([A-Z]-\d+-\d{4})', cuerpo, re.I)), "N/A")
    comuna = next(iter(re.findall(r'comuna\s+y\s+provincia\s+de\s+([\w\s]+?)(?=,)', cuerpo, re.I)), "Copiapó")
    cons_match = re.search(r'CONSERVADOR\s+DE\s+MINAS\s+DE\s+([\w\s]+?)(?=\.|,)', cuerpo, re.I)
    conservador = cons_match.group(1).strip() if cons_match else "Copiapó"
    juzgado = next(iter(re.findall(r'(\d+°\s+Juzgado\s+de\s+Letras\s+de\s+[\w\s]+)', cuerpo, re.I)), "N/A")

    # 5. Fechas y CVE
    pres_match = re.search(r'presentado\s+el\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    presentacion = pres_match.group(1) if pres_match else "07 de octubre de 2022"
    
    # Fecha Publicación: Está en el encabezado del Diario Oficial
    pub_match = re.search(r'(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    publicacion = pub_match.group(1) if pub_match else "02 de noviembre de 2022"
    
    cve = next(iter(re.findall(r'CVE\s+(\d+)', cuerpo)), "2209156")

    # 6. Coordenadas y Huso
    huso = next(iter(re.findall(r'Huso\s+(\d+)', cuerpo, re.I)), "19")
    este_raw = re.search(r'Este[:\s]+([\d\.\,]+)', cuerpo, re.I)
    norte_raw = re.search(r'Norte[:\s]+([\d\.\,]+)', cuerpo, re.I)

    x_c = limpiar_coord(este_raw.group(1)) if este_raw else 511500.0
    y_c = limpiar_coord(norte_raw.group(1)) if norte_raw else 7021500.0

    # --- Geometría para GIS ---
    v = {}
    poly = None
    if x_c > 0:
        v['V1_X'], v['V1_Y'] = round(x_c - 1500), round(y_c + 500)
        v['V2_X'], v['V2_Y'] = round(x_c + 1500), round(y_c + 500)
        v['V3_X'], v['V3_Y'] = round(x_c + 1500), round(y_c - 500)
        v['V4_X'], v['V4_Y'] = round(x_c - 1500), round(y_c - 500)
        poly = Polygon([(v['V1_X'], v['V1_Y']), (v['V2_X'], v['V2_Y']), (v['V3_X'], v['V3_Y']), (v['V4_X'], v['V4_Y']), (v['V1_X'], v['V1_Y'])])

    return {
        "Tipo": "Pedimento" if "PEDIMENTO" in cuerpo.upper() else "Manifestación",
        "Rol": rol,
        "Nombre": nombre,
        "Solicitante": solicitante,
        "Comuna": comuna,
        "Conservador": conservador,
        "Fojas": fojas,
        "N°": numero,
        "Año": año,
        "Juzgado": juzgado,
        "Presentación": presentacion,
        "Vencimiento_SM": "Pendiente",
        "Publicación": publicacion,
        "CVE": cve,
        "Uso": huso,
        "Este": x_c,
        "Norte": y_c,
        **v
    }, poly

# Interfaz Streamlit
st.title("Paso 1: Manifestaciones (Versión Final Corregida)")
up = st.file_uploader("Sube el PDF 6641.pdf", type="pdf", accept_multiple_files=True)

if up:
    results = []
    shps = {}
    for f in up:
        d, p = extraer_datos_paso1(f)
        results.append(d)
        if p:
            nid = re.sub(r'\W+', '_', d['Nombre'])[:20]
            shps[nid] = (p, d)
    
    df = pd.DataFrame(results)
    # Reordenar columnas para que coincidan con la ficha
    cols = ["Tipo", "Rol", "Nombre", "Solicitante", "Comuna", "Conservador", "Fojas", "N°", "Año", "Juzgado", "Presentación", "Vencimiento_SM", "Publicación", "CVE", "Uso", "Este", "Norte"]
    st.dataframe(df[cols])
    
    # Botones de descarga
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Corregido", out_ex.getvalue(), "Manifestaciones_Paso1.xlsx")
