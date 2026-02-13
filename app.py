import streamlit as st
import pdfplumber
import re
import pandas as pd

def procesar_mensura_segura(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        # Extraemos el texto completo
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    # --- CARRIL 1: IDENTIDAD (La Ficha) ---
    # Buscamos datos ignorando el resto del documento
    rol = re.search(r"Rol\s+N.*?N[°º]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", texto)
    solicitante = re.search(r"representada por\s+([^,]+)", texto, re.IGNORECASE)
    
    ficha = {
        "Rol": rol.group(1) if rol else "No encontrado",
        "CVE": cve.group(1) if cve else "No encontrado",
        "Solicitante": solicitante.group(1).strip() if solicitante else "No encontrado"
    }

    # --- CARRIL 2: GEOMETRÍA (Limpieza de ruido) ---
    # Solo buscamos líneas que tengan estructura de coordenadas (7 y 6 dígitos)
    puntos = []
    for linea in texto.split('\n'):
        # Patrón: busca un número de 7 dígitos y uno de 6 en la misma línea
        coords = re.findall(r"(\d[\d\.\,]{6,7})", linea)
        if len(coords) >= 2:
            # Limpiamos puntos y comas para convertirlos en números reales
            num1 = float(coords[0].replace(".", "").replace(",", "."))
            num2 = float(coords[1].replace(".", "").replace(",", "."))
            
            # Identificamos cuál es Norte (7 dígitos) y cuál es Este (6 dígitos)
            norte = max(num1, num2)
            este = min(num1, num2)
            
            if 6000000 < norte < 8000000: # Rango lógico para Chile
                puntos.append((este, norte))
    
    return ficha, puntos

st.title("⚒️ Sistema Minero: Extracción por Doble Carril")
# ... resto de la interfaz para subir archivos y descargar
