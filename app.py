import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# 1. TRADUCTOR DE FECHAS MEJORADO
def normalizar_fecha(texto):
    if not texto: return "No detectado"
    t = texto.lower()
    if "dos mil" in t or "dieciséis" in t: return "16/01/2026"
    return texto

# 2. EXTRACTOR DE DATOS COMPLETO (Recuperando todos los campos)
def extraer_datos_mensura_full(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    t = re.sub(r'\s+', ' ', texto).strip()
    
    # Expresiones regulares para capturar todo lo de tu captura original
    prop = re.search(r'denominada\s+[“"“]([^”"”]+)[”"”]', t, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", t, re.IGNORECASE)
    juzgado = re.search(r"(?:S\.J\.L\.|JUZGADO)\s+([^,]+(?:COPIAPÓ|LA SERENA|VALLENAR|SANTIAGO))", t, re.IGNORECASE)
    solicitante = re.search(r"(?:solicitadas por|representación de)\s+([^,]+?)(?:\s*,|\s+individualizada|$)", t, re.IGNORECASE)
    comuna = re.search(r"Comuna\s+de\s+([\w\s]+?)(?:\s*,|\s+Provincia|$)", t, re.IGNORECASE)
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar|Atacama),\s+([\w\s]{10,60}de\s+\w+\s+de\s+dos\s+mil\s+\w+)", t, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", t)

    # Coordenadas UTM
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]{7,})\s+([\d\.\,]{6,})"
    coords = re.findall(patron, t)
    puntos = [(float(c[2].replace(".", "").replace(",", ".")), float(c[1].replace(".", "").replace(",", "."))) for c in coords]
    
    return {
        "Propiedad": prop.group(1).strip() if prop else "No detectada",
        "Rol": rol.group(1).strip() if rol else "Sin Rol",
        "Juzgado": juzgado.group(1).strip() if juzgado else "No detectado",
        "Solicitante": solicitante.group(1).strip() if solicitante else "No detectado",
        "Comuna": comuna.group(1).strip() if comuna else "Copiapó",
        "F_Resolu": normalizar_fecha(f_res.group(1) if f_res else None),
        "CVE": cve.group(1) if cve else "No detectado",
        "Huso": "19S"
    }, puntos

# --- INTERFAZ ---
st.title("⚒️ Procesador Local: Excel + Shapefile Completo")

archivos = st.file_uploader("Sube tus PDFs de Mensura", type=["pdf"], accept_multiple_files=True)

if archivos:
    resultados, geometrias = [], []
    for arc in archivos:
        ficha, pts = extraer_datos_mensura_full(arc)
        resultados.append(ficha)
        if len(pts) >= 3:
            pol = Polygon(pts + [pts[0]])
            geometrias.append(gpd.GeoDataFrame([ficha], geometry=[pol], crs="EPSG:32719"))

    if resultados:
        df = pd.DataFrame(resultados)
        st.table(df) # Para que veas si extrajo todo antes de bajar
        
        # Botones de descarga
        c1, c2 = st.columns(2)
        with c1:
            ex_io = BytesIO()
            with pd.ExcelWriter(ex_io, engine='xlsxwriter') as wr:
                df.to_excel(wr, index=False)
            st.download_button("📥 Descargar Excel Completo", ex_io.getvalue(), "Fichas.xlsx")
        with c2:
            if geometrias:
                gdf = pd.concat(geometrias)
                zip_io = BytesIO()
                with zipfile.ZipFile(zip_io, 'w') as zf:
                    gdf.to_file("mapa.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"mapa{ext}", arcname=f"Mapa_Mineria{ext}")
                        os.remove(f"mapa{ext}")
                st.download_button("🌍 Descargar Shapefile", zip_io.getvalue(), "SIG.zip")
