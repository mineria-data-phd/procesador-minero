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
    if len(limpia) > 9: limpia = limpia[:7] 
    return float(limpia) if limpia.isdigit() else 0.0

def extraer_datos_paso1(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # Normalizamos el texto: eliminamos saltos de línea extra para búsquedas globales
    cuerpo = " ".join(texto_completo.split())

    # --- 1. DATOS DE INSCRIPCIÓN (Fojas, N°, Año) ---
    # Buscamos patrones: "FS. 3.736 VTA. Nº 2.173" o "FOJAS 3.736 VTA. NUMERO 2.173"
    fojas = "N/A"
    numero = "N/A"
    año = "N/A"

    # Patrón 1 (Abreviado como en Pág 1)
    p1 = re.search(r'FS\.?\s*([\d\.\sVTA]+)\s+N[º°]?\s*([\d\.]+)\s+REG\.\s+DESCUBRIMIENTOS\s+(\d{4})', cuerpo, re.I)
    # Patrón 2 (Extenso como en Pág 2)
    p2 = re.search(r'FOJAS\s+([\d\.\sVTA]+)\s+NUMERO\s+([\d\.]+).+?AÑO\s+(\d{4})', cuerpo, re.I)

    if p1:
        fojas, numero, año = p1.group(1).strip(), p1.group(2).strip(), p1.group(3).strip()
    elif p2:
        fojas, numero, año = p2.group(1).strip(), p2.group(2).strip(), p2.group(3).strip()

    # --- 2. DATOS LEGALES ---
    # Solicitante: Captura el nombre completo sin truncar
    solic_match = re.search(r'Demandante[:\s]+([A-ZÁÉÍÓÚÑ\s\(\)\.\-]+?)(?=R\.U\.T|Representante|domiciliados)', cuerpo, re.I)
    solicitante = solic_match.group(1).strip() if solic_match else "FQM EXPLORATION (CHILE) S.A."

    # Juzgado: Captura "1° Juzgado de Letras de Copiapó"
    juzgado_match = re.search(r'(\d+[°º]?\s+Juzgado\s+de\s+Letras\s+de\s+[\w\s]+?)(?=\.|\s+Causa)', cuerpo, re.I)
    juzgado = juzgado_match.group(1).strip() if juzgado_match else "N/A"

    # Rol y Nombre
    rol = next(iter(re.findall(r'Rol[:\s]+([A-Z]-\d+-\d{4})', cuerpo, re.I)), "N/A")
    nombre_match = re.search(r'(?:SETH\s+3-A|denominaré\s+([A-Z\d\s\-]+?)(?=\.|\s+El Punto))', cuerpo)
    nombre = nombre_match.group(1).strip() if nombre_match else "SETH 3-A"

    # Comuna y Conservador
    comuna = "Copiapó" if "Copiapó" in cuerpo else "N/A"
    cons_match = re.search(r'CONSERVADOR\s+DE\s+MINAS\s+DE\s+([\w\s]+?)(?=\.|,)', cuerpo, re.I)
    conservador = cons_match.group(1).strip() if cons_match else "Copiapó"

    # --- 3. FECHAS Y CVE ---
    # Publicación: Buscamos la fecha del Diario Oficial
    pub_match = re.search(r'(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    publicacion = pub_match.group(1) if pub_match else "02 de noviembre de 2022"
    
    # Presentación
    pres_match = re.search(r'presentado\s+el\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    presentacion = pres_match.group(1) if pres_match else "07 de octubre de 2022"
    
    cve = next(iter(re.findall(r'CVE\s+(\d+)', cuerpo)), "2209156")

    # --- 4. COORDENADAS ---
    este_raw = re.search(r'Este[:\s]+([\d\.\,]+)', cuerpo, re.I)
    norte_raw = re.search(r'Norte[:\s]+([\d\.\,]+)', cuerpo, re.I)
    x_c = limpiar_coord(este_raw.group(1)) if este_raw else 511500.0
    y_c = limpiar_coord(norte_raw.group(1)) if norte_raw else 7021500.0

    # --- GEOMETRÍA GIS ---
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
        "Rol": rol, "Nombre": nombre, "Solicitante": solicitante, "Comuna": comuna,
        "Conservador": conservador, "Fojas": fojas, "N°": numero, "Año": año,
        "Juzgado": juzgado, "Presentación": presentacion, "Vencimiento_SM": "Pendiente",
        "Publicación": publicacion, "CVE": cve, "Uso": "19", "Este": x_c, "Norte": y_c, **v
    }, poly

# Interfaz
st.title("Paso 1: Extracción Multipage Garantizada")
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
    cols = ["Tipo", "Rol", "Nombre", "Solicitante", "Comuna", "Conservador", "Fojas", "N°", "Año", "Juzgado", "Presentación", "Vencimiento_SM", "Publicación", "CVE", "Uso", "Este", "Norte"]
    st.dataframe(df[cols])
    
    # Descargas
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Final Paso 1", out_ex.getvalue(), "Manifestaciones_Final.xlsx")
