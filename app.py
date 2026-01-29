import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def limpiar_profundo(texto, es_mina=False):
    if not texto: return "No detectado"
    # Eliminar ruidos comunes de PDF
    limpio = re.sub(r'\s+', ' ', texto).strip()
    if es_mina:
        # Cortar en palabras que indican que se acabó el nombre
        limpio = re.split(r'(?i)[\.\"\”\“]|,?\s*POR TANTO|,?\s*en mérito|,?\s*causa', limpio)[0]
    return limpio.replace('"', '').strip()

def extraer_datos_mineros(pdf_file):
    texto_completo = ""
    primera_pagina = ""
    with pdfplumber.open(pdf_file) as pdf:
        for i, pagina in enumerate(pdf.pages):
            p_txt = pagina.extract_text()
            if p_txt:
                texto_completo += p_txt + "\n"
                if i == 0: primera_pagina = p_txt

    # --- ESTRATEGIA PARA RECTIFICACIONES (6641, 6645) ---
    # El nombre suele estar entre comillas o después de "causa"
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s]+)[\"”]', texto_completo)
    
    # El solicitante suele ser lo primero que aparece en mayúsculas tras "S.J.L."
    solic = re.search(r'S\.J\.L\.\s*,\s*([A-ZÁÉÍÓÚÑ\s]{10,60})', texto_completo)
    if not solic:
        solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{15,60})\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado)', texto_completo)

    # --- JUZGADO Y CVE ---
    cve = re.search(r'CVE\s*(\d+)', texto_completo)
    # Buscamos el juzgado incluso si está cortado en varias líneas
    juzg = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z]+)', texto_completo, re.IGNORECASE)

    # --- ROL, FOJAS Y COMUNA ---
    rol = re.search(r'([A-Z]-\d+-\d{4})', texto_completo)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', texto_completo, re.IGNORECASE)
    if not fojas: 
        fojas = re.search(r'^(\d{1,4})\s+N°', texto_completo, re.MULTILINE)
    
    comu = re.search(r'comuna\s+de\s+([\wÁÉÍÓÚÑ]+)', texto_completo, re.IGNORECASE)

    # --- COORDENADAS ---
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', texto_completo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', texto_completo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": limpiar_profundo(nombre.group(1), True) if nombre else "No detectado",
        "Solicitante": limpiar_profundo(solic.group(1)) if solic else "No detectado",
        "Rol/Causa": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comu.group(1).capitalize() if comu else "No detectado",
        "Juzgado": limpiar_profundo(juzg.group(1)) if juzg else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = [extraer_datos_mineros(file) for file in uploaded_files]
    df = pd.DataFrame(resultados)
    cols = ["Archivo", "CVE", "Nombre Mina", "Solicitante", "Rol/Causa", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)"]
    st.table(df[cols])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Reporte_Mineria_Final.xlsx")
