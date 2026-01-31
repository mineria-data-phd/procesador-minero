import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import box
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro - Vértices", layout="wide")
st.title("⚒️ Extractor de Expedientes con Cálculo de Vértices")

# ... [Funciones de identificación y limpieza se mantienen iguales] ...

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- Lógica de Extracción de Texto ---
    # Juzgado, Nombre y Solicitante (Mantenemos tu lógica ganadora)
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

    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "No detectado"
    if nombre == "No detectado":
        especifico = re.search(r'\b([A-Z]{3,}\s\d+\-[A-Z])\b', cuerpo)
        nombre = especifico.group(1).strip() if especifico else "No detectado"

    solic_match = re.search(r'(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo, re.IGNORECASE)
    solicitante = solic_match.group(1).strip() if solic_match else "No detectado"

    # --- Coordenadas Base (Punto Central) ---
    e_m = re.search(r'(?i)Este[:\s]*([\d\.\,]{6,11})', cuerpo)
    n_m = re.search(r'(?i)Norte[:\s]*([\d\.\,]{7,12})', cuerpo)
    
    def limpiar_coord(coord):
        if not coord: return None
        limpia = re.sub(r'[\.\,\s]', '', coord)
        return float(limpia) if limpia.isdigit() else None

    x_centro = limpiar_coord(e_m.group(1)) if e_m else None
    y_centro = limpiar_coord(n_m.group(1)) if n_m else None
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)

    # --- Cálculo de los 4 Vértices (Rectángulo 3000x1000) ---
    vertices = {}
    if x_centro and y_centro:
        # Vértice 1: Noroeste
        vertices['V1_X'] = x_centro - 1500; vertices['V1_Y'] = y_centro + 500
        # Vértice 2: Noreste
        vertices['V2_X'] = x_centro + 1500; vertices['V2_Y'] = y_centro + 500
        # Vértice 3: Sureste
        vertices['V3_X'] = x_centro + 1500; vertices['V3_Y'] = y_centro - 500
        # Vértice 4: Suroeste
        vertices['V4_X'] = x_centro - 1500; vertices['V4_Y'] = y_centro - 500
    else:
        for i in range(1, 5): vertices[f'V{i}_X'] = "N/A"; vertices[f'V{i}_Y'] = "N/A"

    data = {
        "Archivo": pdf_file.name,
        "Tipo": identificar_tramite(cuerpo),
        "Nombre": nombre,
        "Solicitante": solicitante,
        "Rol": rol.group(1) if rol else "No detectado",
        "Juzgado": juzgado,
        "Centro_X": x_centro,
        "Centro_Y": y_centro
    }
    data.update(vertices) # Agregamos los vértices al diccionario
    return data

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    results = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(results)
    st.dataframe(df)

    # Descarga Excel
    output_excel = BytesIO()
    with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel con Vértices", output_excel.getvalue(), "Mineria_Vertices.xlsx")

    # [Lógica de generación de SHP se mantiene igual usando box(x_centro-1500, y_centro-500, x_centro+1500, y_centro+500)]
