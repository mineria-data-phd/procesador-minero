import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import box
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro - Polígonos X/Y", layout="wide")
st.title("⚒️ Extractor de Expedientes y Generador de Polígonos")

def identificar_tramite(texto):
    t = texto.lower()
    if "rectificación" in t or "rectificacion" in t: return "Solicitud de Rectificación"
    if "mensura" in t: return "Solicitud de Mensura"
    if "pedimento" in t or "manifestación" in t or "manifestacion" in t: return "Manifestación y Pedimento"
    return "Extracto Minero"

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

    solicitante = "No detectado"
    solic_match = re.search(r'(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo, re.IGNORECASE)
    if solic_match: solicitante = solic_match.group(1).strip()
    else:
        empresa = re.search(r'(FQAM\s+EXPLORATION\s+\(CHILE\)\s+S\.A\.)', cuerpo)
        if empresa: solicitante = empresa.group(1).strip()

    # --- COORDENADAS (X primero, luego Y) ---
    # Buscamos primero el Este (X) y luego el Norte (Y) según tu aclaración
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    coord_x = limpiar_coord(e_m.group(1)) if e_m else None
    coord_y = limpiar_coord(n_m.group(1)) if n_m else None
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)

    return {
        "Archivo": pdf_file.name,
        "Tipo": identificar_tramite(cuerpo),
        "Nombre": nombre,
        "Solicitante": solicitante,
        "Rol": rol.group(1) if rol else "No detectado",
        "Juzgado": juzgado,
        "Este_X": coord_x,
        "Norte_Y": coord_y
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    results = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(results)
    st.dataframe(df)

    # Excel
    output_excel = BytesIO()
    with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel", output_excel.getvalue(), "Datos_Mineros.xlsx")

    # Polígonos SHP
    df_geo = df.dropna(subset=['Este_X', 'Norte_Y']).copy()
    
    if not df_geo.empty:
        poligonos = []
        for _, row in df_geo.iterrows():
            # Construcción: 3000m en X (Este-Oeste), 1000m en Y (Norte-Sur)
            # Centrado en la coordenada capturada
            x_min, x_max = row.Este_X - 1500, row.Este_X + 1500
            y_min, y_max = row.Norte_Y - 500, row.Norte_Y + 500
            poligonos.append(box(x_min, y_min, x_max, y_max))
        
        gdf = gpd.GeoDataFrame(df_geo, geometry=poligonos, crs="EPSG:32719")
        
        temp_dir = "temp_shp"
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)
        base_name = "Concesiones_Poligonos"
        gdf.to_file(os.path.join(temp_dir, f"{base_name}.shp"))

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(os.path.join(temp_dir, f"{base_name}{ext}"), arcname=f"{base_name}{ext}")
        
        st.download_button("🌍 Descargar Polígonos SHP (ZIP)", zip_buffer.getvalue(), "Concesiones_Poligonos.zip")
