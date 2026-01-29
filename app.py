import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def identificar_tramite(texto):
    t = texto.lower()
    if "rectificación" in t or "rectificacion" in t: return "Solicitud de Rectificación"
    if "testificación" in t or "testificacion" in t: return "Solicitud de Testificación"
    if "mensura" in t: return "Solicitud de Mensura"
    if "pedimento" in t or "manifestación" in t or "manifestacion" in t: return "Manifestación y Pedimento"
    return "Extracto EM y EP"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "

    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- 1. JUZGADO (Números y Palabras) ---
    # Busca: 1°, 1ero, Primer, Segundo, Tercer, etc.
    patron_juzgado = r'((?:\d+[°º\s]*|Primer|Segundo|Tercer|Cuarto)\s*Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z]+)'
    juz_match = re.search(patron_juzgado, cuerpo, re.IGNORECASE)
    juzgado = juz_match.group(0).strip() if juz_match else "No detectado"

    # --- 2. NOMBRE DE LA MINA (Mejorado para 6641) ---
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    if not nombre:
        # Busca después de palabras clave si no hay comillas
        nombre = re.search(r'(?i)(?:denominada|pertenencia|mina)\s+([A-ZÁÉÍÓÚÑ\d\s]{3,40})', cuerpo)

    # --- 3. SOLICITANTE (Búsqueda más amplia antes del RUT) ---
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,70})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|procurador|domiciliado))', cuerpo)

    # --- 4. ROL, FOJAS Y COMUNA ---
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    fojas = re.search(r'(?i)(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo)
    if not fojas:
        fojas = re.search(r'(\d{1,4}\.?\d{0,3})\s+N°', cuerpo)

    # Comuna (Las Condes, La Serena, etc)
    com_match = re.search(r'(?i)comuna\s+de\s+([A-ZÁÉÍÓÚÑa-z\s]{3,25})(?=\s*[\.\,]| R\.U\.T| fjs| juzgado)', cuerpo)
    comuna = com_match.group(1).strip() if com_match else "No detectado"

    # --- 5. COORDENADAS Y CVE ---
    tipo = identificar_tramite(cuerpo)
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', cuerpo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', cuerpo, re.IGNORECASE)
    cve = re.search(r'CVE\s*[:\s]*(\d+)', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Nombre Mina": nombre.group(1).strip() if nombre else (nombre.group(0).strip() if nombre else "No detectado"),
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "Rol": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna,
        "Juzgado": juzgado,
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF",
        "CVE": cve.group(1) if cve else "No detectado"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    cols = ["Archivo", "Tipo", "Nombre Mina", "Solicitante", "Rol", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)", "CVE"]
    st.dataframe(df[cols])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Reporte", output.getvalue(), "Base_Datos_Mineria.xlsx")
