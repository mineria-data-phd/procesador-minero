import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def limpiar_texto(txt):
    if not txt: return "No detectado"
    # Quita saltos de línea y espacios dobles
    return " ".join(txt.split()).strip()

def extraer_datos_mineros(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
    
    # 1. CVE (Código de Verificación)
    cve = re.search(r'CVE\s+([\d]+)', texto_completo)
    
    # 2. NOMBRE DE LA MINA (Busca entre comillas o después de 'denominada')
    nombre_mina = re.search(r'(?:denominada|denominará)\s+"([^"]+)"', texto_completo, re.IGNORECASE)
    if not nombre_mina:
        # Intento 2: Buscar después de PEDIMENTO MINERO
        nombre_mina = re.search(r'PEDIMENTO MINERO\s+([\w\s\d]+?)(?=\s+POR TANTO|A\.U\.S|S\.J\.L)', texto_completo)
    
    # 3. SOLICITANTE (Busca nombre antes del RUT)
    solicitante = re.search(r'([A-Z\sÁÉÍÓÚÑ]+?)\s*(?:,?\s*cedula|R\.U\.T|RUT)', texto_completo)
    
    # 4. JUZGADO Y COMUNA
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[\w]+)', texto_completo, re.IGNORECASE)
    comuna = re.search(r'comuna\s+de\s+([\w]+)', texto_completo, re.IGNORECASE)

    # 5. DATOS LEGALES (ROL Y FOJAS)
    rol = re.search(r'([A-Z]-\d+-\d{4})', texto_completo)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', texto_completo, re.IGNORECASE)
    if not fojas: fojas = re.search(r'^(\d{1,4})\s+N°', texto_completo, re.MULTILINE)

    # 6. COORDENADAS
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', texto_completo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', texto_completo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": limpiar_texto(nombre_mina.group(1)) if nombre_mina else "No detectado",
        "Solicitante": limpiar_texto(solicitante.group(1)) if solicitante else "No detectado",
        "Rol/Causa": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna.group(1).capitalize() if comuna else "No detectado",
        "Juzgado": limpiar_texto(juzgado.group(1)) if juzgado else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = [extraer_datos_mineros(file) for file in uploaded_files]
    df = pd.DataFrame(resultados)
    
    # Ordenar columnas para que coincidan con tus fichas
    columnas = ["Archivo", "CVE", "Nombre Mina", "Solicitante", "Rol/Causa", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)"]
    df = df[columnas]
    
    st.table(df)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Reporte_Mineria_Final.xlsx")
