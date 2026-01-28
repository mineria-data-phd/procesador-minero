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
    
    # --- LÓGICA DE EXTRACCIÓN MEJORADA ---
    # 1. Identificar si es Rectificación o Concesión
    tipo = "Concesión Minera"
    if "rectificación" in texto_completo.lower() or "rectificacion" in texto_completo.lower():
        tipo = "Solicitud de Rectificación"
    
    # 2. Extraer Rol (Ej: V-1006-2022)
    rol_match = re.search(r'[A-Z]-\d+-\d{4}', texto_completo)
    rol = rol_match.group(0) if rol_match else "No detectado"
    
    # 3. Extraer Fojas
    fojas_match = re.search(r'Fojas\s*[:\s]*(\d+\.?\d*)', texto_completo, re.IGNORECASE)
    fojas = fojas_match.group(1) if fojas_match else "No detectado"
    
    # 4. Extraer Coordenadas (Buscamos números de 6 o 7 dígitos específicos)
    norte_match = re.search(r'Norte[:\s]*(\d{7})', texto_completo, re.IGNORECASE)
    este_match = re.search(r'Este[:\s]*(\d{6})', texto_completo, re.IGNORECASE)
    
    norte = norte_match.group(1) if norte_match else "Revisar PDF"
    este = este_match.group(1) if este_match else "Revisar PDF"

    return {
        "Archivo": pdf_file.name,
        "Tipo de Trámite": tipo,
        "Rol/Causa": rol,
        "Fojas": fojas,
        "Coordenada Norte (Y)": norte,
        "Coordenada Este (X)": este
    }

uploaded_files = st.file_uploader("Sube tus PDFs aquí", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = []
    for file in uploaded_files:
        datos = extraer_datos_mineros(file)
        resultados.append(datos)
    
    df = pd.DataFrame(resultados)
    st.success("¡Procesamiento completado!")
    st.subheader("Vista previa de los datos extraídos:")
    st.table(df)

    # Preparar descarga de Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos_Mineros')
    
    st.download_button(
        label="📥 Descargar todo en Excel",
        data=output.getvalue(),
        file_name="datos_expedientes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
