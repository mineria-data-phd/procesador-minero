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

    # Normalización total para que los saltos de línea no rompan la búsqueda
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- 1. JUZGADO (Lógica de Proximidad) ---
    # Buscamos la frase base "Juzgado de Letras de [Ciudad]"
    juz_base = re.search(r'(Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z]+)', cuerpo, re.IGNORECASE)
    
    if juz_base:
        pos = juz_base.start()
        # Miramos un poco antes del hallazgo para ver si hay un número o palabra de orden
        fragmento_anterior = cuerpo[max(0, pos-20):pos].strip()
        orden = re.search(r'(\d+[\s°º°\.]*|Primer|Segundo|Tercer|Cuarto|Quinto)', fragmento_anterior, re.IGNORECASE)
        
        prefix = orden.group(0).strip() if orden else ""
        juzgado = f"{prefix} {juz_base.group(0)}".strip()
    else:
        juzgado = "No detectado"

    # --- 2. NOMBRE DE LA MINA Y SOLICITANTE (Reforzado para 6641) ---
    # Si no hay comillas, buscamos el bloque en mayúsculas tras "denominada"
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    if not nombre:
        nombre = re.search(r'(?i)(?:denominada|pertenencia|mina|llamada)\s+([A-ZÁÉÍÓÚÑ\d\s]{3,40})', cuerpo)

    # Solicitante: Todo lo que esté antes del RUT/Cédula
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|domiciliado))', cuerpo)

    # --- 3. ROL, FOJAS Y COMUNA ---
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    fojas = re.search(r'(?i)(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo)
    if not fojas:
        fojas = re.search(r'(\d{1,4}\.?\d{0,3})\s+N°', cuerpo)

    # Comuna: Captura nombres compuestos como "Las Condes"
    com_match = re.search(r'(?i)comuna\s+de\s+([A-ZÁÉÍÓÚÑa-z\s]{3,25})(?=\s*[\.\,]| R\.U\.T| fjs| juzgado)', cuerpo)
    comuna = com_match.group(1).strip() if com_match else "No detectado"

    # --- 4. COORDENADAS Y CVE ---
    tipo = identificar_tramite(cuerpo)
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
    st.download_button("📥 Descargar Reporte Final", output.getvalue(), "Base_Datos_Mineria_PRO.xlsx")
