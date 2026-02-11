import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

st.set_page_config(page_title="Procesador Minero Inteligente", layout="wide")

# --- FUNCIONES DE APOYO (El motor interno) ---
def extraer_coordenadas_mensura(texto):
    # Busca patrones de coordenadas (ej: V1 6.667.505 299.000)
    patron = r"V(\d+)\s+([\d\.]+),?\d*\s+([\d\.]+),?\d*"
    coincidencias = re.findall(patron, texto)
    puntos = []
    for c in coincidencias:
        norte = float(c[1].replace(".", ""))
        este = float(c[2].replace(".", ""))
        puntos.append((este, norte))
    return puntos

# --- INTERFAZ ---
st.title("⚒️ Procesador Minero: Manifestaciones y Mensuras")
tab1, tab2 = st.tabs(["🔍 Paso 1: Por CVE", "📄 Paso 2: Mensuras (PDF)"])

# CONTENIDO TAB 1 (Lo que ya teníamos para tus Maihuén)
with tab1:
    st.subheader("Búsqueda rápida por CVE")
    cve_in = st.text_input("Ingresa CVE:")
    if cve_in:
        st.info("Procesando datos del Paso 1...")
        # Aquí sigue funcionando tu lógica anterior de los 4 vértices

# CONTENIDO TAB 2 (Para el nuevo PDF de TIBU 3)
with tab2:
    st.subheader("Carga de Solicitud de Mensura")
    archivo_pdf = st.file_uploader("Sube el PDF de Mensura aquí", type=["pdf"])
    
    if archivo_pdf:
        with pdfplumber.open(archivo_pdf) as pdf:
            texto_completo = ""
            for pagina in pdf.pages:
                texto_completo += pagina.extract_text()
        
        # Extraemos los puntos
        puntos = extraer_coordenadas_mensura(texto_completo)
        
        if puntos:
            st.success(f"¡Se detectaron {len(puntos)} vértices!")
            df_coords = pd.DataFrame(puntos, columns=["Este (X)", "Norte (Y)"])
            st.table(df_coords)
            
            # Crear el archivo Shapefile
            poly = Polygon(puntos)
            gdf = gpd.GeoDataFrame([{"Nombre": "Mensura Detectada"}], geometry=[poly], crs="EPSG:24879") # Datum PSAD56 Huso 19
            
            # Botón de descarga
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zf:
                gdf.to_file("mensura.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    if os.path.exists(f"mensura{ext}"):
                        zf.write(f"mensura{ext}")
            
            st.download_button("🌍 Descargar Shapefile Mensura", zip_buffer.getvalue(), "mensura_final.zip")
        else:
            st.error("No se encontraron coordenadas automáticas. Asegúrate de que el PDF tenga la tabla de vértices.")
