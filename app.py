import streamlit as st
import pdfplumber
import re
import pandas as pd

def extraer_manifestaciones_pedimentos(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() + " "
    
    # Limpieza básica de espacios
    cuerpo = " ".join(texto.split())

    # Extracción con Regex siguiendo el orden de la ficha
    data = {
        "Tipo": "Pedimento" if "PEDIMENTO" in cuerpo.upper() else "Manifestación",
        "Rol": next(iter(re.findall(r'Rol[:\s]+([A-Z]-\d+-\d{4})', cuerpo, re.I)), "N/A"),
        "Nombre": next(iter(re.findall(r'(?:denominaré|concesión)\s+([A-ZÁÉÍÓÚÑ\d\s\-]+?)(?=\.|\s+El Punto Medio)', cuerpo)), "N/A"),
        "Solicitante": next(iter(re.findall(r'Demandante[:\s]+([A-ZÁÉÍÓÚÑ\s\.\-]+?)(?=R\.U\.T|Representante)', cuerpo)), "N/A"),
        "Comuna": next(iter(re.findall(r'comuna\s+de\s+([\w\s]+?)(?=\s*,|\s+ciudad|\s+provincia)', cuerpo, re.I)), "N/A"),
        "Conservador": next(iter(re.findall(r'Conservador\s+de\s+Minas\s+de\s+([\w\s]+)', cuerpo, re.I)), "N/A"),
        "Fojas": next(iter(re.findall(r'Fs\.?\s*([\d\.]+[\s\w]*)', cuerpo, re.I)), "N/A"),
        "N°": next(iter(re.findall(r'Nº\s*([\d\.]+)', cuerpo, re.I)), "N/A"),
        "Año": next(iter(re.findall(r'REG\.\s+DESCUBRIMIENTOS\s+(\d{4})', cuerpo, re.I)), "2022"),
        "Juzgado": next(iter(re.findall(r'Juzgado[:\s]+([\dº\s\w]+Letras de [\w\s]+)', cuerpo, re.I)), "N/A"),
        "Presentación": next(iter(re.findall(r'presentado el\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)), "N/A"),
        "Vencimiento_SM": "", # Generalmente es cálculo de fecha presentación + 90 días
        "Publicación": next(iter(re.findall(r'(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})\s+BOLETÍN', cuerpo, re.I)), "N/A"),
        "CVE": next(iter(re.findall(r'CVE\s+(\d+)', cuerpo)), "N/A"),
        "Huso": next(iter(re.findall(r'Huso\s+(\d+)', cuerpo, re.I)), "19"),
        "Este": next(iter(re.findall(r'Este[:\s]+([\d\.\,]+)', cuerpo, re.I)), "0"),
        "Norte": next(iter(re.findall(r'Norte[:\s]+([\d\.\,]+)', cuerpo, re.I)), "0")
    }
    return data

# Lógica de Streamlit para prueba
st.title("Paso 1: Extractor de Manifestaciones y Pedimentos")
uploaded = st.file_uploader("Sube el PDF 6641.pdf", type="pdf")
if uploaded:
    res = extraer_manifestaciones_pedimentos(uploaded)
    st.table([res])
