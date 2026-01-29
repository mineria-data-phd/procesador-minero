import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extractor Minero Pro", layout="wide")
st.title("⚒️ Extractor de Expedientes Mineros")

def limpiar_texto(t):
    if not t: return ""
    # Elimina caracteres extraños y normaliza espacios
    return " ".join(t.split()).strip()

def extraer_datos_mineros(pdf_file):
    texto_completo = ""
    primera_parte = ""
    with pdfplumber.open(pdf_file) as pdf:
        for i, pagina in enumerate(pdf.pages):
            txt = pagina.extract_text()
            if txt:
                texto_completo += txt + " "
                if i == 0: primera_parte = txt[:1500] # Primeros 1500 caracteres

    # Limpiamos el texto para que las búsquedas no fallen por saltos de línea
    cuerpo = limpiar_texto(texto_completo)
    cabecera = limpiar_texto(primera_parte)

    # 1. CVE
    cve = re.search(r'CVE\s*(\d+)', cuerpo)
    
    # 2. NOMBRE DE LA MINA (Busca entre comillas o después de 'denominada')
    nombre = re.search(r'[\"“]([A-ZÁÉÍÓÚÑ\d\s\-]+)[\"”]', cabecera)
    if not nombre:
        nombre = re.search(r'(?:denominada|denominará)\s+([A-ZÁÉÍÓÚÑ\d\s]+?)(?=\s+POR TANTO|Fs|Fjs|\.|\,)', cabecera, re.IGNORECASE)

    # 3. SOLICITANTE (Busca nombres largos en mayúsculas antes de RUT o abogado)
    solic = re.search(r'([A-ZÁÉÍÓÚÑ\s]{15,80})(?=\s*,?\s*(?:cédula|R\.U\.T|RUT|abogado|domiciliado))', cabecera)
    if not solic:
        solic = re.search(r'S\.J\.L\.\s*,\s*([A-ZÁÉÍÓÚÑ\s]{10,60})', cabecera)

    # 4. JUZGADO (Busca el patrón del juzgado de letras)
    juzgado = re.search(r'(\d+º?\s*Juzgado\s+de\s+Letras\s+de\s+[\wÁÉÍÓÚÑ]+)', cuerpo, re.IGNORECASE)

    # 5. ROL Y FOJAS
    rol = re.search(r'([A-Z]-\d+-\d{4})', cuerpo)
    fojas = re.search(r'(?:fojas|Fs\.|Fjs\.)\s*([\d\.]+)', cuerpo, re.IGNORECASE)
    if not fojas:
        fojas = re.search(r'(\d{1,4})\s+N°\s+\d+', cuerpo)

    # 6. COMUNA
    comuna = re.search(r'comuna\s+de\s+([\wÁÉÍÓÚÑ]+)', cuerpo, re.IGNORECASE)

    # 7. COORDENADAS (Norte 7 dígitos, Este 6 dígitos)
    norte = re.search(r'Norte[:\s]*([\d\.]{7,10})', cuerpo, re.IGNORECASE)
    este = re.search(r'Este[:\s]*([\d\.]{6,9})', cuerpo, re.IGNORECASE)

    return {
        "Archivo": pdf_file.name,
        "CVE": cve.group(1) if cve else "No detectado",
        "Nombre Mina": limpiar_texto(nombre.group(1)) if nombre else "No detectado",
        "Solicitante": limpiar_texto(solic.group(1)) if solic else "No detectado",
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
    
    # Asegurar orden de columnas
    cols = ["Archivo", "CVE", "Nombre Mina", "Solicitante", "Rol/Causa", "Fojas", "Comuna", "Juzgado", "Norte (Y)", "Este (X)"]
    st.table(df[cols])
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[cols].to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel Completo", output.getvalue(), "Datos_Mineria_Final.xlsx")
