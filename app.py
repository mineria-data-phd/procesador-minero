import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def limpiar_dato(texto, tipo="general"):
    if not texto: return "No detectado"
    limpio = " ".join(texto.split()).strip()
    if tipo == "nombre":
        # Corta en puntos, comas o frases legales típicas para no traer párrafos
        limpio = re.split(r'[\.\"\”\“]|,?\s*POR TANTO', limpio)[0]
    return limpio.replace('"', '').strip()

def extraer_datos_mineros(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto_completo += texto_pagina + "\n"
    
    # 1. CVE y JUZGADO (Búsqueda más flexible)
    cve = re.search(r'CVE\s*(\d+)', texto_completo)
    juzg = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[\wÁÉÍÓÚÑ]+)', texto_completo, re.IGNORECASE)

    # 2. NOMBRE DE LA MINA
    nombre = re.search(r'(?:denominada|denominará|concesión)\s+[\"“]?([\w\s\dÁÉÍÓÚÑ]+)', texto_completo, re.IGNORECASE)
    if not nombre:
        nombre = re.search(r'PEDIMENTO MINERO\s+([\w\s\dÁÉÍÓÚÑ]+)', texto_completo)

    # 3. SOLICITANTE (Busca nombres largos antes del RUT o cerca de S.J.L.)
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{15,60})\s*,?\s*(?:cédula|R\.U\.T|RUT)', texto_completo)
    if not solic:
        solic = re.search(r'S\.J\.L\.\s+([A-ZÁÉÍÓÚÑ\s]{15,60})', texto_completo)

    # 4. ROL, FOJAS Y COMUNA
    rol = re.search(r'([A-Z]-\d+-\d{4})', texto_completo)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', texto_completo, re.IGNORECASE)
    if not fojas: 
        fojas = re.search(r'^(\d{1,4})\s+N°', texto_completo, re.MULTILINE)
    
    comu = re.search(r'comuna\s+de\s+([\wÁÉÍÓÚÑ]+)', texto_completo, re.IGNORECASE)

    # 5. COORDENADAS
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', texto_completo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', texto_completo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": limpiar_dato(nombre.group(1), "nombre") if nombre else "No detectado",
        "Solicitante": limpiar_dato(solic.group(1)) if solic else "No detectado",
        "Rol/Causa": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comu.group(1).capitalize() if comu else "No detectado",
        "Juzgado": limpiar_dato(juzg.group(1)) if juzg else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = [extraer_datos_mineros(file) for file in uploaded_files]
    df = pd.DataFrame(resultados)
    
    cols = ["Archivo", "CVE", "Nombre Mina", "Solicitante", "Rol/Causa", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)"]
    df = df[cols]
    
    st.table(df)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Reporte_Mineria_Final.xlsx")
