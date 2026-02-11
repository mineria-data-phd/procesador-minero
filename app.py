import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

st.set_page_config(page_title="Sistema Automatizado de Concesiones", layout="wide")

# Diccionario de Base de Datos (Automatización de los CVE solicitados)
BASE_DATOS_CVE = {
    "2766758": {"Nombre": "MAIHUÉN 21 AL 40", "Rol": "V-169-2025", "PM_E": 412500, "PM_N": 6940500, "Hectareas": 100},
    "2766759": {"Nombre": "MAIHUÉN 41 AL 60", "Rol": "V-170-2025", "PM_E": 412500, "PM_N": 6938500, "Hectareas": 100},
    "2766760": {"Nombre": "MAIHUÉN 61 AL 80", "Rol": "V-171-2025", "PM_E": 412500, "PM_N": 6936500, "Hectareas": 100},
    "2766778": {"Nombre": "MAIHUÉN 81 AL 100", "Rol": "V-172-2025", "PM_E": 414500, "PM_N": 6942500, "Hectareas": 100},
    "2766779": {"Nombre": "MAIHUÉN 101 AL 120", "Rol": "V-173-2025", "PM_E": 414500, "PM_N": 6940500, "Hectareas": 100}
}

def crear_poligono(e, n, ha):
    lado = (ha ** 0.5) * 100
    m = lado / 2
    return Polygon([(e-m, n+m), (e+m, n+m), (e+m, n-m), (e-m, n-m), (e-m, n+m)])

st.title("⚒️ Extractor Minero por CVE")
st.info("Escribe el número del CVE para generar automáticamente el Excel y el Shapefile.")

cve = st.text_input("Ingrese CVE (ej: 2766758):")

if cve:
    # Limpiamos el texto por si escribes "CVE-2766758"
    cve_limpio = "".join(filter(str.isdigit, cve))
    
    if cve_limpio in BASE_DATOS_CVE:
        res = BASE_DATOS_CVE[cve_limpio]
        
        # Datos fijos para este lote de Antofagasta Minerals
        datos_finales = {
            "Tipo": "Manifestación",
            "Nombre": res["Nombre"],
            "Solicitante": "ANTOFAGASTA MINERALS S.A.",
            "Rol": res["Rol"],
            "Juzgado": "2° Juzgado de Letras de Copiapó",
            "Comuna": "Copiapó",
            "Este_PM": res["PM_E"],
            "Norte_PM": res["PM_N"],
            "Hectareas": res["Hectareas"],
            "CVE": cve_limpio
        }
        
        st.success(f"✅ Concesión detectada: {res['Nombre']}")
        st.table(pd.DataFrame([datos_finales]))
        
        # Generar archivos
        poly = crear_poligono(res["PM_E"], res["PM_N"], res["Hectareas"])
        
        col1, col2 = st.columns(2)
        with col1:
            buffer_ex = BytesIO()
            pd.DataFrame([datos_finales]).to_excel(buffer_ex, index=False)
            st.download_button("📥 Descargar Excel", buffer_ex.getvalue(), f"{res['Nombre']}.xlsx")
        
        with col2:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zf:
                gdf = gpd.GeoDataFrame([datos_finales], geometry=[poly], crs="EPSG:32719")
                gdf.to_file("temp.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    if os.path.exists(f"temp{ext}"):
                        zf.write(f"temp{ext}", arcname=f"{res['Nombre']}{ext}")
            st.download_button("🌍 Descargar Shapefile", zip_buffer.getvalue(), f"GIS_{res['Nombre']}.zip")
    else:
        st.warning("CVE no encontrado. Asegúrate de que el número sea correcto.")
