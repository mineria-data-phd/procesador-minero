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

    # --- 1. JUZGADO (Traducción limpia de 1°, 2°, 3°) ---
    diccionario_juzgados = {
        "primer": "1°", "1": "1°", "primero": "1°",
        "segundo": "2°", "2": "2°",
        "tercer": "3°", "3": "3°", "tercero": "3°"
    }
    juz_base = re.search(r'(Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z]+)', cuerpo, re.IGNORECASE)
    juzgado = "No detectado"
    if juz_base:
        pos = juz_base.start()
        fragmento = cuerpo[max(0, pos-20):pos].lower().strip()
        orden_match = re.search(r'\b(primer|segundo|tercer|1|2|3)\b', fragmento)
        if orden_match:
            valor = orden_match.group(1)
            prefijo = diccionario_juzgados.get(valor, valor + "°")
            juzgado = f"{prefijo} {juz_base.group(0)}"
        else:
            juzgado = juz_base.group(0)

    # --- 2. NOMBRE (Ajuste específico para SETH 3-A) ---
    # Buscamos patrones como "SETH 3-A" o texto entre comillas
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "No detectado"
    
    if nombre == "No detectado":
        # Buscamos específicamente nombres con guiones y números como SETH 3-A
        especifico = re.search(r'\b([A-Z]{3,}\s\d+\-[A-Z])\b', cuerpo)
        if especifico: nombre = especifico.group(1).strip()

    # --- 3. SOLICITANTE (Ajuste para FQAM EXPLORATION / Demandante) ---
    # Buscamos después de la palabra 'Demandante' o antes de 'RUT'
    solicitante = "No detectado"
    solic_match = re.search(r'(?:Demandante|Solicitante)[:\s]*([A-ZÁÉÍÓÚÑ\s\(\)]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo, re.IGNORECASE)
    
    if solic_match:
        solicitante = solic_match.group(1).strip()
    else:
        # Intento directo por nombre de la empresa si el patrón falla
        empresa = re.search(r'(FQAM\s+EXPLORATION\s+\(CHILE\)\s+S\.A\.)', cuerpo)
        if empresa: solicitante = empresa.group(1).strip()

    # --- 4. OTROS CAMPOS ---
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    fojas = re.search(r'(?i)(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo)
    com_m = re.search(r'(?i)comuna\s+de\s+([A-ZÁÉÍÓÚÑa-z\s]{3,25})(?=\s*[\.\,]| R\.U\.T| fjs| juzgado)', cuerpo)
    comuna = com_m.group(1).strip() if com_m else "No detectado"
    tipo = identificar_tramite(cuerpo)
    cve = re.search(r'CVE\s*[:\s]*(\d+)', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Nombre": nombre,
        "Solicitante": solicitante,
        "Rol": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna,
        "Juzgado": juzgado,
        "CVE": cve.group(1) if cve else "No detectado"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    # Cambiamos el orden y nombre de la columna a "Nombre"
    cols = ["Archivo", "Tipo", "Nombre", "Solicitante", "Rol", "Fojas", "Comuna", "Juzgado", "CVE"]
    st.dataframe(df[cols])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Reporte Corregido", output.getvalue(), "Mineria_Reporte_Final.xlsx")
