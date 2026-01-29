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
    
    # --- IDENTIFICAR TIPO ---
    tipo = "Pedimento/Concesión"
    if "rectificación" in texto_completo.lower() or "rectificacion" in texto_completo.lower():
        tipo = "Solicitud de Rectificación"

    # --- EXTRAER FOJAS (Ajustado para 6645 y 6688) ---
    # Busca "fojas 3.247" o el número al inicio "936 N° 506"
    fojas_match = re.search(r'fojas\s+([\d\.]+)', texto_completo, re.IGNORECASE)
    if not fojas_match:
        fojas_match = re.search(r'Fs\.\s*([\d\.]+)', texto_completo, re.IGNORECASE)
    if not fojas_match:
        fojas_match = re.search(r'^(\d{1,4})\s+N°', texto_completo, re.MULTILINE)
    
    fojas = fojas_match.group(1) if fojas_match else "No detectado"

    # --- EXTRAER ROL ---
    rol_match = re.search(r'[A-Z]-\d+-\d{4}', texto_completo)
    rol = rol_match.group(0) if rol_match else "No detectado"

    # --- EXTRAER COORDENADAS (Norte 7 dígitos, Este 6 dígitos) ---
    norte_match = re.search(r'Norte[:\s]*([\d\.]{7,10})', texto_completo, re.IGNORECASE)
    este_match = re.search(r'Este[:\s]*([\d\.]{6,9})', texto_completo, re.IGNORECASE)
    
    norte = norte_match.group(1).replace(".", "") if norte_match else "Ver PDF"
    este = este_match.group(1).replace(".", "") if este_match else "Ver PDF"

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Rol": rol,
        "Fojas": fojas,
        "Norte (Y)": norte,
        "Este (X)": este
    }

uploaded_files = st.file_uploader("Arrastra tus PDFs aquí", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = []
    for file in uploaded_files:
        datos = extraer_datos_mineros(file)
        resultados.append(datos)
    
    df = pd.DataFrame(resultados)
    st.success("¡Análisis completado!")
    st.table(df) # Tabla visual amigable

    # Botón para descargar el Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos_Mineros')
    st.download_button("📥 Descargar Tabla en Excel", output.getvalue(), "Reporte_Mineria.xlsx")
