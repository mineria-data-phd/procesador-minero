import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Point
from io import BytesIO

st.set_page_config(page_title="Extractor de Vértices Pro", layout="wide")
st.title("⚒️ Generador de Vértices para Reconstrucción en ArcMap")

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "
    cuerpo = " ".join(texto_sucio.split()).strip()

    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None

    # Extraer metadatos
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "No detectado"
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)

    vertices_list = []
    if x_c and y_c:
        # Creamos los 5 puntos (incluyendo el de cierre) para que ArcMap los una fácil
        coords = [
            (x_c - 1500, y_c + 500, 1), # V1
            (x_c + 1500, y_c + 500, 2), # V2
            (x_c + 1500, y_c - 500, 3), # V3
            (x_c - 1500, y_c - 500, 4), # V4
            (x_c - 1500, y_c + 500, 5)  # Cierre (V1 otra vez)
        ]
        
        for vx, vy, orden in coords:
            vertices_list.append({
                "Nombre": nombre,
                "Rol": rol.group(1) if rol else "S/R",
                "Orden": orden,
                "X": round(vx),
                "Y": round(vy)
            })
    
    return vertices_list

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_vertices = []
    for f in uploaded_files:
        all_vertices.extend(extraer_datos_mineros(f))
    
    df = pd.DataFrame(all_vertices)
    st.write("Vista de los puntos (V1 a V5):")
    st.dataframe(df)

    # SHAPEFILE DE PUNTOS
    if not df.empty:
        geometry = [Point(xy) for xy in zip(df.X, df.Y)]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:32719")
        
        temp = "temp_shp"
        if not os.path.exists(temp): os.makedirs(temp)
        
        base_name = "Vertices_Control"
        gdf.to_file(os.path.join(temp, f"{base_name}.shp"), driver='ESRI Shapefile')

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            for ex in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(os.path.join(temp, f"{base_name}{ex}"), arcname=f"{base_name}{ex}")
        
        st.download_button("🌍 Descargar Puntos para ArcMap", zip_buf.getvalue(), "Vertices_ArcMap.zip")
