import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes y Generador GIS")

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

    # --- Coordenadas Punto Medio ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None

    # --- Vértices para el Excel ---
    v = {}
    if x_c and y_c:
        v['V1_X'], v['V1_Y'] = x_c - 1500, y_c + 500
        v['V2_X'], v['V2_Y'] = x_c + 1500, y_c + 500
        v['V3_X'], v['V3_Y'] = x_c + 1500, y_c - 500
        v['V4_X'], v['V4_Y'] = x_c - 1500, y_c - 500
    else:
        for i in range(1, 5): v[f'V{i}_X'] = v[f'V{i}_Y'] = None

    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    solic_match = re.search(r'(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo, re.IGNORECASE)
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)

    return {
        "Archivo": pdf_file.name,
        "Nombre": nombre_m.group(1).strip() if nombre_m else "No detectado",
        "Solicitante": solic_match.group(1).strip() if solic_match else "No detectado",
        "Rol": rol.group(1) if rol else "No detectado",
        "Tipo": identificar_tramite(cuerpo),
        "Hectareas": 300,
        **v
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    st.dataframe(df)

    # 1. EXCEL (Completo)
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel", out_ex.getvalue(), "Reporte.xlsx")

    # 2. SHAPEFILE (Validado para ArcMap)
    df_geo = df.dropna(subset=['V1_X', 'V1_Y']).copy()
    if not df_geo.empty:
        geometrias = []
        for _, r in df_geo.iterrows():
            # IMPORTANTE: Cerramos el polígono repitiendo el primer vértice al final
            poly = Polygon([
                (r.V1_X, r.V1_Y), 
                (r.V2_X, r.V2_Y), 
                (r.V3_X, r.V3_Y), 
                (r.V4_X, r.V4_Y), 
                (r.V1_X, r.V1_Y)
            ])
            geometrias.append(poly)
        
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometrias, crs="EPSG:32719")
        
        # Quitamos vértices de la tabla y acortamos nombres para ArcMap
        gdf = gdf.drop(columns=['V1_X', 'V1_Y', 'V2_X', 'V2_Y', 'V3_X', 'V3_Y', 'V4_X', 'V4_Y'])
        gdf.columns = ['Archivo', 'Nombre', 'Solicit', 'Rol', 'Tipo', 'Has', 'geometry']
        
        temp = "temp_shp"
        if not os.path.exists(temp): os.makedirs(temp)
        gdf.to_file(os.path.join(temp, "Mineria.shp"))

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            for ex in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(os.path.join(temp, f"Mineria{ex}"), arcname=f"Mineria{ex}")
        st.download_button("🌍 Descargar SHP Polígonos", zip_buf.getvalue(), "Mineria_SHP.zip")
