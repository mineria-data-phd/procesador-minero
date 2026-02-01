import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Extractor Minero ArcMap Pro", layout="wide")
st.title("⚒️ Generador de Polígonos SHP para ArcMap 10.8")

def identificar_tramite(texto):
    t = texto.lower()
    if "rectificación" in t or "rectificacion" in t: return "Solicitud de Rectificación"
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

    # --- Extracción de Punto Medio ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None

    # --- Cálculo de los 4 Vértices (3000m x 1000m) ---
    v = {}
    if x_c and y_c:
        # Definimos los vértices en sentido HORARIO para ArcMap
        v['V1_X'], v['V1_Y'] = x_c - 1500, y_c + 500  # NW
        v['V2_X'], v['V2_Y'] = x_c + 1500, y_c + 500  # NE
        v['V3_X'], v['V3_Y'] = x_c + 1500, y_c - 500  # SE
        v['V4_X'], v['V4_Y'] = x_c - 1500, y_c - 500  # SW
    else:
        for i in range(1, 5): v[f'V{i}_X'] = v[f'V{i}_Y'] = None

    # --- Metadatos ---
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    solic_match = re.search(r'(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo, re.IGNORECASE)
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)

    res = {
        "Archivo": pdf_file.name,
        "Nombre": nombre_m.group(1).strip() if nombre_m else "No detectado",
        "Solicitante": solic_match.group(1).strip() if solic_match else "No detectado",
        "Rol": rol.group(1) if rol else "No detectado",
        "Tipo": identificar_tramite(cuerpo),
        "Has": 300
    }
    res.update(v)
    return res

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    st.dataframe(df)

    # 1. EXCEL (Con vértices visibles)
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Tabla Excel", out_ex.getvalue(), "Datos_Mineros.xlsx")

    # 2. SHAPEFILE (Polígonos Geométricamente Válidos)
    df_geo = df.dropna(subset=['V1_X', 'V1_Y']).copy()
    if not df_geo.empty:
        geometrias = []
        for _, r in df_geo.iterrows():
            # Creamos el polígono uniendo V1->V2->V3->V4 y CERRANDO en V1
            # El orden es V1(NW), V2(NE), V3(SE), V4(SW)
            puntos = [
                (r.V1_X, r.V1_Y),
                (r.V2_X, r.V2_Y),
                (r.V3_X, r.V3_Y),
                (r.V4_X, r.V4_Y),
                (r.V1_X, r.V1_Y) # Cierre
            ]
            geometrias.append(Polygon(puntos))
        
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometrias, crs="EPSG:32719")
        
        # Limpieza de tabla de atributos para el SHP
        gdf = gdf.drop(columns=['V1_X', 'V1_Y', 'V2_X', 'V2_Y', 'V3_X', 'V3_Y', 'V4_X', 'V4_Y'])
        
        temp = "temp_shp"
        if not os.path.exists(temp): os.makedirs(temp)
        
        # Forzamos nombres de archivo simples
        base_path = os.path.join(temp, "Concesion")
        gdf.to_file(f"{base_path}.shp")

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            for ex in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(f"{base_path}{ex}", arcname=f"Concesion{ex}")
        
        st.download_button("🌍 Descargar SHP Polígonos (Corregido)", zip_buf.getvalue(), "Concesion_ArcMap.zip")
