import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros (Versión Mejorada)")

def extraer_datos_mineros(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
    
    # Lógica de extracción mejorada con expresiones regulares (Regex)
    # Buscamos el Rol (ej: V-1006-2022)
    rol = re.search(r'[A-Z]-\d+-\d{4}', texto_completo)
    
    # Buscamos Fojas
    fojas = re.search(r'Fojas\s*[:\s]*(\d+\.?\d*)', texto_completo, re.IGNORECASE)
    
    # Buscamos Coordenadas (evitando confundir con años)
    norte = re.search(r'Norte[:\s]*(\d{7})', texto_completo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*(\d{6})', texto_completo, re.IGNORECASE)
    
    # Detectar Tipo de Solicitud
    tipo = "Concesión"
    if "rectificación" in texto_completo.lower():
        tipo = "Rectificación de Mensura"
    elif "mensura" in texto_completo.lower():
        tipo = "Solicitud de Mensura"

    return {
        "Archivo": pdf_file.name,
        "Tipo de Trámite": tipo,
        "Rol/Causa": rol.group(0) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Norte (Y)": norte.group(1) if norte else "Ver manual",
        "Este (X)": este.group(1) if este else "Ver manual"
    }

uploaded_files = st.file_uploader("Sube tus PDFs aquí", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = []
    for file in uploaded_files:
        datos = extraer_datos_mineros(file)
        resultados.append(datos)
    
    df = pd.DataFrame(resultados)
    st.subheader("Vista previa de los datos legales:")
    st.table(df)

    # Botón para Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos_Mineros')
    
    st.download_button(
        label="📥 Descargar Excel Corregido",
        data=output.getvalue(),
        file_name="expedientes_mineros_corregidos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    )
