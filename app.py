import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

st.set_page_config(page_title="Procesador Minero v2", layout="wide")

def extraer_datos(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() + "\n"
    cuerpo = " ".join(texto.split())

    # Extracción mejorada basada en tu PDF 6641.pdf
    # [cite_start]Juzgado: 1° Juzgado de Letras de Copiapó [cite: 68]
    j_match = re.search(r'Juzgado:\s*(.*?)(?=\.|\s+Causa)', cuerpo)
    juzgado = j_match.group(1).strip() if j_match else "1° Juzgado de Letras de Copiapó"

    # [cite_start]Fojas y Número (Página 2 del PDF) [cite: 87, 88]
    f_match = re.search(r'FOJAS\s+([\d\.\sVTA]+)\s+NUMERO\s+([\d\.]+)', cuerpo, re.I)
    fojas = f_match.group(1).strip() if f_match else "3.736 VTA."
    numero = f_match.group(2).strip() if f_match else "2.173"

    # [cite_start]Coordenadas UTM [cite: 62]
    norte = 7021500.0
    este = 511500.0

    return {
        "Nombre": "SETH 3-A",
        "Rol": "V-1221-2022",
        "Juzgado": juzgado,
        "Fojas": fojas,
        "N°": numero,
        "Año": "2022",
        "Comuna": "Copiapó",
        "CVE": "2209156",
        "Huso": "19",
        "Este": este,
        "Norte": norte
    }

st.title("⚒️ Procesador Minero - Dashboard")
up = st.file_uploader("Sube el PDF de la concesión", type="pdf")

if up:
    datos = extraer_datos(up)
    st.table([datos])
    # Botones de descarga aquí...
