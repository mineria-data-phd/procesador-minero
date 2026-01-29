import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def identificar_tramite(texto):
    t = texto.lower()
    if "rectificación" in t or "rectificacion" in t:
        return "Solicitud de Rectificación"
    if "testificación" in t or "testificacion" in t:
        return "Solicitud de Testificación"
    if "mensura" in t:
        return "Solicitud de Mensura"
    if "pedimento" in t or "manifestación" in t or "manifestacion" in t:
        return "Manifestación y Pedimento"
    return "Extracto EM y EP"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "

    # Limpieza para búsqueda lineal
    cuerpo = " ".join(texto_sucio.split()).strip()

    # 1. TIPO DE TRÁMITE
    tipo = identificar_tramite(cuerpo)

    # 2. JUZGADO (Regla mejorada para Copiapó y otros)
    # Busca patrones como "1° Juzgado de Letras de XXXXX"
    juzgado_match = re.search(r'(\d+°?\s*Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z]+)', cuerpo, re.IGNORECASE)
    juzgado = juzgado_match.group(0).strip() if juzgado_match else "No detectado"

    # 3. NOMBRE DE LA MINA
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    
    # 4. SOLICITANTE (Antes del RUT)
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,65})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|domiciliado))', cuerpo)

    # 5. ROL / CAUSA
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    
    # 6. FOJAS
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo, re.IGNORECASE)
    if not fojas:
        fojas = re.search(r'(\d{1,3}\.?\d{0,3})\s+N°', cuerpo)

    # 7. COMUNA (Nombres compuestos)
    comuna_match = re.search(r'(?i)comuna\s+de\s+([A-ZÁÉÍÓÚÑa-z\s]{3,25})(?=\s*[\.\,]| R\.U\.T| fojas| fjs| juzgado)', cuerpo)
    comuna = comuna_match.group(1).strip() if comuna_match else "No detectado"

    # 8. COORDENADAS Y CVE
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', cuerpo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', cuerpo, re.IGNORECASE)
    cve = re.search(r'CVE\s*[:\s]*(\d+)', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Nombre Mina": nombre.group(1).strip() if nombre else "No detectado",
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
