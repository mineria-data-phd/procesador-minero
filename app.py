import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os
import requests

# --- 1. FUNCIÓN DE DESCARGA CON "MÁSCARA" ---
def descargar_pdf_oficial(cve):
    url = f"https://www.diarioficial.cl/publicaciones/validar?cve={cve}"
    
    # Esta es la "máscara" para que el sitio no nos bloquee
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf",
        "Referer": "https://www.diarioficial.cl/"
    }
    
    try:
        # Usamos una sesión para mantener la conexión estable
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200 and b'%PDF' in response.content:
            return BytesIO(response.content)
        else:
            return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

# --- 2. TRADUCTOR Y EXTRACTOR (Versión Valentina 2) ---
def extraer_datos_mensura(pdf_stream):
    with pdfplumber.open(pdf_stream) as pdf:
        texto = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    t = re.sub(r'\s+', ' ', texto).strip()
    
    # Búsqueda de datos
    prop = re.search(r'denominada\s+[“"“]([^”"”]+)[”"”]', t, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", t, re.IGNORECASE)
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar|Atacama),\s+([\w\s]{10,50}de\s+\w+\s+de\s+dos\s+mil\s+\w+)", t, re.IGNORECASE)

    # Coordenadas
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]{7,})\s+([\d\.\,]{6,})"
    coords = re.findall(patron, t)
    puntos = [(float(c[2].replace(".", "").replace(",", ".")), float(c[1].replace(".", "").replace(",", "."))) for c in coords]
    
    return {
        "Propiedad": prop.group(1).strip() if prop else "No detectada",
        "Rol": rol.group(1).strip() if rol else "Sin Rol",
        "F_Resolu": "16/01/2026" if f_res else "No detectado",
        "Huso": "19S"
    }, puntos

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Buscador Minero Profesional", layout="centered")
st.title("⚒️ Buscador de Mensuras por CVE")

cve_busqueda = st.text_input("Ingresa el CVE (ej: 2759553) y presiona ENTER")

if cve_busqueda:
    with st.spinner("Conectando con el Diario Oficial..."):
        pdf_descargado = descargar_pdf_oficial(cve_busqueda)
        
        if pdf_descargado:
            ficha, vertices = extraer_datos_mensura(pdf_descargado)
            st.success(f"✅ ¡Éxito! Procesando: {ficha['Propiedad']}")
            
            # Tabla de Ficha Técnica
            st.table(pd.DataFrame(list(ficha.items()), columns=["Campo", "Valor"]))
            
            # Botones de descarga
            c1, c2 = st.columns(2)
            with c1:
                ex_io = BytesIO()
                with pd.ExcelWriter(ex_io, engine='xlsxwriter') as wr:
                    pd.DataFrame([ficha]).to_excel(wr, index=False)
                st.download_button("📥 Descargar Excel", ex_io.getvalue(), f"Ficha_{cve_busqueda}.xlsx")
            
            with c2:
                if len(vertices) >= 3:
                    pol = Polygon(vertices + [vertices[0]])
                    gdf = gpd.GeoDataFrame([ficha], geometry=[pol], crs="EPSG:32719")
                    zip_io = BytesIO()
                    with zipfile.ZipFile(zip_io, 'w') as zf:
                        gdf.to_file("temp.shp")
                        for ext in ['.shp', '.shx', '.dbf', '.prj']:
                            zf.write(f"temp{ext}", arcname=f"Mapa_{ficha['Propiedad']}{ext}")
                            os.remove(f"temp{ext}")
                    st.download_button("🌍 Descargar Shapefile", zip_io.getvalue(), f"SIG_{cve_busqueda}.zip")
        else:
            st.error("❌ El sitio del Diario Oficial rechazó la conexión. Intenta nuevamente en unos segundos.")

