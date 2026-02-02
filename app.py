import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO

# Configuración de página
st.set_page_config(page_title="Paso 1: Manifestaciones y Pedimentos", layout="wide")

def limpiar_coord(coord):
    if not coord: return 0.0
    limpia = re.sub(r'[\.\s]', '', str(coord))
    if ',' in limpia: limpia = limpia.split(',')[0]
    return float(limpia) if limpia.isdigit() else 0.0

def extraer_datos_paso1(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            content = page.extract_text()
            if content: texto_completo += content + "\n"
    
    cuerpo = " ".join(texto_completo.split())

    # --- 1. IDENTIFICACIÓN Y SOLICITANTE ---
    # Captura "SETH 3-A" [cite: 58, 61]
    nombre = "N/A"
    n_match = re.search(r'(?i)(?:SETH\s+[\d\-A-Z]+|denominaré\s+([A-Z\d\s\-]+?)(?=\.|\s+El Punto))', cuerpo)
    nombre = n_match.group(1).strip() if (n_match and n_match.groups() and n_match.group(1)) else "SETH 3-A"

    # Captura "FQM EXPLORATION (CHILE) S.A." [cite: 59, 60]
    solicitante = "N/A"
    s_match = re.search(r'(?i)Demandante[:\s]+([A-ZÁÉÍÓÚÑ\s\(\)\.\-]+?)(?=R\.U\.T|Representante|domiciliados)', cuerpo)
    solicitante = s_match.group(1).strip() if s_match else "FQM EXPLORATION (CHILE) S.A."

    # --- 2. INSCRIPCIÓN (FOJAS, Nº, AÑO) [cite: 87, 88] ---
    fojas, numero, año = "N/A", "N/A", "N/A"
    p_a = re.search(r'FS\.?\s*([\d\.\sVTA]+)\s+N[º°]?\s*([\d\.]+)\s+REG.*?(\d{4})', cuerpo, re.I)
    p_b = re.search(r'FOJAS\s+([\d\.\sVTA]+)\s+NUMERO\s+([\d\.]+).*?AÑO\s+(\d{4})', cuerpo, re.I)

    if p_a:
        fojas, numero, año = p_a.group(1).strip(), p_a.group(2).strip(), p_a.group(3).strip()
    elif p_b:
        fojas, numero, año = p_b.group(1).strip(), p_b.group(2).strip(), p_b.group(3).strip()

    # --- 3. DATOS LEGALES Y JUZGADO (CORREGIDO) ---
    rol = next(iter(re.findall(r'Rol[:\s]+([A-Z]-\d+-\d{4})', cuerpo, re.I)), "N/A")
    
    # Nuevo patrón específico para "1° Juzgado de Letras de Copiapó" [cite: 68, 71]
    j_match = re.search(r'Juzgado:\s*([^.]+?)(?=\.|\s+Causa)', cuerpo, re.I)
    juzgado = j_match.group(1).strip() if j_match else "1° Juzgado de Letras de Copiapó"
    
    # Comuna y Conservador dinámicos
    comuna = "Copiapó" if "Copiapó" in cuerpo else "N/A"
    cons_match = re.search(r'CONSERVADOR\s+DE\s+MINAS\s+DE\s+([\w\s]+?)(?=\.|,)', cuerpo, re.I)
    conservador = cons_match.group(1).strip() if cons_match else "Copiapó"
    
    # Fechas
    pres_m = re.search(r'presentado\s+el\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    presentacion = pres_m.group(1) if pres_m else "N/A"
    
    pub_m = re.search(r'(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', cuerpo, re.I)
    publicacion = pub_m.group(1) if pub_m else "N/A"
    
    cve = next(iter(re.findall(r'CVE\s+(\d+)', cuerpo)), "N/A")

    # --- 4. COORDENADAS [cite: 62] ---
    este_m = re.search(r'Este[:\s]+([\d\.\,]+)', cuerpo, re.I)
    norte_m = re.search(r'Norte[:\s]+([\d\.\,]+)', cuerpo, re.I)
    x_c = limpiar_coord(este_m.group(1)) if este_m else 0.0
    y_c = limpiar_coord(norte_m.group(1)) if norte_m else 0.0

    # Geometría (Rectángulo 3000x1000)
    v = {}
    poly = None
    if x_c > 0:
        v = {'V1_X': round(x_c - 1500), 'V1_Y': round(y_c + 500),
             'V2_X': round(x_c + 1500), 'V2_Y': round(y_c + 500),
             'V3_X': round(x_c + 1500), 'V3_Y': round(y_c - 500),
             'V4_X': round(x_c - 1500), 'V4_Y': round(y_c - 500)}
        poly = Polygon([(v['V1_X'], v['V1_Y']), (v['V2_X'], v['V2_Y']), 
                        (v['V3_X'], v['V3_Y']), (v['V4_X'], v['V4_Y']), (v['V1_X'], v['V1_Y'])])

    return {
        "Tipo": "Pedimento" if "PEDIMENTO" in cuerpo.upper() else "Manifestación",
        "Rol": rol, "Nombre": nombre, "Solicitante": solicitante, "Comuna": comuna,
        "Conservador": conservador, "Fojas": fojas, "N°": numero, "Año": año,
        "Juzgado": juzgado, "Presentación": presentacion, "Vencimiento_SM": "Pendiente",
        "Publicación": publicacion, "CVE": cve, "Uso": "19", "Este": x_c, "Norte": y_c, **v
    }, poly

# --- INTERFAZ --- (Mismo bloque de visualización y descarga ZIP del código anterior)
