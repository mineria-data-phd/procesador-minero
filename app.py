import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Point
from io import BytesIO

st.set_page_config(page_title="Generador de Vértices Mineros", layout="wide")
st.title("⚒️ Extractor de Vértices para ArcMap 10.8")

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

    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "Sin_Nombre"
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    rol_txt = rol.group(1) if rol else "S/R"

    puntos_concesion = []
    if x_c and y_c:
        # Generamos los 5 vértices para cerrar el rectángulo (3000m x 1000m)
        # 1: NW, 2: NE, 3: SE, 4: SW, 5: NW (Cierre)
        coords = [
            (x_c - 1500, y_c + 500, 1),
            (x_c + 1500, y_c + 500, 2),
            (x_c + 1500, y_c - 500, 3),
            (x_c - 1500, y_c - 500, 4),
            (x_c - 1500, y_c + 500, 5) 
        ]
        
        for vx, vy, orden in coords:
            puntos_concesion.append({
                "Nombre": nombre[:15], # Acortamos para DBF
                "Rol": rol_txt,
                "Orden": orden,
                "X": round(vx),
                "Y": round(vy)
            })
    return puntos_concesion

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    lista_total = []
    for f in uploaded_files:
        lista_total.extend(extraer_datos_mineros(f))
    
    if lista_total:
        df = pd.DataFrame(lista_total)
        st.write("### Vértices Generados (V1 a V5)")
        st.dataframe(df)

        # Crear Shapefile de Puntos
        geometry = [Point(xy) for xy in zip(df.X, df.Y)]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:32719")
        
        temp = "temp_shp"
        if not os.path.exists(temp): os.makedirs(temp)
        
        base_name = "Vertices_Concesion"
        gdf.to_file(os.path.join(temp, f"{base_name}.shp"), driver='ESRI Shapefile')

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            for ex in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(os.path.join(temp, f"{base_name}{ex}"), arcname=f"{base_name}{ex}")
        
        st.download_button("🌍 Descargar Vértices para ArcMap", zip_buf.getvalue(), "Vertices_Final.zip")
