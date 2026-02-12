import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# --- MOTOR DE TRADUCCIÓN DE FECHAS ---
def normalizar_fecha(texto):
    MESES = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
             "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"}
    NUMEROS = {"uno": "01", "dos": "02", "tres": "03", "cuatro": "04", "cinco": "05", "seis": "06", "siete": "07", "ocho": "08", 
               "nueve": "09", "diez": "10", "once": "11", "doce": "12", "trece": "13", "catorce": "14", "quince": "15", 
               "dieciséis": "16", "diecisiete": "17", "dieciocho": "18", "diecinueve": "19", "veinte": "20", "veintiuno": "21", 
               "veintidós": "22", "veintitrés": "23", "veinticuatro": "24", "veinticinco": "25", "veintiséis": "26", 
               "veintisiete": "27", "veintiocho": "28", "veintinueve": "29", "treinta": "30", "treintiuno": "31"}
    if not texto: return ""
    t = texto.lower().strip()
    # Caso numérico: 29/12/2023
    m_num = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", t)
    if m_num: return f"{m_num.group(1).zfill(2)}/{m_num.group(2).zfill(2)}/{m_num.group(3)}"
    # Caso texto: dieciséis de enero...
    m_txt = re.search(r"(\w+)\s+de\s+(\w+)\s+de\s+dos\s+mil\s+(\w+)", t)
    if m_txt:
        d, m, a = m_txt.groups()
        return f"{NUMEROS.get(d, '01')}/{MESES.get(m, '01')}/20{NUMEROS.get(a, '26')}"
    return texto

def extraer_datos_prospeccion(texto_sucio):
    texto = re.sub(r'\s+', ' ', texto_sucio).strip()
    
    # Detección de Tipo
    tipo = "EXTRACTO EM/EP" if "EXTRACTO" in texto.upper() else "SOLICITUD MENSURA"
    
    # Extracción de campos clave
    prop = re.search(r'(?:denominada|pertenencia|concesión:)\s+[“"“]?([^”"”\n,]+)[”"”]?', texto, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º.]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    juz = re.search(r"(?:S\.J\.L\.|JUZGADO)\s*(\d+.*? (?:COPIAPÓ|LA SERENA|VALLENAR|SANTIAGO))", texto, re.IGNORECASE)
    solic = re.search(r"(?:solicitadas por|representación de)\s+([^,]+)", texto, re.IGNORECASE)
    
    # Fechas específicas de Extracto
    f_mensura = re.search(r"mensuradas el\s+(\d{1,2}/\d{1,2}/\d{4})", texto, re.IGNORECASE)
    f_resol = re.search(r"resolución de fecha\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)

    return {
        "Tipo": tipo,
        "Propiedad": prop.group(1).strip() if prop else "No detectado",
        "Rol": rol.group(1).strip() if rol else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "F_Mensura": normalizar_fecha(f_mensura.group(1)) if f_mensura else "",
        "F_Resoluc": normalizar_fecha(f_resol.group(1)) if f_resol else "",
        "CVE": re.search(r"CVE\s+(\d+)", texto).group(1) if re.search(r"CVE\s+(\d+)", texto) else "No detectado"
    }

# --- INTERFAZ STREAMLIT ---
st.title("⚒️ Prospecciones Mineras: Módulo EM/EP")
archivo = st.file_uploader("Sube el PDF (Mensura o Extracto)", type=["pdf"])

if archivo:
    with pdfplumber.open(archivo) as pdf:
        texto_completo = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    datos = extraer_datos_prospeccion(texto_completo)
    st.success(f"✅ Detectado como: {datos['Tipo']}")
    st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
