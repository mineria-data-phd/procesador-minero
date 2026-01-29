import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def limpiar_texto_minero(texto, es_nombre=False):
    if not texto: return "No detectado"
    # Eliminar saltos de línea y limpiar espacios extra
    limpio = " ".join(texto.split()).strip()
    if es_nombre:
        # Si es el nombre de la mina, cortamos en puntos o palabras legales
        limpio = re.split(r'[\.\"\”\“]|,?\s*POR TANTO|,?\s*en mérito', limpio)[0]
    return limpio.replace('"', '').strip()

def extraer_datos_mineros(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto_temp = pagina.extract_text()
            if texto_temp: texto_completo += texto_temp + "\n"
    
    # 1. CVE y JUZGADO (Búsqueda por patrón de texto)
    cve = re.search(r'CVE\s*(\d+)', texto_completo)
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[\wÁÉÍÓÚÑ]+)', texto_completo, re.IGNORECASE)

    # 2. NOMBRE DE LA MINA (Busca lo que esté entre comillas, que es el estándar)
    nombre_mina = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s]+)[\"”]', texto_completo)
    if not nombre_mina:
        nombre_mina = re.search(r'(?:denominada|denominará|pertenencia)\s+([\w\s\dÁÉÍÓÚÑ]+)', texto_completo, re.IGNORECASE)

    # 3. SOLICITANTE (Busca el nombre largo en mayúsculas antes del RUT o abogado)
    solicitante = re.search(r'([A-ZÁÉÍÓÚÑ\s]{15,70})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|en representación))', texto_completo)
    if not solicitante:
        solicitante = re.search(r'S\.J\.L\.\s*,\s*([A-ZÁÉÍÓÚÑ\s]{15,70})', texto_completo)

    # 4. ROL, FOJAS Y COMUNA
    rol = re.search(r'([A-Z]-\d+-\d{4})', texto_completo)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', texto_completo, re.IGNORECASE)
    if not fojas: 
        fojas = re.search(r'^(\d{1,4})\s+N°', texto_completo, re.MULTILINE)
    
    comuna = re.search(r'comuna\s+de\s+([\wÁÉÍÓÚÑ]+)', texto_completo, re.IGNORECASE)

    # 5. COORDENADAS
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', texto_completo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', texto_completo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": limpiar_texto_minero(nombre_mina.group(1), True) if nombre_mina else "No detectado",
        "Solicitante": limpiar_texto_minero(solicitante.group(1)) if solicitante else "No detectado",
        "Rol/Causa": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna.group(1).capitalize() if comuna else "No detectado",
        "Juzgado": limpiar_texto_minero(juzgado.group(1)) if juzgado else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = [extraer_datos_mineros(file) for file in uploaded_files]
    df = pd.DataFrame(resultados)
    
    # Ordenar columnas igual que tus fichas manuales
    cols = ["Archivo", "CVE", "Nombre Mina", "Solicitante", "Rol/Causa", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)"]
    df = df[cols]
    
    st.table(df)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Reporte_Mineria_Final.xlsx")
