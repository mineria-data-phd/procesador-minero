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

# --- 1. CONFIGURACIÓN DE BÚSQUEDA WEB ---
def descargar_pdf_por_cve(cve):
    # URL oficial de validación del Diario Oficial
    url = f"https://www.diarioficial.cl/publicaciones/validar?cve={cve}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200 and b'%PDF' in response.content:
            return BytesIO(response.content)
        else:
            return None
    except:
        return None

# --- 2. EXTRACCIÓN DE DATOS (Foco en Extractos y Mensuras) ---
def extraer_datos_mineros(pdf_stream):
    with pdfplumber.open(pdf_stream) as pdf:
        texto = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    # Limpieza de texto para búsqueda
    t_limpio = re.sub(r'\s+', ' ', texto).strip()
    
    # Búsqueda de campos clave
    prop = re.search(r'(?:denominada|pertenencias mineras|concesión:)\s*[“"“]([^”"”]+)[”"”]', t_limpio, re.IGNORECASE)
    rol = re.search(r"Rol\s+Nac\w*\s*N[°º]?\s*([A-Z0-9\-]+)", t_limpio, re.IGNORECASE)
    juz = re.search(r"(?:S\.J\.L\.|JUZGADO|autos Rol.*? del)\s+([^,]+(?:COPIAPÓ|LA SERENA|VALLENAR|SANTIAGO))", t_limpio, re.IGNORECASE)
    solic = re.search(r"(?:solicitadas por|representación de)\s+([^,]+?)(?:\s*,|\s+individualizada|$)", t_limpio, re.IGNORECASE)
    
    # Fechas (Sentencia/Resolución y Publicación)
    f_res = re.search(r"fecha\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", t_limpio, re.IGNORECASE)
    f_pub = re.search(r"(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", t_limpio)

    datos = {
        "Propiedad": prop.group(1).strip() if prop else "No detectada",
        "Rol": rol.group(1).strip() if rol else "Sin Rol",
        "Juzgado": juz.group(1).strip() if juz else "Sin Juzgado",
        "Solicitante": solic.group(1).strip() if solic else "Sin Solicitante",
        "F_Resolucion": f_res.group(1) if f_res else "No detectada",
        "F_Publicacion": f_pub.group(1) if f_pub else "No detectada"
    }
    
    # Coordenadas (Norte y Este)
    patron_coords = r"([\d\.\,]{7,})\s+([\d\.\,]{6,})"
    coords = re.findall(patron_coords, t_limpio)
    puntos = [(float(c[1].replace(".", "").replace(",", ".")), float(c[0].replace(".", "").replace(",", "."))) for c in coords]
    
    return datos, puntos

# --- 3. INTERFAZ DE USUARIO ---
st.set_page_config(page_title="Buscador Minero CVE", layout="centered")
st.title("🔍 Buscador de Documentos por CVE")
st.write("Ingresa el código para generar automáticamente el Excel y Shapefile.")

cve_input = st.text_input("Ingrese el CVE (ej: 2590858)", placeholder="2590858")

if cve_input:
    with st.spinner(f"Buscando CVE {cve_input} en el Diario Oficial..."):
        pdf_file = descargar_pdf_por_cve(cve_input)
        
        if pdf_file:
            datos, puntos = extraer_datos_mineros(pdf_file)
            st.success(f"✅ Documento encontrado: {datos['Propiedad']}")
            
            # Mostrar Ficha técnica
            st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
            
            # --- SECCIÓN DE DESCARGAS ---
            c1, c2 = st.columns(2)
            
            with c1:
                # Excel
                ex_io = BytesIO()
                with pd.ExcelWriter(ex_io, engine='xlsxwriter') as wr:
                    pd.DataFrame([datos]).to_excel(wr, index=False)
                st.download_button("📥 Descargar Excel", ex_io.getvalue(), f"Ficha_{cve_input}.xlsx")
            
            with c2:
                # Shapefile (Solo si hay coordenadas)
                if len(puntos) >= 3:
                    pol = Polygon(puntos + [puntos[0]])
                    gdf = gpd.GeoDataFrame([datos], geometry=[pol], crs="EPSG:32719")
                    zip_io = BytesIO()
                    with zipfile.ZipFile(zip_io, 'w') as zf:
                        gdf.to_file("temp.shp")
                        for ext in ['.shp', '.shx', '.dbf', '.prj']:
                            zf.write(f"temp{ext}", arcname=f"Mapa_{cve_input}{ext}")
                            os.remove(f"temp{ext}")
                    st.download_button("🌍 Descargar Shapefile", zip_io.getvalue(), f"SIG_{cve_input}.zip")
                else:
                    st.warning("⚠️ El documento no contiene coordenadas para el Shapefile.")
        else:
            st.error("❌ No se pudo encontrar el documento. Verifique el CVE o la conexión.")
