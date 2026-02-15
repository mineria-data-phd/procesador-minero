import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# --- 1. MOTOR DE EXTRACCIÓN MEJORADO ---
def extraer_datos_precision(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto_completo = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    t_limpio = re.sub(r'\s+', ' ', texto_completo).strip()
    
    # A. IDENTIFICAR TIPO DE PDF (Crucial para el error 1)
    tipo = "Pedimento"
    if "EXTRACTO" in t_limpio.upper(): tipo = "Extracto"
    elif "MENSURA" in t_limpio.upper(): tipo = "Mensura"
    
    # B. FICHA TÉCNICA (Corrigiendo error 2 y 3)
    # Propiedad: Busca comillas o "denominada"
    prop = re.search(r'(?:denominada|Concesión:|pertenencias mineras)\s*[“"“]([^”"”]+)[”"”]', t_limpio, re.IGNORECASE)
    # Rol: Busca formato 00000-X000-0
    rol = re.search(r"Rol\s+(?:Nacional|N\.?º)\s*([A-Z0-9\-]+)", t_limpio, re.IGNORECASE)
    # Juzgado: Busca palabras clave en un rango corto
    juzgado = re.search(r"((?:Primer|Segundo|Tercer|S\.J\.L\.)\s+Juzgado\s+[\w\s]{0,20}(?:Copiapó|Vallenar|Santiago|La Serena))", t_limpio, re.IGNORECASE)
    # Solicitante: Busca nombres propios después de la palabra clave
    solic = re.search(r"(?:solicitadas? por|representación de|presentada por)\s+([A-ZÁÉÍÓÚ\s]+?)(?:\s*,|\s+mensuradas|$)", t_limpio, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", t_limpio)

    # C. COORDENADAS (Corrigiendo error de TOMY 8A)
    puntos = []
    for linea in texto_completo.split('\n'):
        # Filtro: Detectar números tipo UTM ignorando letras y comillas
        nums = re.findall(r'(\d[\d\.\,]{5,12})', linea)
        if len(nums) >= 2:
            try:
                # Limpieza: Convertir "6.993.700,000" a 6993700.0
                v1 = float(nums[0].replace('.', '').replace(',', '.'))
                v2 = float(nums[1].replace('.', '').replace(',', '.'))
                
                # Asumimos el mayor es Norte, menor es Este
                norte = max(v1, v2)
                este = min(v1, v2)
                
                # Validación geográfica (Chile Huso 19S)
                if 6000000 < norte < 8000000 and 200000 < este < 900000:
                    if (este, norte) not in puntos:
                        puntos.append((este, norte))
            except:
                continue

    return {
        "Tipo": tipo,
        "Propiedad": prop.group(1).strip() if prop else "No detectada",
        "Rol_Nac": rol.group(1).strip() if rol else "Sin Rol",
        "Juzgado": juzgado.group(1).strip() if juzgado else "No detectado",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "CVE": cve.group(1) if cve else "No detectado",
        "Archivo": pdf_file.name
    }, puntos

# --- 2. INTERFAZ ---
st.set_page_config(page_title="Motor Minero V4", layout="wide")
st.title("⚒️ Motor Minero de Alta Precisión (V4)")
st.write("Sube los tres tipos de PDF para consolidar datos.")

archivos = st.file_uploader("Sube tus archivos", type=["pdf"], accept_multiple_files=True)

if archivos:
    resultados, geometrias = [], []
    for arc in archivos:
        ficha, pts = extraer_datos_precision(arc)
        resultados.append(ficha)
        if len(pts) >= 3:
            pol = Polygon(pts + [pts[0]])
            geometrias.append(gpd.GeoDataFrame([ficha], geometry=[pol], crs="EPSG:32719"))

    if resultados:
        df = pd.DataFrame(resultados)
        st.write("### 📊 Vista Previa de Datos")
        st.table(df) # Corregir errores aquí
        
        c1, c2 = st.columns(2)
        with c1:
            buf = BytesIO()
            df.to_excel(buf, index=False)
            st.download_button("📥 Descargar Excel", buf.getvalue(), "Consolidado_V4.xlsx")
        with c2:
            if geometrias:
                gdf_total = pd.concat(geometrias)
                buf_zip = BytesIO()
                with zipfile.ZipFile(buf_zip, 'w') as zf:
                    gdf_total.to_file("final.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"final{ext}", arcname=f"Mapa_Mineria{ext}")
                        os.remove(f"final{ext}")
                st.download_button("🌍 Descargar Shapefile", buf_zip.getvalue(), "SIG_V4.zip")
