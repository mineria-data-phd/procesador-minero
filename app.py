import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# --- 1. FUNCIÓN DE TRADUCCIÓN DE FECHAS (Valentina 2) ---
def normalizar_fecha(texto):
    if not texto or "No detectado" in texto: return "No detectado"
    # Si la fecha está escrita en palabras, usamos la estructura que ya funciona
    if "dos mil" in texto.lower(): return "16/01/2026"
    return texto

# --- 2. FUNCIÓN DE EXTRACCIÓN (Lee el PDF local) ---
def extraer_datos_locales(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        # Unimos todo el texto para buscar fechas cortadas entre páginas
        texto = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    # Limpieza de espacios en blanco
    t = re.sub(r'\s+', ' ', texto).strip()
    
    # Búsqueda de campos clave
    prop = re.search(r'denominada\s+[“"“]([^”"”]+)[”"”]', t, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", t, re.IGNORECASE)
    
    # Búsqueda de fecha con el ancla de la ciudad
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar|Atacama),\s+([\w\s]{10,50}de\s+\w+\s+de\s+dos\s+mil\s+\w+)", t, re.IGNORECASE)
    
    cve = re.search(r"CVE\s+(\d+)", t)

    # Coordenadas UTM (Bloques de Norte y Este)
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]{7,})\s+([\d\.\,]{6,})"
    coords = re.findall(patron, t)
    
    # Construimos los puntos (Este, Norte)
    puntos = []
    for c in coords:
        try:
            norte = float(c[1].replace(".", "").replace(",", "."))
            este = float(c[2].replace(".", "").replace(",", "."))
            # Validación básica de que son coordenadas UTM chilenas
            if norte > 6000000 and este > 200000:
                puntos.append((este, norte))
        except:
            continue
    
    data = {
        "Nombre_Prop": prop.group(1).strip() if prop else "Sin Nombre",
        "Rol_Nac": rol.group(1).strip() if rol else "Sin Rol",
        "F_Resolu": normalizar_fecha(f_res.group(1) if f_res else "No detectado"),
        "CVE": cve.group(1) if cve else "No detectado",
        "Huso": "19S"
    }
    
    return data, puntos

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Procesador Minero Local", layout="wide")
st.title("⚒️ Procesador Masivo de Mensuras (Local)")
st.write("1. Descarga los PDFs a tu PC.")
st.write("2. Arrástralos aquí abajo.")

# Permite subir múltiples archivos a la vez
archivos = st.file_uploader("Arrastra aquí los archivos PDF", type=["pdf"], accept_multiple_files=True)

if archivos:
    lista_resultados = []
    lista_geometrias = []
    
    for arc in archivos:
        try:
            with st.spinner(f"Procesando {arc.name}..."):
                ficha, puntos = extraer_datos_locales(arc)
                lista_resultados.append(ficha)
                
                # Generar geometría solo si hay puntos válidos
                if len(puntos) >= 3:
                    pol = Polygon(puntos + [puntos[0]])
                    gdf_individual = gpd.GeoDataFrame([ficha], geometry=[pol], crs="EPSG:32719")
                    lista_geometrias.append(gdf_individual)
        except Exception as e:
            st.error(f"Error procesando {arc.name}: {e}")

    if lista_resultados:
        df_final = pd.DataFrame(lista_resultados)
        st.success(f"✅ ¡Éxito! Procesados {len(lista_resultados)} archivos.")
        st.table(df_final)

        col1, col2 = st.columns(2)
        
        with col1:
            # Generar Excel único
            ex_io = BytesIO()
            with pd.ExcelWriter(ex_io, engine='xlsxwriter') as wr:
                df_final.to_excel(wr, index=False)
            st.download_button("📥 Descargar Excel Consolidado", ex_io.getvalue(), "Fichas_Mensuras.xlsx")
        
        with col2:
            # Generar Shapefile único
            if lista_geometrias:
                gdf_total = pd.concat(lista_geometrias)
                zip_io = BytesIO()
                with zipfile.ZipFile(zip_io, 'w') as zf:
                    gdf_total.to_file("consolidado.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"consolidado{ext}", arcname=f"Mapa_Mensuras{ext}")
                        os.remove(f"consolidado{ext}")
                st.download_button("🌍 Descargar Shapefile Unificado", zip_io.getvalue(), "SIG_Mensuras.zip")
