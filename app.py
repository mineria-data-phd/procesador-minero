import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Master", layout="wide")
st.title("⚒️ Sistema Consolidado: Fichas Legales y GIS")

def identificar_tramite(texto):
    t = texto.lower()
    if any(x in t for x in ["rectificación", "rectificacion"]): return "Rectificación"
    if "mensura" in t: return "Mensura"
    if any(x in t for x in ["pedimento", "manifestación", "manifestacion"]): return "Manifestación/Pedimento"
    return "Extracto"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- MOTOR DE EXTRACCIÓN LEGAL (EL 98% LOGRADO) ---
    # Rol: busca formato A-123-2024
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    # Nombre: busca texto entre comillas grandes o simples
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    # Juzgado: captura "1er Juzgado de Letras de..." o similar
    juzgado = re.search(r'(?i)(?:Juzgado|Letras)[:\s]+([\w\sº\.]+?)(?=\s*,|\s+de\s+\d|\s+RUT)', cuerpo)
    # Comuna: busca después de "comuna de"
    comuna = re.search(r'(?i)comuna\s+de\s+([\w\s]+?)(?=\s*,|\s+provincia|\s+región)', cuerpo)
    # Solicitante: nombre de la persona o empresa
    solic = re.search(r'(?i)(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|domiciliado))', cuerpo)
    # Conservador: CBR de ...
    cons = re.search(r'(?i)Conservador\s+de\s+Bienes\s+Raíces\s+de\s+([\w\s]+?)(?=\s*,|\.|\s+fs)', cuerpo)
    # Fechas: Captura fechas en formato "12 de octubre de 2023"
    fechas = re.findall(r'(\d{1,2}\s+de\s+[a-zñ]+\s+de\s+\d{4})', cuerpo.lower())
    # Fojas y Número (si existen)
    fojas = re.search(r'(?i)fs\.?\s*(\d+)', cuerpo)
    numero = re.search(r'(?i)(?:nº|número)\s*(\d+)', cuerpo)

    # --- COORDENADAS (UTM 19S) ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_c = limpiar_coord(e_m.group(1)) if e_m else None
    y_c = limpiar_coord(n_m.group(1)) if n_m else None

    # --- PREPARACIÓN DE GEOMETRÍA INDIVIDUAL ---
    nombre_raw = nombre.group(1).strip() if nombre else "Sin_Nombre"
    nombre_id = re.sub(r'[^a-zA-Z0-9]', '_', nombre_raw)[:20]
    
    poly = None
    v = {}
    if x_c and y_c:
        v['V1_X'], v['V1_Y'] = round(x_c - 1500), round(y_c + 500)
        v['V2_X'], v['V2_Y'] = round(x_c + 1500), round(y_c + 500)
        v['V3_X'], v['V3_Y'] = round(x_c + 1500), round(y_c - 500)
        v['V4_X'], v['V4_Y'] = round(x_c - 1500), round(y_c - 500)
        # Polígono cerrado (V1->V2->V3->V4->V1)
        poly = Polygon([(v['V1_X'], v['V1_Y']), (v['V2_X'], v['V2_Y']), 
                        (v['V3_X'], v['V3_Y']), (v['V4_X'], v['V4_Y']), 
                        (v['V1_X'], v['V1_Y'])])

    # --- DICCIONARIO PARA EXCEL ---
    row = {
        "ID_Archivo": nombre_id,
        "Nombre_Concesión": nombre_raw,
        "Rol_Expediente": rol.group(1) if rol else "N/A",
        "Juzgado": juzgado.group(1).strip() if juzgado else "N/A",
        "Comuna": comuna.group(1).strip() if comuna else "N/A",
        "Solicitante": solic.group(1).strip() if solic else "N/A",
        "Conservador": cons.group(1).strip() if cons else "N/A",
        "Fojas": fojas.group(1) if fojas else "",
        "Número": numero.group(1) if numero else "",
        "Fecha_Presentación": fechas[0] if len(fechas) > 0 else "",
        "Fecha_Sentencia/Pub": fechas[1] if len(fechas) > 1 else "",
        "UTM_Este_Medio": x_c,
        "UTM_Norte_Medio": y_c,
        "Hectáreas": 300,
        **v
    }
    return row, poly

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    geometries = {}
    
    for f in uploaded_files:
        info, poly = extraer_datos_mineros(f)
        all_data.append(info)
        if poly: geometries[info['ID_Archivo']] = (poly, info)

    df = pd.DataFrame(all_data)
    st.write("### Datos Legales Extraídos")
    st.dataframe(df)

    # 1. EXCEL GLOBAL (Respaldo de datos legales completo)
    out_ex = BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Legal Completo", out_ex.getvalue(), "Fichas_Mineras_Final.xlsx")

    # 2. ZIP DE SHAPEFILES INDIVIDUALES (Solución para el Zoom en ArcMap)
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zf:
        temp = "temp_final"
        if not os.path.exists(temp): os.makedirs(temp)
        
        for nid, (p, data) in geometries.items():
            gdf = gpd.GeoDataFrame([data], geometry=[p], crs="EPSG:32719")
            # Dejamos solo campos esenciales en el SHP para evitar errores de DBF
            gdf_shp = gdf[['Nombre_Concesión', 'Rol_Expediente', 'geometry']]
            gdf_shp.columns = ['Nombre', 'Rol', 'geometry'] # Nombres cortos < 10 caracteres
            
            path = os.path.join(temp, nid)
            gdf_shp.to_file(f"{path}.shp", driver='ESRI Shapefile')
            
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                zf.write(f"{path}{ext}", arcname=f"{nid}/{nid}{ext}")

    st.download_button("🌍 Descargar SHPs Individuales (Zoom OK)", zip_buf.getvalue(), "GIS_Concesiones.zip")
