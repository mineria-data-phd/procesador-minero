import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def limpiar_profundo(t, tipo="general"):
    if not t: return "No detectado"
    # Quita saltos de línea y espacios múltiples
    t = " ".join(t.split()).strip()
    if tipo == "mina":
        # Corta el nombre si encuentra palabras legales o puntos
        t = re.split(r'(?i)[\.\"\”\“]|,?\s*POR TANTO|,?\s*en mérito|,?\s*causa', t)[0]
    return t.replace('"', '').strip()

def extraer_datos_mineros(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_completo += txt + " \n "

    # --- 1. CVE Y JUZGADO ---
    cve = re.search(r'CVE\s*(\d+)', texto_completo)
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[\wÁÉÍÓÚÑ]+)', texto_completo, re.IGNORECASE)

    # --- 2. NOMBRE DE LA MINA (Prioridad Comillas) ---
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]+)[\"”]', texto_completo)
    if not nombre:
        nombre = re.search(r'(?i)(?:denominada|denominará|pertenencia)\s+([\w\s\dÁÉÍÓÚÑ]+)', texto_completo)

    # --- 3. SOLICITANTE (Anclado al RUT) ---
    # Busca el bloque de mayúsculas antes de la palabra RUT o Cédula
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,100})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|domiciliado))', texto_completo)
    if not solic:
        # Intento 2: Lo que sigue después de S.J.L.
        solic = re.search(r'S\.J\.L\.\s*,\s*([A-ZÁÉÍÓÚÑ\s]{10,80})', texto_completo)

    # --- 4. ROL, FOJAS Y COMUNA ---
    rol = re.search(r'([A-Z]-\d+-\d{4})', texto_completo)
    fojas = re.search(r'(?i)(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', texto_completo)
    if not fojas:
        fojas = re.search(r'(\d{1,4})\s+N°\s+\d+', texto_completo)
    
    comuna = re.search(r'(?i)comuna\s+de\s+([\wÁÉÍÓÚÑ]+)', texto_completo)

    # --- 5. COORDENADAS ---
    norte = re.search(r'(?i)Norte[:\s]*([\d\.]{7,10})', texto_completo)
    este = re.search(r'(?i)Este[:\s]*([\d\.]{6,9})', texto_completo)

    return {
        "Archivo": pdf_file.name,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": limpiar_profundo(nombre.group(1), "mina") if nombre else "No detectado",
        "Solicitante": limpiar_profundo(solic.group(1)) if solic else "No detectado",
        "Rol/Causa": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna.group(1).capitalize() if comuna else "No detectado",
        "Juzgado": limpiar_profundo(juzgado.group(1)) if juzgado else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = [extraer_datos_mineros(file) for file in uploaded_files]
    df = pd.DataFrame(resultados)
    
    # Ordenar columnas
    cols = ["Archivo", "CVE", "Nombre Mina", "Solicitante", "Rol/Causa", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)"]
    st.table(df[cols])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Reporte_Mineria_V3.xlsx")
