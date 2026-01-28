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
    tipo = "Concesión/Pedimento"
    if "rectificación" in texto_completo.lower():
        tipo = "Solicitud de Rectificación"

    # --- EXTRAER FOJAS (Nuevo método más flexible) ---
    # Busca patrones como "fojas 3.247" o "Fs. 936" o "936 N° 506"
    fojas_match = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', texto_completo, re.IGNORECASE)
    if not fojas_match:
        fojas_match = re.search(r'^(\d{1,4})\s*N°\s*\d+', texto_completo, re.MULTILINE)
    fojas = fojas_match.group(1) if fojas_match else "No detectado"

    # --- EXTRAER ROL ---
    rol_match = re.search(r'[A-Z]-\d+-\d{4}', texto_completo)
    rol = rol_match.group(0) if rol_match else "No detectado"

    # --- EXTRAER COORDENADAS (Formatos con y sin puntos) ---
    # Busca números de 7 dígitos para Norte y 6 para Este, ignorando puntos intermedios
    norte_match = re.search(r'Norte[:\s]*([\d\.]{7,10})', texto_completo, re.IGNORECASE)
    este_match = re.search(r'Este[:\s]*([\d\.]{6,9})', texto_completo, re.IGNORECASE)
    
    norte = norte_match.group(1).replace(".", "") if norte_match else "Revisar PDF"
    este = este_match.group(1).replace(".", "") if este_match else "Revisar PDF"

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Rol": rol,
        "Fojas": fojas,
        "Norte (Y)": norte,
        "Este (X)": este
    }

uploaded_files = st.file_uploader("Sube tus PDFs aquí", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = []
    for file in uploaded_files:
        datos = extraer_datos_mineros(file)
        resultados.append(datos)
    
    df = pd.DataFrame(resultados)
    st.success("¡Análisis finalizado!")
    st.table(df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Mineria')
    
    st.download_button("📥 Descargar Excel", output.getvalue(), "data_minera.xlsx")
