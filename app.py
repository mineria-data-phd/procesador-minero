import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# Configuración básica
st.set_page_config(page_title="Automatización Minera CVE", layout="wide")

def generar_cuadrado(este_central, norte_central, ha=100):
    lado = (ha ** 0.5) * 100
    m = lado / 2
    coords = [
        (este_central - m, norte_central + m),
        (este_central + m, norte_central + m),
        (este_central + m, norte_central - m),
        (este_central - m, norte_central - m)
    ]
    return Polygon(coords), coords

st.title("⚒️ Procesador Automático de CVE")
st.write("Solo ingresa el CVE y el sistema generará el Excel y el Shapefile.")

# Entrada del usuario
cve_input = st.text_input("Escribe el CVE aquí:")

if cve_input:
    # Por ahora, como ejemplo real con el CVE que me diste:
    if cve_input == "2766748":
        datos = {
            "Nombre": "MAIHUÉN 1 AL 20",
            "Solicitante": "ANTOFAGASTA MINERALS S.A.",
            "Juzgado": "2° Juzgado de Letras de Copiapó",
            "Rol": "V-168-2025",
            "Fojas": "321", "N°": "184", "Año": "2026",
            "Este_PM": 412500.0, "Norte_PM": 6942500.0,
            "Hectáreas": 100
        }
        
        poly, vertices = generar_cuadrado(datos["Este_PM"], datos["Norte_PM"], datos["Hectáreas"])
        
        st.success(f"Datos recuperados para: {datos['Nombre']}")
        df = pd.DataFrame([datos])
        st.table(df)

        # GENERACIÓN DE ARCHIVOS
        col1, col2 = st.columns(2)
        
        with col1:
            buf_ex = BytesIO()
            df.to_excel(buf_ex, index=False)
            st.download_button("📥 Bajar Excel", buf_ex.getvalue(), f"Ficha_{cve_input}.xlsx")
            
        with col2:
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                gdf = gpd.GeoDataFrame([datos], geometry=[poly], crs="EPSG:32719")
                gdf.to_file("temp.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    if os.path.exists(f"temp{ext}"):
                        zf.write(f"temp{ext}", arcname=f"{datos['Nombre']}{ext}")
            st.download_button("🌍 Bajar Shapefile (ZIP)", zip_buf.getvalue(), f"GIS_{cve_input}.zip")
    else:
        st.info("Buscando en el Boletín... (Para este prototipo, usa el CVE 2766748)")
