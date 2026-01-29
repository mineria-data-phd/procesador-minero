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
    
    # 1. TIPO Y ROL
    tipo = "Pedimento/Concesión"
    if "rectificación" in texto_completo.lower(): tipo = "Solicitud de Rectificación"
    rol = re.search(r'[A-Z]-\d+-\d{4}', texto_completo)
    
    # 2. NOMBRE DE LA MINA (Suele venir en mayúsculas después de 'denominará' o en el encabezado)
    nombre_mina = re.search(r'denominará\s+"([^"]+)"', texto_completo, re.IGNORECASE)
    if not nombre_mina: # Intento 2 para pedimentos
        nombre_mina = re.search(r'PEDIMENTO MINERO\s+(.*)', texto_completo)

    # 3. SOLICITANTE
    solicitante = re.search(r'SOLICITANTE:\s*([^\n\r]+)', texto_completo, re.IGNORECASE)
    
    # 4. COMUNA
    comuna = re.search(r'Comuna de\s+([A-Za-z]+)', texto_completo, re.IGNORECASE)
    
    # 5. JUZGADO
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[A-Za-z]+)', texto_completo, re.IGNORECASE)

    # 6. FOJAS Y COORDENADAS (Lo que ya teníamos)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', texto_completo, re.IGNORECASE)
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', texto_completo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', texto_completo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Nombre Mina": nombre_mina.group(1).strip() if nombre_mina else "No detectado",
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
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Reporte_Mineria_Pro.xlsx")
