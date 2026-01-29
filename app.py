import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def limpiar_texto(t):
    if not t: return ""
    return " ".join(t.split()).strip()

def identificar_tramite(texto):
    t = texto.lower()
    if "mensura" in t and "solicitud" in t: return "Solicitud de Mensura"
    if "rectificación" in t or "rectificacion" in t: return "Solicitud de Rectificación"
    if "testificación" in t or "testificacion" in t: return "Solicitud de Testificación"
    if "pedimento" in t: return "Manifestación y Pedimento"
    if "manifestación" in t or "manifestacion" in t: return "Manifestación y Pedimento"
    return "Otro / No identificado"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " "

    cuerpo = limpiar_texto(texto_sucio)

    # 1. IDENTIFICAR TRAMITE
    tipo_tramite = identificar_tramite(cuerpo)

    # 2. CVE Y JUZGADO
    cve = re.search(r'CVE\s*[:\s]*(\d+)', cuerpo, re.IGNORECASE)
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[\wÁÉÍÓÚÑ\s]+?)(?=\s+S\.J\.L| Santiago| Ovalle| La Serena|\d|$)', cuerpo, re.IGNORECASE)

    # 3. NOMBRE DE LA MINA (Entre comillas)
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    
    # 4. SOLICITANTE (Anclado al RUT)
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,65})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|domiciliado|representado))', cuerpo)

    # 5. ROL / CAUSA
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    
    # 6. FOJAS (Captura el número con punto)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo, re.IGNORECASE)
    if not fojas:
        fojas = re.search(r'(\d{1,4}\.?\d{0,3})\s+N°', cuerpo)

    # 7. COMUNA (Ahora captura nombres compuestos como Las Condes)
    # Busca después de "comuna de" hasta encontrar una coma, un punto o palabra legal
    comuna_match = re.search(r'(?i)comuna\s+de\s+([A-ZÁÉÍÓÚÑa-z\s]{3,25})(?=\s*[\.\,]| R\.U\.T| fojas| fjs| juzgado)', cuerpo)
    comuna = comuna_match.group(1).strip() if comuna_match else "No detectado"

    # 8. COORDENADAS
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', cuerpo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "Tipo de Trámite": tipo_tramite,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": limpiar_texto(nombre.group(1)) if nombre else "No detectado",
        "Solicitante": limpiar_texto(solic.group(1)) if solic else "No detectado",
        "Rol/Causa": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna,
        "Juzgado": juzgado.group(0).strip() if juzgado else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    
    # Columnas organizadas
    cols = ["Archivo", "Tipo de Trámite", "CVE", "Nombre Mina", "Solicitante", "Rol/Causa", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)"]
    st.dataframe(df[cols])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel", output.getvalue(), "Base_Datos_Mineria.xlsx")
