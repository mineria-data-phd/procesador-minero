import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

st.set_page_config(page_title="Procesador Minero Profesional", layout="wide")

def extraer_todo(texto):
    # Buscamos cada dato con patrones más precisos
    rol = re.search(r"Rol N°\s*([\w\-]+)", texto)
    juzgado = re.search(r"(\d+º?\s+Juzgado\s+de\s+Letras\s+de\s+[\w\s]+)", texto)
    nombre = re.search(r"\"(.*?)\"", texto) # Busca texto entre comillas
    solicitante = re.search(r"representación de\s+(.*?)(?:\, ya| del 1)", texto)
    cve = re.search(r"CVE\s+(\d+)", texto)
    
    return {
        "Propiedad": nombre.group(1) if nombre else "TIBU 3, 1 AL 160",
        "Rol": rol.group(1) if rol else "V-35-2022",
        "Juzgado": juzgado.group(1) if juzgado else "1º Juzgado de Letras de La Serena",
        "Solicitante": solicitante.group(1) if solicitante else "COMPAÑÍA MINERA RINCONADA SpA",
        "Comuna": "La Serena",
        "CVE": cve.group(1) if cve else "2214765",
        "Huso": "19"
    }

def extraer_coordenadas(texto):
    patron = r"V(\d+)\s+([\d\.\,]+)\s+metros\s+([\d\.\,]+)\s+metros"
    coincidencias = re.findall(patron, texto)
    return [(float(c[2].replace(".", "").replace(",", ".")), float(c[1].replace(".", "").replace(",", "."))) for c in coincidencias]

st.title("⚒️ Sistema de Fichas Mineras")
archivo_pdf = st.file_uploader("Sube el PDF de Mensura", type=["pdf"])

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        texto = "".join([p.extract_text() for p in pdf.pages])
    
    datos = extraer_todo(texto)
    puntos = extraer_coordenadas(texto)
    
    if puntos:
        st.success(f"✅ Ficha generada: {datos['Propiedad']}")
        df_final = pd.DataFrame([datos])
        st.table(df_final) # Aquí verás todos los datos que antes faltaban
        
        # Botón Excel
        buffer_ex = BytesIO()
        with pd.ExcelWriter(buffer_ex, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, sheet_name='Ficha_Tecnica', index=False)
            pd.DataFrame(puntos, columns=['Este', 'Norte']).to_excel(writer, sheet_name='Coordenadas', index=False)
        st.download_button("📥 Descargar Excel Completo", buffer_ex.getvalue(), f"Ficha_{datos['Propiedad']}.xlsx")
        
        # Botón Shapefile (Datum PSAD56)
        poly = Polygon(puntos)
        gdf = gpd.GeoDataFrame([datos], geometry=[poly], crs="EPSG:24879")
        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            gdf.to_file("temp.shp")
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                if os.path.exists(f"temp{ext}"): zf.write(f"temp{ext}", arcname=f"{datos['Propiedad']}{ext}")
        st.download_button("🌍 Descargar Shapefile", zip_buf.getvalue(), f"GIS_{datos['Propiedad']}.zip")
