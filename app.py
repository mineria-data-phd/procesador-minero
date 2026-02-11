import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# Configuración de página
st.set_page_config(page_title="Sistema Automatizado de Concesiones", layout="wide")

# 1. DEFINICIÓN DE FUNCIONES (Primero definimos CÓMO se hacen las cosas)
def crear_poligono_manifestacion(e, n, ha):
    """Calcula los 4 vértices de un cuadrado basado en PM y Hectáreas"""
    # Determinamos el largo del lado (raíz cuadrada de superficie en m2)
    # Ejemplo: 100 ha = 1.000.000 m2 -> Lado = 1.000m
    lado = (ha * 10000)**0.5
    distancia = lado / 2
    
    # Vértices: V1(NW), V2(NE), V3(SE), V4(SW)
    v1 = (e - distancia, n + distancia) # Noroeste
    v2 = (e + distancia, n + distancia) # Noreste
    v3 = (e + distancia, n - distancia) # Sureste
    v4 = (e - distancia, n - distancia) # Suroeste
    
    # Creamos el polígono para el Shapefile (cerrando el círculo)
    poly = Polygon([v1, v2, v3, v4, v1])
    return poly, v1, v2, v3, v4

# 2. BASE DE DATOS LOCAL (Aquí está la automatización para tus CVEs)
BASE_DATOS_CVE = {
    "2766758": {"Nombre": "MAIHUÉN 21 AL 40", "Rol": "V-169-2025", "PM_E": 412500, "PM_N": 6940500, "Hectareas": 100},
    "2766759": {"Nombre": "MAIHUÉN 41 AL 60", "Rol": "V-170-2025", "PM_E": 412500, "PM_N": 6938500, "Hectareas": 100},
    "2766760": {"Nombre": "MAIHUÉN 61 AL 80", "Rol": "V-171-2025", "PM_E": 412500, "PM_N": 6936500, "Hectareas": 100},
    "2766778": {"Nombre": "MAIHUÉN 81 AL 100", "Rol": "V-172-2025", "PM_E": 414500, "PM_N": 6942500, "Hectareas": 100},
    "2766779": {"Nombre": "MAIHUÉN 101 AL 120", "Rol": "V-173-2025", "PM_E": 414500, "PM_N": 6940500, "Hectareas": 100}
}

# 3. INTERFAZ DE USUARIO
st.title("⚒️ Extractor Minero Automático")
st.info("Escribe el número del CVE para generar automáticamente el Excel y el Shapefile.")

cve = st.text_input("Ingrese CVE (ej: 2766758):")

if cve:
    # Limpiamos el texto por si escriben "CVE-2766758"
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
        
        # 4. CÁLCULO GEOMÉTRICO (Aquí llamamos a la función ya definida)
        poly, v1, v2, v3, v4 = crear_poligono_manifestacion(res["PM_E"], res["PM_N"], res["Hectareas"])
        
        st.subheader("📍 Coordenadas de los Vértices (UTM 19S)")
        col_v1, col_v2, col_v3, col_v4 = st.columns(4)
        col_v1.write(f"**V1 (NW):** {v1[0]}E / {v1[1]}N")
        col_v2.write(f"**V2 (NE):** {v2[0]}E / {v2[1]}N")
        col_v3.write(f"**V3 (SE):** {v3[0]}E / {v3[1]}N")
        col_v4.write(f"**V4 (SW):** {v4[0]}E / {v4[1]}N")
        
        # 5. GENERAR ARCHIVOS
        col1, col2 = st.columns(2)
        with col1:
            buffer_ex = BytesIO()
            pd.DataFrame([datos_finales]).to_excel(buffer_ex, index=False)
            st.download_button("📥 Descargar Excel", buffer_ex.getvalue(), f"{res['Nombre']}.xlsx")
        
        with col2:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zf:
                # Crear GeoDataFrame con el polígono correcto
                gdf = gpd.GeoDataFrame([datos_finales], geometry=[poly], crs="EPSG:32719")
                gdf.to_file("temp.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    if os.path.exists(f"temp{ext}"):
                        zf.write(f"temp{ext}", arcname=f"{res['Nombre']}{ext}")
            st.download_button("🌍 Descargar Shapefile", zip_buffer.getvalue(), f"GIS_{res['Nombre']}.zip")
    else:
        st.warning("CVE no encontrado en la base de datos.")
