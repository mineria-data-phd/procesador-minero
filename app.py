import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Individual", layout="wide")
st.title("⚒️ Generador de Shapefiles Individuales (1 por Expediente)")

def identificar_tramite(texto):
    t = texto.lower()
    if any(x in t for x in ["rectificación", "rectificacion"]): return "Rectificacion"
    if "mensura" in t: return "Mensura"
    if any(x in t for x in ["pedimento", "manifestación", "manifestacion"]): return "Pedimento"
    return "Extracto"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- Coordenadas ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None

    # --- Nombre y Rol ---
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre_raw = nombre_m.group(1).strip() if nombre_m else "Sin_Nombre"
    # Limpiar nombre para que sea un nombre de archivo válido
    nombre_limpio = re.sub(r'[^a-zA-Z0-9]', '_', nombre_raw)[:20]
    
    rol_match = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    rol = rol_match.group(1) if rol_match else "S_R"

    # --- Geometría ---
    poligono = None
    if x_c and y_c:
        # V1->V2->V3->V4->V1 (Sentido horario y cierre)
        coords = [
            (x_c - 1500, y_c + 500),
            (x_c + 1500, y_c + 500),
            (x_c + 1500, y_c - 500),
            (x_c - 1500, y_c - 500),
            (x_c - 1500, y_c + 500)
        ]
        poligono = Polygon(coords)

    return {
        "Nombre_Arch": nombre_limpio,
        "Nombre_Real": nombre_raw,
        "Rol": rol,
        "Tipo": identificar_tramite(cuerpo),
        "Geometria": poligono
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = [extraer_datos_mineros(f) for f in uploaded_files]
    df_base = pd.DataFrame(resultados)
    st.write("Expedientes procesados:")
    st.dataframe(df_base.drop(columns=["Geometria"]))

    # Crear el ZIP con archivos individuales
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        temp_dir = "temp_individual"
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)

        for index, row in df_base.iterrows():
            if row['Geometria']:
                # Crear GeoDataFrame para este expediente único
                gdf_individual = gpd.GeoDataFrame(
                    [row], 
                    geometry=[row['Geometria']], 
                    crs="EPSG:32719"
                )
                # Limpiar columnas para el DBF
                gdf_shp = gdf_individual.drop(columns=["Geometria", "Nombre_Arch"])
                gdf_shp.columns = ['Nombre', 'Rol', 'Tipo', 'geometry']

                # Guardar temporalmente
                base_name = f"{row['Nombre_Arch']}_{index}"
                path_base = os.path.join(temp_dir, base_name)
                gdf_shp.to_file(f"{path_base}.shp", driver='ESRI Shapefile')

                # Agregar al ZIP todas las extensiones del Shapefile
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    file_path = f"{path_base}{ext}"
                    if os.path.exists(file_path):
                        zf.write(file_path, arcname=f"{row['Nombre_Arch']}/{base_name}{ext}")

    st.download_button(
        label="📥 Descargar todos los Shapefiles (1 por carpeta)",
        data=zip_buffer.getvalue(),
        file_name="Concesiones_Individuales.zip",
        mime="application/zip"
    )
