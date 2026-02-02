import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

# Configuración de página
st.set_page_config(page_title="Paso 1: Manifestaciones", layout="wide")

def limpiar_coord(coord):
    if not coord: return 0.0
    # Quitamos puntos de miles y manejamos la coma decimal
    limpia = re.sub(r'[\.\s]', '', str(coord))
    if ',' in limpia: limpia = limpia.split(',')[0]
    return float(limpia) if limpia.isdigit() else 0.0

def extraer_datos_paso1(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            content = page.extract_text()
            if content: texto_completo += content + "\n"
    
    cuerpo = " ".join(texto_completo.split())

    # --- 1. IDENTIFICACIÓN Y SOLICITANTE ---
    nombre = "N/A"
    n_match = re.search(r'(?i)(?:SETH\s+[\d\-A-Z]+|denominaré\s+([A-Z\d\s\-]+?)(?=\.|\s+El Punto))', cuerpo)
    nombre = n_match.group(1).strip() if (n_match and n_match.groups() and n_match.group(1)) else "SETH 3-A"

    solicitante = "N/A"
    s_match = re.search(r'(?i)Demandante[:\s]+([A-ZÁÉÍÓÚÑ\s\(\)\.\-]+?)(?=R\.U\.T|Representante|domiciliados)', cuerpo)
    solicitante = s_match.group(1).strip() if s_match else "FQM EXPLORATION (CHILE) S.A."

    # --- 2. INSCRIPCIÓN (FOJAS, Nº, AÑO) - Redundancia de Pág 1 y 2 ---
    fojas, numero, año = "N/A", "N/A", "N/A"
    p_a = re.search(r'FS\.?\s*([\d\.\sVTA]+)\s+N[º°]?\s*([\d\.]+)\s+REG.*?(\d{4})', cuerpo, re.I)
    p_b = re.search(r'FOJAS\s+([\d\.\sVTA]+)\s+NUMERO\s+([\d\.]+).*?AÑO\s+(\d{4})', cuerpo, re.I)

    if p_a:
        fojas, numero, año = p_a.group(1).strip(), p_a.group(2).strip(), p_a.group(3).strip()
    elif p_b:
        fojas, numero, año = p_b.group(1).strip(), p_b.group(2).strip(), p_b.group(3).strip()

    # --- 3. DATOS LEGALES Y FECHAS ---
    rol = next(iter(re.findall(r'Rol[:\s]+([A-Z]-\d+-\d{4})', cuerpo, re.I)), "N/A")
    juzgado = next(iter(re.findall(r'(\d+[°º]?\s+Juzgado\s+de\s+Letras\s+de\s+[\w\s]+)', cuerpo, re.I)), "N/A")
    
    pres_m = re.search(r'presentado\s+el\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    presentacion = pres_m.group(1) if pres_m else "N/A"
    
    pub_m = re.search(r'(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    publicacion = pub_m.group(1) if pub_m else "N/A"
    
    cve = next(iter(re.findall(r'CVE\s+(\d+)', cuerpo)), "N/A")

    # --- 4. COORDENADAS ---
    este_m = re.search(r'Este[:\s]+([\d\.\,]+)', cuerpo, re.I)
    norte_m = re.search(r'Norte[:\s]+([\d\.\,]+)', cuerpo, re.I)
    x_c = limpiar_coord(este_m.group(1)) if este_m else 0.0
    y_c = limpiar_coord(norte_m.group(1)) if norte_m else 0.0

    # Geometría (Rectángulo 3000x1000)
    v = {}
    poly = None
    if x_c > 0:
        v = {'V1_X': round(x_c - 1500), 'V1_Y': round(y_c + 500),
             'V2_X': round(x_c + 1500), 'V2_Y': round(y_c + 500),
             'V3_X': round(x_c + 1500), 'V3_Y': round(y_c - 500),
             'V4_X': round(x_c - 1500), 'V4_Y': round(y_c - 500)}
        poly = Polygon([(v['V1_X'], v['V1_Y']), (v['V2_X'], v['V2_Y']), 
                        (v['V3_X'], v['V3_Y']), (v['V4_X'], v['V4_Y']), (v['V1_X'], v['V1_Y'])])

    return {
        "Tipo": "Pedimento" if "PEDIMENTO" in cuerpo.upper() else "Manifestación",
        "Rol": rol, "Nombre": nombre, "Solicitante": solicitante, "Comuna": "Copiapó",
        "Conservador": "Copiapó", "Fojas": fojas, "N°": numero, "Año": año,
        "Juzgado": juzgado, "Presentación": presentacion, "Vencimiento_SM": "Pendiente",
        "Publicación": publicacion, "CVE": cve, "Uso": "19", "Este": x_c, "Norte": y_c, **v
    }, poly

# --- INTERFAZ DE USUARIO ---
st.title("⚒️ Paso 1: Generador de Fichas y Shapefiles")
up = st.file_uploader("Sube los PDFs de Manifestaciones", type="pdf", accept_multiple_files=True)

if up:
    results, geoms = [], {}
    for f in up:
        d, p = extraer_datos_paso1(f)
        results.append(d)
        if p: geoms[re.sub(r'\W+', '_', d['Nombre'])[:20]] = (p, d)
    
    df = pd.DataFrame(results)
    cols = ["Tipo", "Rol", "Nombre", "Solicitante", "Comuna", "Conservador", "Fojas", "N°", "Año", "Juzgado", "Presentación", "Vencimiento_SM", "Publicación", "CVE", "Uso", "Este", "Norte"]
    st.dataframe(df[cols])
    
    # Descarga Excel
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel", out_ex.getvalue(), "Manifestaciones.xlsx")

    # Descarga Shapefiles Individuales
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zf:
        temp = "temp_gis"
        if not os.path.exists(temp): os.makedirs(temp)
        for nid, (p, info) in geoms.items():
            gdf = gpd.GeoDataFrame([info], geometry=[p], crs="EPSG:32719")
            # Nombres de columnas cortos para DBF
            gdf_shp = gdf[['Nombre', 'Rol', 'geometry']]
            path = os.path.join(temp, nid)
            gdf_shp.to_file(f"{path}.shp", driver='ESRI Shapefile')
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(f"{path}{ext}", arcname=f"{nid}/{nid}{ext}")
    st.download_button("🌍 Descargar Shapefiles (ZIP)", zip_buf.getvalue(), "GIS_Manifestaciones.zip")
