import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def limpiar_bloque(texto):
    if not texto: return ""
    # Elimina saltos de línea, tabulaciones y espacios múltiples
    return " ".join(texto.split()).strip()

def extraer_datos_mineros(pdf_file):
    texto_sucio = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if txt: texto_sucio += txt + " "

    # Aplanamos el texto para que nada lo interrumpa
    cuerpo = limpiar_bloque(texto_sucio)

    # 1. CVE (Búsqueda numérica simple)
    cve = re.search(r'CVE\s*[:\s]*(\d+)', cuerpo, re.IGNORECASE)
    
    # 2. JUZGADO (Búsqueda por ciudad o palabra clave)
    # Buscamos el patrón "X Juzgado de Letras de CIUDAD"
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[\wÁÉÍÓÚÑ]+)', cuerpo, re.IGNORECASE)
    if not juzgado: # Intento alternativo
        juzgado = re.search(r'Juzgado\s+de\s+Letras\s+de\s+([\wÁÉÍÓÚÑ]+)', cuerpo, re.IGNORECASE)

    # 3. NOMBRE DE LA MINA
    # En minería casi siempre va entre comillas o después de 'denominada'
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]{3,40})[\"”]', cuerpo)
    if not nombre:
        nombre = re.search(r'(?:denominada|denominará|pertenencia)\s+([A-ZÁÉÍÓÚÑ\d\s]{3,40})', cuerpo, re.IGNORECASE)

    # 4. SOLICITANTE (Lo que esté antes del RUT o después de S.J.L.)
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{10,60})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado))', cuerpo)
    if not solic:
        solic = re.search(r'S\.J\.L\.\s*,\s*([A-ZÁÉÍÓÚÑ\s]{10,60})', cuerpo)

    # 5. ROL / CAUSA
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    
    # 6. FOJAS (Captura el número antes de "N°" o después de "fojas")
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo, re.IGNORECASE)
    if not fojas:
        fojas = re.search(r'(\d{1,4}\.?\d{0,3})\s+N°', cuerpo)

    # 7. COMUNA (Busca la ciudad tras "comuna de")
    comuna = re.search(r'comuna\s+de\s+([\wÁÉÍÓÚÑ]+)', cuerpo, re.IGNORECASE)

    # 8. COORDENADAS
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', cuerpo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": limpiar_bloque(nombre.group(1)) if nombre else "No detectado",
        "Solicitante": limpiar_bloque(solic.group(1)) if solic else "No detectado",
        "Rol/Causa": rol.group(1) if rol else "No detectado",
        "Fojas": fojas.group(1) if fojas else "No detectado",
        "Comuna": comuna.group(1).capitalize() if comuna else "No detectado",
        "Juzgado": juzgado.group(0).strip() if juzgado else "No detectado",
        "Norte (Y)": norte.group(1).replace(".", "") if norte else "Ver PDF",
        "Este (X)": este.group(1).replace(".", "") if este else "Ver PDF"
    }

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = [extraer_datos_mineros(f) for f in uploaded_files]
    df = pd.DataFrame(data)
    
    # Reordenar columnas para que coincidan con la Ficha de la imagen
    cols = ["Archivo", "CVE", "Nombre Mina", "Solicitante", "Rol/Causa", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)"]
    st.dataframe(df[cols]) # Usamos dataframe para mejor visualización
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Base_Datos_Mineria.xlsx")
