import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# Configuración de la página
st.set_page_config(page_title="Sistema Minero Integral PRO", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN ---

def limpiar_texto(t):
    if not t: return ""
    return re.sub(r'\s+', ' ', t).strip()

def extraer_datos_mineros(texto_sucio):
    texto = limpiar_texto(texto_sucio)
    prop = re.search(r'(?:denominada|pertenencia|pertenencias)\s+[“"“]([^”"”]+)[”"”]', texto, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    juz = re.search(r"(?:S\.J\.L\.|JUZGADO)\s*(\d+.*? (?:COPIAPÓ|LA SERENA|VALLENAR|SANTIAGO))", texto, re.IGNORECASE)
    solic = re.search(r"representación(?:.*? de| de)\s+([^,]+?)(?:\s*,|\s+individualizada|\s+ya|$)", texto, re.IGNORECASE)
    f_pub = re.search(r"(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto)
    f_sol_m = re.search(r"(?:manifestadas|presentación)\s+con\s+fecha\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar),\s+([a-z\s]+de\s+[a-z]+\s+de\s+dos\s+mil\s+[a-z]+)", texto, re.IGNORECASE)

    return {
        "Propiedad": prop.group(1).strip() if prop else "No detectado",
        "Rol": rol.group(1).strip() if rol else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Solicitante": solic.group(1).strip().replace('“', '').replace('”', '') if solic else "No detectado",
        "Comuna": "Copiapó" if "COPIAPÓ" in texto.upper() else "La Serena",
        "CVE": re.search(r"CVE\s+(\d+)", texto).group(1) if re.search(r"CVE\s+(\d+)", texto) else "No detectado",
        "F_Solicitud": f_sol_m.group(1) if f_sol_m else "No detectado",
        "F_Resolucion": f_res.group(1).strip() if f_res else "No detectado",
        "F_Publicacion": f_pub.group(1) if f_pub else "No detectado",
        "Huso": "19"
    }

def extraer_coordenadas(texto):
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]+)\s+([\d\.\,]+)"
    coincidencias = re.findall(patron, texto)
    puntos = []
    for c in coincidencias:
        norte = float(c[1].replace(".", "").replace(",", "."))
        este = float(c[2].replace(".", "").replace(",", "."))
        puntos.append((este, norte)) # Formato (X, Y) para GIS
    return puntos

# --- INTERFAZ ---

st.title("⚒️ Sistema de Gestión Minera Integral")
tab1, tab2 = st.tabs(["🔍 Paso 1: Por CVE", "📄 Paso 2: Por PDF de Mensura"])

with tab1:
    st.subheader("Búsqueda por CVE")
    cve_input = st.text_input("Ingresa el CVE:")
    if cve_input: st.info(f"Módulo CVE {cve_input} activo.")

with tab2:
    st.subheader("Procesador de PDF")
    archivo_pdf = st.file_uploader("Sube el PDF de Mensura", type=["pdf"])
    
    if archivo_pdf:
        with pdfplumber.open(archivo_pdf) as pdf:
            texto_completo = " ".join([p.extract_text() for p in pdf.pages])
        
        datos = extraer_datos_mineros(texto_completo)
        puntos = extraer_coordenadas(texto_completo)
        
        if datos:
            st.success(f"✅ Ficha generada: {datos['Propiedad']}")
            st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Información"]))
            
            col1, col2 = st.columns(2)
            
            # --- DESCARGA EXCEL ---
            with col1:
                out_ex = BytesIO()
                with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
                    pd.DataFrame([datos]).to_excel(writer, sheet_name='Ficha', index=False)
                    pd.DataFrame(puntos, columns=['Este (X)', 'Norte (Y)']).to_excel(writer, sheet_name='Coordenadas', index=False)
                st.download_button("📥 Descargar Excel", out_ex.getvalue(), f"Ficha_{datos['Propiedad']}.xlsx")

            # --- DESCARGA SHAPEFILE ---
            with col2:
                if len(puntos) >= 3:
                    # Cerrar el polígono
                    puntos_cerrados = puntos + [puntos[0]]
                    poligono = Polygon(puntos_cerrados)
                    
                    # Crear GeoDataFrame (SIRGAS 2000 / UTM 19S)
                    gdf = gpd.GeoDataFrame([datos], geometry=[poligono], crs="EPSG:32719")
                    
                    # Crear ZIP con los 4 archivos del Shapefile
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w') as zf:
                        gdf.to_file("temp.shp")
                        for ext in ['.shp', '.shx', '.dbf', '.prj']:
                            if os.path.exists(f"temp{ext}"):
                                zf.write(f"temp{ext}", arcname=f"{datos['Propiedad']}{ext}")
                                os.remove(f"temp{ext}") # Limpieza
                    
                    st.download_button("🌍 Descargar Shapefile (ZIP)", zip_buffer.getvalue(), f"GIS_{datos['Propiedad']}.zip")
                else:
                    st.warning("No hay suficientes coordenadas para crear el Shapefile.")
