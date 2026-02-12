import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

def normalizar_fecha(texto):
    MESES = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
             "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"}
    if not texto: return ""
    t = texto.lower().strip()
    # Caso numérico (ej: 29/12/2023) [cite: 173]
    m_num = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", t)
    if m_num: return f"{m_num.group(1).zfill(2)}/{m_num.group(2).zfill(2)}/{m_num.group(3)}"
    # Caso texto largo (ej: 10 de diciembre de 2024) 
    m_txt = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", t)
    if m_txt:
        dia, mes, año = m_txt.groups()
        return f"{dia.zfill(2)}/{MESES.get(mes, '01')}/{año}"
    return texto

def extraer_datos_em_ep(texto_sucio):
    texto = re.sub(r'\s+', ' ', texto_sucio).strip()
    
    # Identificar si es Extracto o Mensura
    tipo = "EXTRACTO EM/EP" if "EXTRACTO ART. 83" in texto.upper() else "SOLICITUD MENSURA" [cite: 170]
    
    # Datos de la Concesión [cite: 170, 172, 173]
    prop = re.search(r'(?:pertenencias mineras|denominada)\s+[“"“]?([^”"”\n]+)[”"”]?', texto, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º.]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    juz = re.search(r"del\s+([^,]+JUZGADO[^,]+(?:COPIAPÓ|LA SERENA|VALLENAR))", texto, re.IGNORECASE)
    solic = re.search(r"solicitadas por\s+([^,]+)", texto, re.IGNORECASE)
    
    # Fechas específicas (Interfaz EM/EP) [cite: 167, 172, 173]
    f_sentencia = re.search(r"resolución de fecha\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    f_publicacion = re.search(r"(?:Jueves|Viernes|Lunes)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    f_vencimiento = "" # Este campo suele calcularse o extraerse de plazos legales

    return {
        "Ficha №": "164681", # Placeholder según tu captura
        "Tipo": tipo,
        "Rol": rol.group(1).strip() if rol else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Nombre": prop.group(1).strip() if prop else "No detectado",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "Sentencia": normalizar_fecha(f_sentencia.group(1)) if f_sentencia else "",
        "Publicación": normalizar_fecha(f_publicacion.group(1)) if f_publicacion else "",
        "CVE": re.search(r"CVE\s+(\d+)", texto).group(1) if re.search(r"CVE\s+(\d+)", texto) else ""
    }

# --- (El resto de la lógica de coordenadas y GIS se mantiene igual) ---
