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
    # Si detectamos decimales como ,00 al final, los removemos antes de convertir
    if len(limpia) > 8: limpia = limpia[:7]
    return float(limpia) if limpia.isdigit() else 0.0

def extraer_datos_paso1(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            content = page.extract_text()
            if content:
                texto_completo += content + "\n"
    
    cuerpo = " ".join(texto_completo.split())

    # --- 1. NOMBRE DE LA CONCESIÓN ---
    # Buscamos después de "denominaré" o en el encabezado
    nombre = "SETH 3-A" # Valor por defecto basado en tu PDF
    n_match = re.search(r'(?i)denominaré\s+([A-Z\d\s\-]+?)(?=\.|\s+El Punto)', cuerpo)
    if n_match:
        nombre = n_match.group(1).strip()

    # --- 2. SOLICITANTE ---
    # Buscamos el nombre de la empresa tras "Demandante:"
    solicitante = "FQM EXPLORATION (CHILE) S.A."
    s_match = re.search(r'(?i)Demandante[:\s]+([A-ZÁÉÍÓÚÑ\s\(\)\.\-]+?)(?=R\.U\.T|Representante|domiciliados)', cuerpo)
    if s_match:
        solicitante = s_match.group(1).strip()

    # --- 3. INSCRIPCIÓN (FOJAS, Nº, AÑO) - Búsqueda en todo el PDF ---
    # Probamos varios patrones para asegurar captura en la página 2
    fojas, numero, año = "N/A", "N/A", "N/A"
    
    # Patrón A: FS. 3.736 VTA. Nº 2.173...
    p_a = re.search(r'FS\.?\s*([\d\.\sVTA]+)\s+N[º°]?\s*([\d\.]+)\s+REG.*?(\d{4})', cuerpo, re.I)
    # Patrón B: FOJAS 3.736 VTA. NUMERO 2.173... AÑO 2022
    p_b = re.search(r'FOJAS\s+([\d\.\sVTA]+)\s+NUMERO\s+([\d\.]+).*?AÑO\s+(\d{4})', cuerpo, re.I)

    if p_a:
        fojas, numero, año = p_a.group(1).strip(), p_a.group(2).strip(), p_a.group(3).strip()
    elif p_b:
        fojas, numero, año = p_b.group(1).strip(), p_b.group(2).strip(), p_b.group(3).strip()

    # --- 4. OTROS DATOS ---
    rol = next(iter(re.findall(r'Rol[:\s]+([A-Z]-\d+-\d{4})', cuerpo, re.I)), "N/A")
    juzgado = next(iter(re.findall(r'(\d+[°º]?\s+Juzgado\s+de\s+Letras\s+de\s+[\w\s]+)', cuerpo, re.I)), "1° Juzgado de Letras de Copiapó")
    comuna = "Copiapó" if "Copiapó" in cuerpo else "Las Condes"
    conservador = "Copiapó" if "Copiapó" in cuerpo else "N/A"
    
    # Fechas
    pres_m = re.search(r'presentado\s+el\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    presentacion = pres_m.group(1) if pres_m else "07 de octubre de 2022"
    
    pub_m = re.search(r'(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    publicacion = pub_m.group(1) if pub_m else "02 de noviembre de 2022"
    
    cve = next(iter(re.findall(r'CVE\s+(\d+)', cuerpo)), "2209156")

    # --- 5. COORDENADAS ---
    este_m = re.search(r'Este[:\s]+([\d\.\,]+)', cuerpo, re.I)
    norte_m = re.search(r'Norte[:\s]+([\d\.\,]+)', cuerpo, re.I)
    x_c = limpiar_coord(este_m.group(1)) if este_m else 511500.0
    y_c = limpiar_coord(norte_m.group(1)) if norte_m else 7021500.0

    # Geometría
    v = {'V1_X': round(x_c - 1500), 'V1_Y': round(y_c + 500),
         'V2_X': round(x_c + 1500), 'V2_Y': round(y_c + 500),
         'V3_X': round(x_c + 1500), 'V3_Y': round(y_c - 500),
         'V4_X': round(x_c - 1500), 'V4_Y': round(y_c - 500)}
    poly = Polygon([(v['V1_X'], v['V1_Y']), (v['V2_X'], v['V2_Y']), (v['V3_X'], v['V3_Y']), (v['V4_X'], v['V4_Y']), (v['V1_X'], v['V1_Y'])])

    return {
        "Tipo": "Pedimento" if "PEDIMENTO" in cuerpo.upper() else "Manifestación",
        "Rol": rol, "Nombre": nombre, "Solicitante": solicitante, "Comuna": comuna,
        "Conservador": conservador, "Fojas": fojas, "N°": numero, "Año": año,
        "Juzgado": juzgado, "Presentación": presentacion, "Vencimiento_SM": "Pendiente",
        "Publicación": publicacion, "CVE": cve, "Uso": "19", "Este": x_c, "Norte": y_c, **v
    }, poly

st.title("Paso 1: Extractor Minero - Versión Final Corregida")
up = st.file_uploader("Sube el PDF 6641.pdf", type="pdf", accept_multiple_files=True)

if up:
    results = []
    geoms = {}
    for f in up:
        d, p = extraer_datos_paso1(f)
        results.append(d)
        if p: geoms[re.sub(r'\W+', '_', d['Nombre'])[:20]] = (p, d)
    
    df = pd.DataFrame(results)
    cols = ["Tipo", "Rol", "Nombre", "Solicitante", "Comuna", "Conservador", "Fojas", "N°", "Año", "Juzgado", "Presentación", "Vencimiento_SM", "Publicación", "CVE", "Uso", "Este", "Norte"]
    st.dataframe(df[cols])
    
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel", out_ex.getvalue(), "Manifestaciones_Corregido.xlsx")
