import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import box
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro - Vértices Final", layout="wide")
st.title("⚒️ Extractor de Expedientes con Cálculo de Vértices")

# REPARACIÓN: Función para identificar el tipo de trámite
def identificar_tramite(texto):
    t = texto.lower()
    if "rectificación" in t or "rectificacion" in t: return "Solicitud de Rectificación"
    if "testificación" in t or "testificacion" in t: return "Solicitud de Testificación"
    if "mensura" in t: return "Solicitud de Mensura"
    if "pedimento" in t or "manifestación" in t or "manifestacion" in t: return "Manifestación y Pedimento"
    return "Extracto EM y EP"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- JUZGADO ---
    diccionario_juzgados = {"primer": "1°", "1": "1°", "primero": "1°", "segundo": "2°", "2": "2°", "tercer": "3°", "3": "3°", "tercero": "3°"}
    juz_base = re.search(r'(Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z]+)', cuerpo, re.IGNORECASE)
    juzgado = "No detectado"
    if juz_base:
        pos = juz_base.start()
        fragmento = cuerpo[max(0, pos-20):pos].lower().strip()
        orden_match = re.search(r'\b(primer|segundo|tercer|1|2|3)\b', fragmento)
        if orden_match:
            prefijo = diccionario_juzgados.get(orden_match.group(1), orden_match.group(1) + "°")
            juzgado = f"{prefijo} {juz_base.group(0)}"
        else: juzgado = juz_base.group(0)

    # --- NOMBRE Y SOLICITANTE ---
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "No detectado"
    if nombre == "No detectado":
        especifico = re.search(r'\b([A-Z]{3,}\s\d+\-[A-Z])\b', cuerpo)
        nombre = especifico.group(1).strip() if especifico else "No detectado"

    solic_match = re.search(r'(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo, re.IGNORECASE)
    solicitante = solic_match.group(1).strip() if solic_match else "No detectado"
    if solicitante == "No detectado":
        empresa = re.search(r'(FQAM\s+EXPLORATION\s+\(CHILE\)\s+S\.A\.)', cuerpo)
        if empresa: solicitante = empresa.group(1).strip()

    # --- COORDENADAS (Punto Central) ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)

    # --- CÁLCULO DE VÉRTICES (3000m E-O x 1000m N-S) ---
    v = {}
    if x_c and y_c:
        v['V1_Este_X'], v['V1_Norte_Y'] = x_c - 1500, y_c + 500  # NW
        v['V2_Este_X'], v['V2_Norte_Y'] = x_c + 1500, y_c + 500  # NE
        v['V3_Este_X'], v['V3_Norte_Y'] = x_c + 1500, y_c - 500  # SE
        v['V4_Este_X'], v['V4_Norte_Y'] = x_c - 1500, y_c - 500  # SW
    else:
        for i in range(1, 5): v[f'V{i}_Este_X'] = v[f'V{i}_Norte_Y'] = "N/A"

    res = {
        "Archivo": pdf_file.name,
        "Tipo": identificar_tramite(cuerpo),
        "Nombre": nombre,
        "Solicitante": solicitante,
        "Rol": rol.group(1) if rol else "No detectado",
        "Juzgado": juzgado,
        "Centro_X": x_c, "Centro_Y": y_c
    }
    res.update(v)
    return res

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    st.dataframe(df)

    # Descarga Excel
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel con Vértices", out_ex.getvalue(), "Mineria_Reporte.xlsx")

    # Generación Shapefile Polígonos
    df_geo = df.dropna(subset=['Centro_X', 'Centro_Y']).copy()
    if not df_geo.empty:
        poligonos = [box(r.Centro_X-1500, r.Centro_Y-500, r.Centro_X+1500, r.Centro_Y+500) for _, r in df_geo.iterrows()]
        gdf = gpd.GeoDataFrame(df_geo, geometry=poligonos, crs="EPSG:32719")
        
        temp = "temp_shp"
        if not os.path.exists(temp): os.makedirs(temp)
        gdf.to_file(os.path.join(temp, "Concesiones.shp"))

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            for ex in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(os.path.join(temp, f"Concesiones{ex}"), arcname=f"Concesiones{ex}")
        st.download_button("🌍 Descargar Polígonos SHP", zip_buf.getvalue(), "Concesiones_Poligonos.zip")
