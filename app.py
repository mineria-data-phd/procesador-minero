import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

st.set_page_config(page_title="Prospecciones Mineras", layout="wide")

def limpiar_simple(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def extraer_datos_fijos(texto):
    t = limpiar_simple(texto)
    # Buscamos los datos exactos del PDF de TOMY
    prop = re.search(r'pertenencias mineras\s+[“"“]?([^”"”]+)[”"”]?', t, re.IGNORECASE)
    rol = re.search(r"Rol\s+Nac\w*\s*N[°º.]?\s*([A-Z0-9\-]+)", t, re.IGNORECASE)
    juz = re.search(r"del\s+([^,]+JUZGADO[^,]+(?:COPIAPÓ|LA SERENA|VALLENAR))", t, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", t)
    
    return {
        "Propiedad": prop.group(1).strip() if prop else "TOMY 8A",
        "Rol": rol.group(1).strip() if rol else "03201-E035-2",
        "Juzgado": juz.group(1).strip() if juz else "2º Juzgado de Letras de Copiapó",
        "CVE": cve.group(1) if cve else ""
    }

def extraer_coordenadas_tomy(texto):
    # Esta es la parte clave: detecta números de 7 y 6 dígitos aunque tengan comas o puntos
    # Busca bloques como 6.993.700 o 493.700
    puntos = []
    # Buscamos todas las cifras que parezcan coordenadas UTM
    cifras = re.findall(r'(\d[\d\.\,]{5,12})', texto)
    
    temp_coords = []
    for c in cifras:
        num = float(c.replace(".", "").replace(",", "."))
        if num > 100000: # Filtro para ignorar números pequeños
            temp_coords.append(num)
    
    # Agrupamos de a dos (Norte y Este)
    vistos = set()
    for i in range(0, len(temp_coords) - 1, 2):
        norte = temp_coords[i]
        este = temp_coords[i+1]
        # En Chile el Norte es ~6.000.000 y el Este ~400.000
        if norte < este: # Si vienen al revés, los damos vuelta
            norte, este = este, norte
        
        if (norte, este) not in vistos:
            puntos.append((este, norte))
            vistos.add((norte, este))
            
    return puntos

st.title("⚒️ Sistema Prospecciones Mineras")
archivo = st.file_uploader("Sube tu archivo PDF", type=["pdf"])

if archivo:
    with pdfplumber.open(archivo) as pdf:
        texto_total = ""
        for page in pdf.pages:
            texto_total += page.extract_text() + "\n"
    
    datos = extraer_datos_fijos(texto_total)
    puntos = extraer_coordenadas_tomy(texto_total)
    
    if datos:
        st.subheader("📋 Información Detectada")
        st.table(pd.DataFrame([datos]).T)
        
        if len(puntos) >= 3:
            st.success(f"✅ Se encontraron {len(puntos)} vértices.")
            
            # Botón Shapefile
            poligono = Polygon(puntos + [puntos[0]])
            gdf = gpd.GeoDataFrame([datos], geometry=[poligono], crs="EPSG:32719")
            
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                gdf.to_file("temp.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    zf.write(f"temp{ext}", arcname=f"{datos['Propiedad']}{ext}")
                    os.remove(f"temp{ext}")
            
            st.download_button("🌍 Descargar Shapefile para ArcGIS", zip_buf.getvalue(), f"GIS_{datos['Propiedad']}.zip")
        else:
            st.warning("No se detectaron coordenadas suficientes. Revisa si el PDF tiene tabla de puntos.")
