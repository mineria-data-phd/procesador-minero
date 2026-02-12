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

def extraer_todo_robusto(texto):
    # 1. Datos Identificatorios
    rol = re.search(r"Rol N°\s*([\w\-]+)", texto, re.IGNORECASE)
    juzgado = re.search(r"(\d+º?\s+Juzgado\s+de\s+Letras\s+de\s+[\w\s]+)", texto, re.IGNORECASE)
    nombre = re.search(r"denominada\s+\"(.*?)\"", texto, re.IGNORECASE) or re.search(r"pertenencias\s+\"(.*?)\"", texto)
    
    # 2. Solicitante (Busca después de 'representación de' o 'representación judicial de')
    solicitante = re.search(r"representación(?:\s+judicial)?\s+(?:según\s+se\s+acreditará\s+de|de)\s+([^,.\n]+)", texto, re.IGNORECASE)
    
    # 3. Comuna y CVE
    comuna = re.search(r"domiciliado\s+en\s+([\w\s]+),", texto, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", texto)
    
    # 4. FECHAS (El punto más crítico)
    # Fecha de Publicación (Normalmente en el encabezado del Diario Oficial)
    f_publicacion = re.search(r"(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto)
    
    # Fecha de Solicitud de Mensura (Busca la fecha de la manifestación citada)
    f_sol_mensura = re.search(r"manifestadas\s+con\s+fecha\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto)
    
    # Fecha de Resolución/Mensura (Busca la fecha de la firma del Juez al final)
    f_mensura = re.search(r"(?:Copiapó|La Serena|Santiago),\s+(\w+\s+de\s+\w+\s+de\s+dos\s+mil\s+[\w\s]+)", texto, re.IGNORECASE)

    return {
        "Propiedad": nombre.group(1).strip() if nombre else "No detectado",
        "Rol": rol.group(1).strip() if rol else "No detectado",
        "Juzgado": juzgado.group(1).strip() if juzgado else "No detectado",
        "Solicitante": solicitante.group(1).strip() if solicitante else "No detectado",
        "Comuna": comuna.group(1).strip() if comuna else "No detectado",
        "CVE": cve.group(1) if cve else "No detectado",
        "F_Sol_Mensura": f_sol_mensura.group(1) if f_sol_mensura else "No detectado",
        "F_Mensura": f_mensura.group(1) if f_mensura else "No detectado",
        "F_Publicacion": f_publicacion.group(1) if f_publicacion else "No detectado",
        "Huso": "19"
    }

def extraer_coordenadas(texto):
    # Detecta V1, L1, etc. seguidos de coordenadas
    patron = r"(?:V|L)(\d+)\s+([\d\.\,]+)\s*(?:metros)?\s+([\d\.\,]+)\s*(?:metros)?"
    coincidencias = re.findall(patron, texto)
    return [(float(c[2].replace(".", "").replace(",", ".")), float(c[1].replace(".", "").replace(",", "."))) for c in coincidencias]

st.title("⚒️ Sistema de Fichas Mineras Pro")
tab1, tab2 = st.tabs(["🔍 Paso 1: Por CVE", "📄 Paso 2: Mensuras (PDF)"])

with tab2:
    archivo_pdf = st.file_uploader("Sube el PDF de Mensura", type=["pdf"])
    if archivo_pdf:
        with pdfplumber.open(archivo_pdf) as pdf:
            texto = "".join([p.extract_text() for p in pdf.pages])
        
        datos = extraer_todo_robusto(texto)
        puntos = extraer_coordenadas(texto)
        
        if puntos:
            st.success(f"✅ Ficha generada: {datos['Propiedad']}")
            df_display = pd.DataFrame(list(datos.items()), columns=["Dato", "Valor"])
            st.table(df_display)
            
            # Excel
            buffer_ex = BytesIO()
            with pd.ExcelWriter(buffer_ex, engine='xlsxwriter') as writer:
                pd.DataFrame([datos]).to_excel(writer, sheet_name='Ficha_Tecnica', index=False)
                pd.DataFrame(puntos, columns=['Este', 'Norte']).to_excel(writer, sheet_name='Coordenadas', index=False)
            st.download_button("📥 Descargar Excel Completo", buffer_ex.getvalue(), f"Ficha_{datos['Propiedad']}.xlsx")
            
            # Shapefile
            poly = Polygon(puntos)
            gdf = gpd.GeoDataFrame([datos], geometry=[poly], crs="EPSG:32719") # SIRGAS 2000 / UTM 19S
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                gdf.to_file("temp.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    if os.path.exists(f"temp{ext}"): zf.write(f"temp{ext}", arcname=f"{datos['Propiedad']}{ext}")
            st.download_button("🌍 Descargar Shapefile", zip_buf.getvalue(), f"GIS_{datos['Propiedad']}.zip")
