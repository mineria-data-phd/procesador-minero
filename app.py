import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Extractor Minero ArcMap Pro", layout="wide")
st.title("⚒️ Generador de Polígonos SHP (4 Vértices)")

def identificar_tramite(texto):
    t = texto.lower()
    if "rectificación" in t or "rectificacion" in t: return "Solicitud de Rectificación"
    if "mensura" in t: return "Solicitud de Mensura"
    if "pedimento" in t or "manifestación" in t or "manifestacion" in t: return "Manifestación y Pedimento"
    return "Extracto EM y EP"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- Extracción de Coordenadas del Punto Medio ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None

    # --- Cálculo de los 4 Vértices ---
    # Rectángulo de 3.000m (X) x 1.000m (Y) = 3.000.000 m2 = 300 Ha
    v1_x, v1_y = (x_c - 1500, y_c + 500) if x_c else (None, None) # NW
    v2_x, v2_y = (x_c + 1500, y_c + 500) if x_c else (None, None) # NE
    v3_x, v3_y = (x_c + 1500, y_c - 500) if x_c else (None, None) # SE
    v4_x, v4_y = (x_c - 1500, y_c - 500) if x_c else (None, None) # SW

    # --- Otros Datos ---
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "No detectado"
    solic_match = re.search(r'(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo, re.IGNORECASE)
    solicitante = solic_match.group(1).strip() if solic_match else "No detectado"
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)

    return {
        "Archivo": pdf_file.name,
        "Nombre": nombre,
        "Solicitante": solicitante,
        "Rol": rol.group(1) if rol else "No detectado",
        "V1_X": v1_x, "V1_Y": v1_y,
        "V2_X": v2_x, "V2_Y": v2_y,
        "V3_X": v3_x, "V3_Y": v3_y,
        "V4_X": v4_x, "V4_Y": v4_y,
        "Hectareas": 300,
        "Tipo": identificar_tramite(cuerpo)
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    st.dataframe(df)

    # 1. Excel con los 4 Vértices
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel de Vértices", out_ex.getvalue(), "Coordenadas_Vértices.xlsx")

    # 2. Shapefile de Polígonos (Calculado con los 4 vértices)
    df_geo = df.dropna(subset=['V1_X', 'V1_Y']).copy()
    if not df_geo.empty:
        geometrias = []
        for _, r in df_geo.iterrows():
            # Creamos el polígono cerrando los 4 puntos calculados
            poly = Polygon([(r.V1_X, r.V1_Y), (r.V2_X, r.V2_Y), (r.V3_X, r.V3_Y), (r.V4_X, r.V4_Y)])
            geometrias.append(poly)
        
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometrias, crs="EPSG:32719")
        
        # Guardar archivos del SHP
        temp = "temp_shp"
        if not os.path.exists(temp): os.makedirs(temp)
        # Nombres cortos para evitar errores en ArcMap (máx 10 caracteres en DBF)
        gdf.to_file(os.path.join(temp, "Concesion.shp"))

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            for ex in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(os.path.join(temp, f"Concesion{ex}"), arcname=f"Concesion{ex}")
        st.download_button("🌍 Descargar Shapefile Polígono", zip_buf.getvalue(), "Concesiones_300Ha.zip")
