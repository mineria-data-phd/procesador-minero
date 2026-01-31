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

    # Normalizamos el texto quitando espacios extra
    cuerpo = " ".join(texto_sucio.split()).strip()

    # --- 1. JUZGADO (Lógica Robusta para el 1°, 2°, 3°) ---
    # Buscamos la frase "Juzgado de Letras de..."
    juz_base = re.search(r'(Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-z]+)', cuerpo, re.IGNORECASE)
    
    juzgado = "No detectado"
    if juz_base:
        # Si lo encuentra, miramos qué hay JUSTO antes (máximo 5 caracteres)
        inicio_frase = juz_base.start()
        prefijo = cuerpo[max(0, inicio_frase-5):inicio_frase].strip()
        
        # Extraemos solo el primer número que veamos (1, 2 o 3)
        numero = re.search(r'(\d)', prefijo)
        
        if numero:
            # Forzamos que aparezca con el símbolo ° que tú necesitas
            juzgado = f"{numero.group(1)}° {juz_base.group(0)}"
        else:
            # Si no hay número cerca, dejamos la frase sola
            juzgado = juz_base.group(0)

    # --- 2. NOMBRE DE LA MINA (Ajuste para el archivo 6641) ---
    # Buscamos el nombre entre comillas
    nombre_m = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,50})[\"”]', cuerpo)
    nombre = nombre_m.group(1).strip() if nombre_m else "No detectado"
    
    # Si sigue sin aparecer (caso 6641), buscamos el primer bloque de mayúsculas tras el Juzgado
    if nombre == "No detectado" and juz_base:
        pos_final_juzgado = juz_base.end()
        mayusculas = re.search(r'([A-ZÁÉÍÓÚÑ\s]{5,40})', cuerpo[pos_final_juzgado:])
        if mayusculas: nombre = mayusculas.group(1).strip()

    # --- 3. SOLICITANTE, ROL Y COMUNA ---
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo)
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    fojas = re.search(r'(?i)(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo)
    
    com_match = re.search(r'(?i)comuna\s+de\s+([A-ZÁÉÍÓÚÑa-z\s]{3,25})(?=\s*[\.\,]| R\.U\.T| fjs| juzgado)', cuerpo)
    comuna = com_match.group(1).strip() if com_match else "No detectado"

    # --- 4. COORDENADAS ---
    tipo = identificar_tramite(cuerpo)
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', cuerpo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', cuerpo, re.IGNORECASE)
    cve = re.search(r'CVE\s*[:\s]*(\d+)', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "Tipo": tipo,
        "Nombre Mina": nombre,
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
    st.download_button("📥 Descargar Reporte Final", output.getvalue(), "Reporte_Mineria.xlsx")
