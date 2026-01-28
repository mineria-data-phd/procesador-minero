import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

# Configuración de la página
st.set_page_config(page_title="Procesador Minero Pro", layout="wide")

st.title("⚒️ Extractor Masivo de Expedientes Mineros")
st.markdown("Sube uno o varios PDFs para generar tu tabla de Excel automáticamente.")

def extraer_datos_mineros(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t: texto += t + "\n"

    # Lógica inteligente con Regex (Busca patrones, no palabras fijas)
    # Busca Nombres después de palabras clave como PEDIMENTO o MANIFESTACION
    nombre_raw = re.search(r"(?:PEDIMENTO|MANIFESTACION|MINA|Mina)\s+([\w\s-]+)", texto)
    
    # Busca Roles con formato V-000-0000
    rol_raw = re.search(r"(?:Rol|Causa|V-)\s*(\d+-\d+|V-\d+-\d+)", texto, re.I)
    
    # Busca Inscripción (Fojas y Número)
    fojas_raw = re.search(r"(?:Fs|Fojas|fs)\.?\s*([\d\.]+)", texto, re.I)
    num_raw = re.search(r"(?:N°|Nº|Nro|número)\s*([\d\.]+)", texto, re.I)
    ano_raw = re.search(r"(?:Año|año|AÑO)\s*(\d{4})", texto)

    # Busca Coordenadas UTM (formato 6 o 7 millones)
    norte_raw = re.search(r"(?:N|Norte)[:\s]*([\d\.]+)", texto, re.I)
    este_raw = re.search(r"(?:E|Este)[:\s]*([\d\.]+)", texto, re.I)

    return {
        "Archivo": pdf_file.name,
        "Nombre Mina": nombre_raw.group(1).strip() if nombre_raw else "No detectado",
        "Rol/Causa": rol_raw.group(0) if rol_raw else "S/R",
        "Fojas": fojas_raw.group(1) if fojas_raw else "",
        "Número": num_raw.group(1) if num_raw else "",
        "Año": ano_raw.group(1) if ano_raw else "",
        "Coordenada Norte": norte_raw.group(1) if norte_raw else "",
        "Coordenada Este": este_raw.group(1) if este_raw else ""
    }

# Lógica de la interfaz
uploaded_files = st.file_uploader("Arrastra aquí tus archivos PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = []
    for file in uploaded_files:
        with st.spinner(f"Procesando {file.name}..."):
            datos = extraer_datos_mineros(file)
            resultados.append(datos)
    
    df = pd.DataFrame(resultados)
    
    st.success("¡Procesamiento completado!")
    st.write("### Vista previa de los datos extraídos:")
    st.dataframe(df)

    # Botón para descargar Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos_Mineros')
    
    st.download_button(
        label="📥 Descargar todo en Excel",
        data=output.getvalue(),
        file_name="consolidado_minero.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )