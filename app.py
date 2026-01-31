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

    # --- 1. JUZGADO (Traductor de Orden: Números y Palabras) ---
    # Diccionario de traducción para estandarizar el formato
    diccionario_juzgados = {
        "primer": "1°", "1": "1°", "primero": "1°",
        "segundo": "2°", "2": "2°",
        "tercer": "3°", "3": "3°", "tercero": "3°",
        "cuarto": "4°", "4": "4°",
        "quinto": "5°", "5": "5°"
    }

    juz_base = re.search(r'(Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z]+)', cuerpo, re.IGNORECASE)
    juzgado = "No detectado"

    if juz_base:
        pos = juz_base.start()
        # Escaneamos un poco antes del texto para pillar el número o la palabra
        fragmento = cuerpo[max(0, pos-15):pos].lower().strip()
        # Buscamos un dígito o una palabra de orden
        orden_match = re.search(r'(\d+|primer|segundo|tercer|cuarto|quinto)', fragmento)
        
        if orden_match:
            valor_encontrado = orden_match.group(1)
            prefijo = diccionario_juzgados.get(valor_encontrado, valor_encontrado + "°")
            juzgado = f"{prefijo} {juz_base.group(0)}"
        else:
            juzgado = juz_base.group(0)

    # --- 2. NOMBRE DE LA MINA Y SOLICITANTE ---
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "No detectado"
    
    # Rescate para nombres sin comillas (como el FQM E que ya detectamos)
    if nombre == "No detectado":
        respaldo = re.search(r'(?:denominada|pertenencia|mina)\s+([A-ZÁÉÍÓÚÑ\s]{3,40})', cuerpo, re.IGNORECASE)
        if respaldo: nombre = respaldo.group(1).strip()

    solic_m = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|domiciliado))', cuerpo)
    solicitante = solic_m.group(1).strip() if solic_m else "No detectado"

    # --- 3. RESTO DE CAMPOS ---
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    fojas = re.search(r'(?i)(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo)
    com_m = re.search(r'(?i)comuna\s+de\s+([A-ZÁÉÍÓÚÑa-z\s]{3,25})(?=\s*[\.\,]| R\.U\.T| fjs| juzgado)', cuerpo)
    comuna = com_m.group(1).strip() if com_m else "No detectado"

    tipo = identificar_tramite(cuerpo)
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', cuerpo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', cuerpo, re.IGNORECASE)
    cve = re.search(r'CVE\s*[:\s]*(\d+)', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Nombre Mina": nombre,
        "Solicitante": solicitante,
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
    st.download_button("📥 Descargar Reporte Final", output.getvalue(), "Mineria_Reporte.xlsx")
