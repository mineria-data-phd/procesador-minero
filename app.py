import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def identificar_tramite(texto):
    t = texto.lower()
    # Lógica basada en las capturas de tus formularios
    if "rectificación" in t or "rectificacion" in t:
        return "Solicitud de Rectificación"
    if "mensura" in t and ("solicitud" in t or "sentencia" in t):
        return "Solicitud de Mensura"
    if "testificación" in t or "testificacion" in t:
        return "Solicitud de Testificación"
    if "pedimento" in t or "manifestación" in t or "manifestacion" in t:
        return "Manifestación y Pedimento"
    return "Extracto EM y EP"

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " \n "

    # Normalización del texto (aplanado total)
    cuerpo = " ".join(texto_sucio.split()).strip()

    # 1. TIPO DE TRÁMITE
    tipo = identificar_tramite(cuerpo)

    # 2. CVE
    cve = re.search(r'CVE\s*[:\s]*(\d+)', cuerpo, re.IGNORECASE)
    
    # 3. JUZGADO (Busca hasta encontrar un quiebre lógico como S.J.L o Santiago)
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z\s]+?)(?=\s+S\.J\.L|\s+Santiago|\s+CVE|\d{2}\.)', cuerpo)

    # 4. NOMBRE DE LA MINA (Prioriza texto entre comillas)
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    
    # 5. SOLICITANTE (Anclado al RUT para evitar párrafos largos)
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,65})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|domiciliado))', cuerpo)

    # 6. ROL / CAUSA
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    
    # 7. FOJAS (Captura el número con punto separador de miles)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo, re.IGNORECASE)
    if not fojas:
        fojas = re.search(r'(\d{1,3}\.?\d{0,3})\s+N°', cuerpo)

    # 8. COMUNA (Captura nombres compuestos como "Las Condes" o "La Serena")
    comuna_match = re.search(r'(?i)comuna\s+de\s+([A-ZÁÉÍÓÚÑa-z\s]{3,25})(?=\s*[\.\,]| R\.U\.T| fojas| fjs| juzgado)', cuerpo)
    comuna = comuna_match.group(1).strip() if comuna_match else "No detectado"

    # 9. COORDENADAS
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', cuerpo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Nombre Mina": nombre.group(1).strip() if nombre else "No detectado",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "Rol": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna,
        "Juzgado": juzgado.group(0).strip() if juzgado else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF",
        "CVE": cve.group(1) if cve else "No detectado"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    
    # Columnas organizadas según tus capturas de pantalla
    cols = ["Archivo", "Tipo", "Nombre Mina", "Solicitante", "Rol", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)", "CVE"]
    st.dataframe(df[cols])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Reporte", output.getvalue(), "Base_Datos_Mineria.xlsx")
