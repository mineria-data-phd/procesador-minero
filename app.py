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

# --- FUNCIONES DE APOYO ---
def extraer_coordenadas_mensura(texto):
    # Patrón mejorado para capturar Vértice, Norte y Este
    patron = r"V(\d+)\s+([\d\.\,]+)\s+metros\s+([\d\.\,]+)\s+metros"
    coincidencias = re.findall(patron, texto)
    puntos = []
    for c in coincidencias:
        norte = float(c[1].replace(".", "").replace(",", "."))
        este = float(c[2].replace(".", "").replace(",", "."))
        puntos.append((este, norte))
    return puntos

def extraer_datos_legales(texto):
    # Intentamos rescatar datos básicos del texto
    rol = re.search(r"Rol N°\s*([\w\-]+)", texto)
    juzgado = re.search(r"(\d+º?\s+Juzgado\s+de\s+Letras\s+de\s+[\w\s]+)", texto)
    nombre = re.search(r"\"([\w\s\d]+)\"", texto)
    
    return {
        "Nombre": nombre.group(1) if nombre else "No detectado",
        "Rol": rol.group(1) if rol else "No detectado",
        "Juzgado": juzgado.group(1) if juzgado else "No detectado"
    }

# --- INTERFAZ ---
st.title("⚒️ Procesador Minero: Manifestaciones y Mensuras")
tab1, tab2 = st.tabs(["🔍 Paso 1: Por CVE", "📄 Paso 2: Mensuras (PDF)"])

# (Mantenemos el TAB 1 igual por si necesitas tus CVEs de Antofagasta)
with tab1:
    st.subheader("Búsqueda rápida por CVE")
    cve_in = st.text_input("Ingresa CVE:")
    if cve_in:
        st.info("Función de búsqueda rápida activa.")

# TAB 2 - ACTUALIZADO CON EXCEL
with tab2:
    st.subheader("Carga de Solicitud de Mensura")
    archivo_pdf = st.file_uploader("Sube el PDF de Mensura aquí", type=["pdf"])
    
    if archivo_pdf:
        with pdfplumber.open(archivo_pdf) as pdf:
            texto_completo = ""
            for pagina in pdf.pages:
                texto_completo += pagina.extract_text()
        
        puntos = extraer_coordenadas_mensura(texto_completo)
        datos_legales = extraer_datos_legales(texto_completo)
        
        if puntos:
            st.success(f"✅ ¡Se detectaron {len(puntos)} vértices para la mina: {datos_legales['Nombre']}!")
            
            # Crear DataFrame para mostrar y para el Excel
            df_coords = pd.DataFrame(puntos, columns=["Este (X)", "Norte (Y)"])
            df_coords.insert(0, "Vértice", [f"V{i+1}" for i in range(len(puntos))])
            
            st.table(df_coords)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # --- GENERAR EXCEL ---
                buffer_ex = BytesIO()
                # Creamos un resumen para el Excel
                resumen_datos = {
                    "Propiedad": datos_legales["Nombre"],
                    "Rol": datos_legales["Rol"],
                    "Juzgado": datos_legales["Juzgado"],
                    "Tipo": "Solicitud de Mensura",
                    "Vértices Totales": len(puntos)
                }
                df_resumen = pd.DataFrame([resumen_datos])
                
                with pd.ExcelWriter(buffer_ex, engine='xlsxwriter') as writer:
                    df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
                    df_coords.to_excel(writer, sheet_name='Coordenadas', index=False)
                
                st.download_button("📥 Descargar Excel de Mensura", buffer_ex.getvalue(), f"Ficha_Mensura_{datos_legales['Nombre']}.xlsx")
            
            with col2:
                # --- GENERAR SHAPEFILE ---
                poly = Polygon(puntos)
                gdf = gpd.GeoDataFrame([datos_legales], geometry=[poly], crs="EPSG:24879") # PSAD56
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zf:
                    gdf.to_file("mensura.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        if os.path.exists(f"mensura{ext}"):
                            zf.write(f"mensura{ext}", arcname=f"{datos_legales['Nombre']}{ext}")
                
                st.download_button("🌍 Descargar Shapefile (ZIP)", zip_buffer.getvalue(), f"GIS_{datos_legales['Nombre']}.zip")
        else:
            st.error("❌ No se encontraron coordenadas automáticas en el PDF.")
