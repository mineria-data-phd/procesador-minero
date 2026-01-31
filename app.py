import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Extractor Minero para ArcMap", layout="wide")
st.title("⚒️ Extractor de Expedientes: Generador de Polígonos para ArcMap")

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

    # --- EXTRACCIÓN DE IDENTIFICADORES ---
    # Juzgado
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

    # Nombre y Solicitante
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "No detectado"
    if nombre == "No detectado":
        especifico = re.search(r'\b([A-Z]{3,}\s\d+\-[A-Z])\b', cuerpo)
        nombre = especifico.group(1).strip() if especifico else "No detectado"

    solic_match = re.search(r'(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo, re.IGNORECASE)
    solicitante = solic_match.group(1).strip() if solic_match else "No detectado"

    # --- COORDENADAS (X, Y) ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)

    # --- CÁLCULO DE LOS 4 VÉRTICES (Rectángulo 3000m x 1000m) ---
    v = {}
    if x_c and y_c:
        # V1: NW, V2: NE, V3: SE, V4: SW
        v_coords = [
            (x_c - 1500, y_c + 500), # V1
            (x_c + 1500, y_c + 500), # V2
            (x_c + 1500, y_c - 500), # V3
            (x_c - 1500, y_c - 500)  # V4
        ]
        for i, (vx, vy) in enumerate(v_coords, 1):
            v[f'V{i}_X'] = vx
            v[f'V{i}_Y'] = vy
    else:
        for i in range(1, 5): 
            v[f'V{i}_X'] = v[f'V{i}_Y'] = None

    res = {
        "Archivo": pdf_file.name,
        "Nombre": nombre,
        "Solicitante": solicitante,
        "Rol": rol.group(1) if rol else "No detectado",
        "Juzgado": juzgado,
        "Tipo": identificar_tramite(cuerpo)
    }
    res.update(v)
    return res

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    st.dataframe(df)

    # Excel
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Tabla para ArcMap", out_ex.getvalue(), "Coordenadas_Vertices.xlsx")

    # Shapefile Polígono
    df_geo = df.dropna(subset=['V1_X', 'V1_Y']).copy()
    if not df_geo.empty:
        poligonos = []
        for _, r in df_geo.iterrows():
            # Crear polígono cerrado uniendo los 4 vértices
            p = Polygon([(r.V1_X, r.V1_Y), (r.V2_X, r.V2_Y), (r.V3_X, r.V3_Y), (r.V4_X, r.V4_Y)])
            poligonos.append(p)
        
        gdf = gpd.GeoDataFrame(df_geo, geometry=poligonos, crs="EPSG:32719")
        
        temp = "temp_shp"
        if not os.path.exists(temp): os.makedirs(temp)
        gdf.to_file(os.path.join(temp, "Concesiones_Rectangulos.shp"))

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            for ex in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(os.path.join(temp, f"Concesiones_Rectangulos{ex}"), arcname=f"Concesiones_Rectangulos{ex}")
        st.download_button("🌍 Descargar Shapefile (ZIP)", zip_buf.getvalue(), "Concesiones_SHP.zip")
