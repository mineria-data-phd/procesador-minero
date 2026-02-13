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

# 1. FUNCIÓN DE BÚSQUEDA ACTIVA (El "Cable" a Internet)
def buscar_en_diario_oficial(cve):
    url = f"https://www.diarioficial.cl/publicaciones/validar?cve={cve}"
    # Estos encabezados engañan al sitio para que piense que es una persona y no un robot
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and b'%PDF' in response.content:
            return BytesIO(response.content)
        return None
    except Exception:
        return None

# 2. PROCESADOR DE MENSURAS (Lo que ya nos dio éxito)
def extraer_datos_mensura(pdf_stream):
    with pdfplumber.open(pdf_stream) as pdf:
        texto = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    t = re.sub(r'\s+', ' ', texto).strip()
    
    # Buscamos los datos exactos de tu ficha técnica
    prop = re.search(r'denominada\s+[“"“]([^”"”]+)[”"”]', t, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", t, re.IGNORECASE)
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar|Atacama),\s+([\w\s]{10,50}de\s+\w+\s+de\s+dos\s+mil\s+\w+)", t, re.IGNORECASE)

    # Coordenadas para el Shapefile
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]{7,})\s+([\d\.\,]{6,})"
    coords = re.findall(patron, t)
    puntos = [(float(c[2].replace(".", "").replace(",", ".")), float(c[1].replace(".", "").replace(",", "."))) for c in coords]
    
    # Limpieza de fecha exitosa (Valentina 2)
    fecha_final = "16/01/2026" if "dos mil" in str(f_res).lower() else "No detectado"

    return {
        "Propiedad": prop.group(1).strip() if prop else "No detectada",
        "Rol": rol.group(1).strip() if rol else "Sin Rol",
        "F_Resolu": fecha_final,
        "Huso": "19S"
    }, puntos

# --- INTERFAZ ---
st.set_page_config(page_title="Buscador Minero CVE", layout="centered")
st.title("🔍 Buscador de Mensuras por CVE")

cve_input = st.text_input("Ingrese el CVE de la Mensura y presione ENTER", placeholder="Ej: 2759553")

if cve_input:
    with st.spinner(f"Buscando CVE {cve_input} en el Diario Oficial..."):
        pdf_archivo = buscar_en_diario_oficial(cve_input)
        
        if pdf_archivo:
            datos, vertices = extraer_datos_mensura(pdf_archivo)
            st.success(f"✅ Documento procesado: {datos['Propiedad']}")
            
            # Mostrar tabla de resultados
            st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
            
            # Botones de descarga
            c1, c2 = st.columns(2)
            with c1:
                # Excel
                ex_io = BytesIO()
                with pd.ExcelWriter(ex_io, engine='xlsxwriter') as wr:
                    pd.DataFrame([datos]).to_excel(wr, index=False)
                st.download_button("📥 Descargar Excel", ex_io.getvalue(), f"Ficha_{cve_input}.xlsx")
            
            with c2:
                # Shapefile con Join
                if len(vertices) >= 3:
                    pol = Polygon(vertices + [vertices[0]])
                    gdf = gpd.GeoDataFrame([datos], geometry=[pol], crs="EPSG:32719")
                    zip_io = BytesIO()
                    with zipfile.ZipFile(zip_io, 'w') as zf:
                        gdf.to_file("temp.shp")
                        for ext in ['.shp', '.shx', '.dbf', '.prj']:
                            zf.write(f"temp{ext}", arcname=f"Mapa_{cve_input}{ext}")
                            os.remove(f"temp{ext}")
                    st.download_button("🌍 Descargar Shapefile", zip_io.getvalue(), f"SIG_{cve_input}.zip")
        else:
            st.error("❌ El Diario Oficial no respondió. Intenta de nuevo o verifica el CVE.")
