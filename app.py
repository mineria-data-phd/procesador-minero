import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor: Excel Global y SHP Individuales para ArcMap")

def identificar_tramite(texto):
    t = texto.lower()
    if any(x in t for x in ["rectificación", "rectificacion"]): return "Rectificacion"
    if "mensura" in t: return "Mensura"
    if any(x in t for x in ["pedimento", "manifestación", "manifestacion"]): return "Pedimento"
    return "Extracto"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- Coordenadas Punto Medio ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None

    # --- Vértices para Excel ---
    v = {}
    poligono = None
    if x_c and y_c:
        v['V1_X'], v['V1_Y'] = round(x_c - 1500), round(y_c + 500)
        v['V2_X'], v['V2_Y'] = round(x_c + 1500), round(y_c + 500)
        v['V3_X'], v['V3_Y'] = round(x_c + 1500), round(y_c - 500)
        v['V4_X'], v['V4_Y'] = round(x_c - 1500), round(y_c - 500)
        # Crear polígono para el SHP
        poligono = Polygon([(v['V1_X'], v['V1_Y']), (v['V2_X'], v['V2_Y']), 
                            (v['V3_X'], v['V3_Y']), (v['V4_X'], v['V4_Y']), 
                            (v['V1_X'], v['V1_Y'])])
    else:
        for i in range(1, 5): v[f'V{i}_X'] = v[f'V{i}_Y'] = None

    # --- Metadatos ---
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre_raw = nombre_m.group(1).strip() if nombre_m else "Sin_Nombre"
    nombre_archivo = re.sub(r'[^a-zA-Z0-9]', '_', nombre_raw)[:20]
    
    rol_match = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    
    res = {
        "Nombre_ID": nombre_archivo,
        "Nombre": nombre_raw,
        "Rol": rol_match.group(1) if rol_match else "S/R",
        "Tipo": identificar_tramite(cuerpo),
        "Hectareas": 300
    }
    res.update(v)
    return res, poligono

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data_list = []
    geometrias = {}
    
    for f in uploaded_files:
        datos, poly = extraer_datos_mineros(f)
        data_list.append(datos)
        if poly:
            geometrias[datos['Nombre_ID']] = (poly, datos)

    df = pd.DataFrame(data_list)
    st.write("### Vista previa de datos")
    st.dataframe(df)

    # 1. GENERAR EXCEL GLOBAL
    output_excel = BytesIO()
    with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Global", output_excel.getvalue(), "Reporte_Completo.xlsx")

    # 2. GENERAR ZIP CON SHPs INDIVIDUALES
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        temp_dir = "temp_shp"
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)

        for nombre_id, (poly, info) in geometrias.items():
            # Crear GeoDataFrame individual
            gdf = gpd.GeoDataFrame([info], geometry=[poly], crs="EPSG:32719")
            # Limpiar para ArcMap (quitar columnas X/Y y Nombre_ID)
            gdf_clean = gdf.drop(columns=['Nombre_ID', 'V1_X', 'V1_Y', 'V2_X', 'V2_Y', 'V3_X', 'V3_Y', 'V4_X', 'V4_Y'])
            
            # Nombre de archivo único
            path_base = os.path.join(temp_dir, nombre_id)
            gdf_clean.to_file(f"{path_base}.shp", driver='ESRI Shapefile')

            # Agregar los 4 componentes al ZIP
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                if os.path.exists(f"{path_base}{ext}"):
                    zf.write(f"{path_base}{ext}", arcname=f"{nombre_id}/{nombre_id}{ext}")

    st.download_button("🌍 Descargar Shapefiles Individuales (ZIP)", zip_buffer.getvalue(), "Concesiones_ArcMap.zip")
