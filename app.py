import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Extractor de Fichas Mineras", layout="wide")
st.title("⚒️ Extractor de Expedientes para Fichas y ArcMap")

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- Diccionario de búsqueda con lógica de las imágenes proporcionadas ---
    
    # 1. Identificación básica
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    juzgado = re.search(r'(?i)(?:Letras|Juzgado)[:\s]+([\w\sº\.]+?)(?=\s*,|\s+de\s+\d)', cuerpo)
    comuna = re.search(r'(?i)comuna\s+de\s+([\w\s]+?)(?=\s*,|\s+provincia)', cuerpo)
    
    # 2. Solicitante y Conservador
    solicitante = re.search(r'(?i)(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo)
    conservador = re.search(r'(?i)Conservador\s+de\s+Bienes\s+Raíces\s+de\s+([\w\s]+)', cuerpo)

    # 3. Fechas (Presentación, Publicación, Sentencia)
    fechas = re.findall(r'(\d{1,2}\s+de\s+[a-zñ]+\s+de\s+\d{4})', cuerpo.lower())
    
    # 4. Coordenadas UTM (Punto Medio para el cálculo)
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None

    # --- Construcción del registro ---
    nombre_raw = nombre.group(1).strip() if nombre else "Sin Nombre"
    nombre_id = re.sub(r'[^a-zA-Z0-9]', '_', nombre_raw)[:20]

    v = {}
    poly = None
    if x_c and y_c:
        v['V1_X'], v['V1_Y'] = round(x_c - 1500), round(y_c + 500)
        v['V2_X'], v['V2_Y'] = round(x_c + 1500), round(y_c + 500)
        v['V3_X'], v['V3_Y'] = round(x_c + 1500), round(y_c - 500)
        v['V4_X'], v['V4_Y'] = round(x_c - 1500), round(y_c - 500)
        poly = Polygon([(v['V1_X'], v['V1_Y']), (v['V2_X'], v['V2_Y']), (v['V3_X'], v['V3_Y']), (v['V4_X'], v['V4_Y']), (v['V1_X'], v['V1_Y'])])

    row = {
        "Nombre_ID": nombre_id,
        "Nombre": nombre_raw,
        "Rol": rol.group(1) if rol else "S/R",
        "Juzgado": juzgado.group(1).strip() if juzgado else "No detectado",
        "Comuna": comuna.group(1).strip() if comuna else "No detectada",
        "Solicitante": solicitante.group(1).strip() if solicitante else "No detectado",
        "Conservador": conservador.group(1).strip() if conservador else "No detectado",
        "Fecha_1": fechas[0] if len(fechas) > 0 else "",
        "Fecha_2": fechas[1] if len(fechas) > 1 else "",
        "Hectareas": 300,
        "Este_Medio": x_c,
        "Norte_Medio": y_c,
        **v
    }
    return row, poly

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    shapes = {}
    
    for f in uploaded_files:
        info, poly = extraer_datos_mineros(f)
        all_data.append(info)
        if poly: shapes[info['Nombre_ID']] = (poly, info)

    df = pd.DataFrame(all_data)
    st.write("### Datos Extraídos para Fichas")
    st.dataframe(df)

    # 1. EXCEL GLOBAL (Todos los campos de las imágenes)
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel para Fichas", out_ex.getvalue(), "Fichas_Mineras.xlsx")

    # 2. ZIP DE SHAPEFILES INDIVIDUALES
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zf:
        temp = "temp_shp"
        if not os.path.exists(temp): os.makedirs(temp)
        for nid, (p, data) in shapes.items():
            gdf = gpd.GeoDataFrame([data], geometry=[p], crs="EPSG:32719")
            # Limpiar columnas para que no rompa el DBF de ArcMap
            gdf_clean = gdf[['Nombre', 'Rol', 'Juzgado', 'geometry']]
            path = os.path.join(temp, nid)
            gdf_clean.to_file(f"{path}.shp", driver='ESRI Shapefile')
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(f"{path}{ext}", arcname=f"{nid}/{nid}{ext}")

    st.download_button("🌍 Descargar SHPs Individuales (ZIP)", zip_buf.getvalue(), "Planos_ArcMap.zip")
