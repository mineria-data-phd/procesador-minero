import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def extraer_datos_mineros(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
    
    # --- 1. DATOS DE CABECERA (CVE y JUZGADO) ---
    cve = re.search(r'CVE\s+(\d+)', texto_completo)
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[A-Za-z]+)', texto_completo, re.IGNORECASE)

    # --- 2. NOMBRE DE LA MINA Y SOLICITANTE ---
    # Buscamos el nombre entre comillas o después de "denominará"
    nombre_mina = re.search(r'denominará\s+"?([^"]+)"?', texto_completo, re.IGNORECASE)
    if not nombre_mina: # Caso Pedimento 6688
        nombre_mina = re.search(r'PEDIMENTO MINERO\s*\n\s*(.*)', texto_completo)
    
    solicitante = re.search(r'SOLICITANTE:\s*([A-Z\s]+R\.U\.T\.[^\s]+)', texto_completo)
    if not solicitante:
        solicitante = re.search(r'S\.J\.L\.\s+([A-Z\s]+),', texto_completo)

    # --- 3. DATOS LEGALES (ROL, FOJAS, COMUNA) ---
    rol = re.search(r'[A-Z]-\d+-\d{4}', texto_completo)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', texto_completo, re.IGNORECASE)
    if not fojas: fojas = re.search(r'^(\d{1,4})\s+N°', texto_completo, re.MULTILINE)
    
    comuna = re.search(r'Comuna de\s+([A-Za-z]+)', texto_completo, re.IGNORECASE)

    # --- 4. COORDENADAS ---
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', texto_completo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', texto_completo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": nombre_mina.group(1).replace('"', '').strip() if nombre_mina else "No detectado",
        "Solicitante": solicitante.group(1).strip() if solicitante else "No detectado",
        "Rol/Causa": rol.group(0) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna.group(1) if comuna else "No detectado",
        "Juzgado": juzgado.group(1) if juzgado else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = [extraer_datos_mineros(file) for file in uploaded_files]
    df = pd.DataFrame(resultados)
    st.table(df)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Reporte_Mineria_Fichas.xlsx")
