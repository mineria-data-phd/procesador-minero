import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# --- 1. MOTOR DE EXTRACCIÓN DE ALTA PRECISIÓN ---
def motor_v5_total(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto_paginas = [p.extract_text() for p in pdf.pages if p.extract_text()]
        texto_completo = "\n".join(texto_paginas)
    
    t_limpio = re.sub(r'\s+', ' ', texto_completo).strip()
    
    # A. IDENTIFICACIÓN DE TIPO (Error 1 corregido)
    tipo = "Pedimento/Manifestación"
    if "EXTRACTO" in t_limpio.upper(): tipo = "Extracto"
    elif "MENSURA" in t_limpio.upper(): tipo = "Mensura"

    # B. FICHA TÉCNICA (Errores 2, 3 y 4 corregidos)
    prop = re.search(r'(?:denominada|Concesión:|pertenencias mineras|denominadas)\s*[“"“]([^”"”]+)[”"”]', t_limpio, re.IGNORECASE)
    rol = re.search(r"Rol\s+(?:Nacional|N\.?º)\s*([A-Z0-9\-]+)", t_limpio, re.IGNORECASE)
    # Buscador de Juzgado más flexible (S.J.L o Juzgado de Letras)
    juz = re.search(r"((?:Primer|Segundo|Tercer|S\.J\.L\.|Juzgado de Letras)\s+[\w\s]{0,20}(?:Copiapó|Vallenar|Santiago|La Serena))", t_limpio, re.IGNORECASE)
    # Solicitante limpio (detiene la captura antes de la paja legal)
    solic = re.search(r"(?:solicitadas? por|representación de|presentada por)\s+([A-ZÁÉÍÓÚÑ\s]{3,40})(?:\s*,|\s+mensuradas|\s+domiciliado|$)", t_limpio, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", t_limpio)

    nombre_prop = prop.group(1).strip() if prop else "Sin Nombre"
    
    ficha = {
        "Tipo": tipo,
        "Propiedad": nombre_prop,
        "Rol_Nac": rol.group(1).strip() if rol else "Sin Rol",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "CVE": cve.group(1) if cve else "No detectado"
    }

    # C. COORDENADAS (El "Imán" mejorado para TOMY 8A)
    puntos_lista = []
    for linea in texto_completo.split('\n'):
        # Extrae números ignorando comillas '"6.993.700,000"'
        nums = re.findall(r'(\d[\d\.\,]{5,12})', linea)
        if len(nums) >= 2:
            try:
                v1 = float(nums[0].replace('.', '').replace(',', '.'))
                v2 = float(nums[1].replace('.', '').replace(',', '.'))
                norte, este = (v1, v2) if v1 > v2 else (v2, v1)
                
                if 6000000 < norte < 8000000 and 200000 < este < 900000:
                    puntos_lista.append({"Propiedad": nombre_prop, "Vértice": len(puntos_lista)+1, "Norte": norte, "Este": este})
            except: continue
            
    return ficha, puntos_lista

# --- 2. INTERFAZ ---
st.set_page_config(page_title="Motor Minero V5", layout="wide")
st.title("⚒️ Motor Minero Profesional (V5)")
st.write("Procesamiento masivo de Pedimentos, Mensuras y Extractos con exportación de coordenadas.")

archivos = st.file_uploader("Sube tus archivos PDF aquí", type=["pdf"], accept_multiple_files=True)

if archivos:
    fichas_finales = []
    coordenadas_finales = []
    geometrias = []
    
    for arc in archivos:
        f, pts = motor_v5_total(arc)
        fichas_finales.append(f)
        coordenadas_finales.extend(pts)
        
        # Generar geometría para el mapa
        if len(pts) >= 3:
            lista_pts = [(p['Este'], p['Norte']) for p in pts]
            pol = Polygon(lista_pts + [lista_pts[0]])
            geometrias.append(gpd.GeoDataFrame([f], geometry=[pol], crs="EPSG:32719"))

    if fichas_finales:
        df_fichas = pd.DataFrame(fichas_finales)
        df_coords = pd.DataFrame(coordenadas_finales)
        
        st.write("### 1. Fichas Técnicas Detectadas")
        st.table(df_fichas)
        
        if not df_coords.empty:
            st.write("### 2. Tabla de Coordenadas (Segunda Hoja)")
            st.dataframe(df_coords.head(10)) # Muestra las primeras 10
            
            # --- DESCARGA EXCEL CON DOS HOJAS ---
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df_fichas.to_excel(writer, sheet_name='Fichas_Tecnicas', index=False)
                df_coords.to_excel(writer, sheet_name='Coordenadas', index=False)
            st.download_button("📥 Descargar Excel (2 Hojas)", buf.getvalue(), "Reporte_Minero_Completo.xlsx")
            
            # --- DESCARGA SHAPEFILE ---
            if geometrias:
                gdf_total = pd.concat(geometrias)
                buf_zip = BytesIO()
                with zipfile.ZipFile(buf_zip, 'w') as zf:
                    gdf_total.to_file("mapa.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"mapa{ext}", arcname=f"Mapa_Mineria{ext}")
                        os.remove(f"mapa{ext}")
                st.download_button("🌍 Descargar Shapefile (SIG)", buf_zip.getvalue(), "Mapa_Mineria.zip")
