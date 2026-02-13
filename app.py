import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# 1. TRADUCTOR DE FECHAS MEJORADO
def normalizar_fecha(texto):
    MESES = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
             "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"}
    NUMEROS = {"uno": "01", "dos": "02", "tres": "03", "cuatro": "04", "cinco": "05", "seis": "06", "siete": "07", "ocho": "08", 
               "nueve": "09", "diez": "10", "once": "11", "doce": "12", "trece": "13", "catorce": "14", "quince": "15", 
               "dieciséis": "16", "diecisiete": "17", "dieciocho": "18", "diecinueve": "19", "veinte": "20", "veintiuno": "21", 
               "veintidós": "22", "veintitrés": "23", "veinticuatro": "24", "veinticinco": "25", "veintiséis": "26", 
               "veintisiete": "27", "veintiocho": "28", "veintinueve": "29", "treinta": "30", "treintiuno": "31"}
    
    if not texto or "No detectado" in texto: return "No detectado"
    t = texto.lower().replace("  ", " ").strip()
    
    # Busca formato: "16 de enero de 2026"
    m1 = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", t)
    if m1:
        dia, mes, año = m1.groups()
        return f"{dia.zfill(2)}/{MESES.get(mes, '01')}/{año}"
    
    # Busca formato: "dieciséis de enero de dos mil veintiséis"
    m2 = re.search(r"(\w+)\s+de\s+(\w+)\s+de\s+dos\s+mil\s+(\w+)", t)
    if m2:
        dia_txt, mes_txt, año_txt = m2.groups()
        año_final = "20" + NUMEROS.get(año_txt, "26")
        return f"{NUMEROS.get(dia_txt, '01')}/{MESES.get(mes_txt, '01')}/{año_final}"
    
    return texto

# 2. EXTRACCIÓN CON FOCO EN LA RESOLUCIÓN
def extraer_datos_mineros(texto_sucio):
    texto = re.sub(r'\s+', ' ', texto_sucio).strip()
    
    prop = re.search(r'(?:denominada|pertenencia|pertenencias)\s+[“"“]([^”"”]+)[”"”]', texto, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    juz = re.search(r"(?:S\.J\.L\.|JUZGADO)\s*(\d+.*? (?:COPIAPÓ|LA SERENA|VALLENAR|SANTIAGO))", texto, re.IGNORECASE)
    solic = re.search(r"representación(?:.*? de| de)\s+([^,]+?)(?:\s*,|\s+individualizada|\s+ya|$)", texto, re.IGNORECASE)
    
    # FECHA DE RESOLUCIÓN: Buscamos el patrón que viene después de la ciudad al final del documento
    # Ejemplo: "Copiapó, dieciséis de enero de dos mil veintiséis"
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar|Atacama),\s+([^.]+)", texto, re.IGNORECASE)

    return {
        "Propiedad": prop.group(1).strip() if prop else "No detectado",
        "Rol": rol.group(1).strip() if rol else "Sin Rol",
        "Juzgado": juz.group(1).strip() if juz else "Sin Juzgado",
        "Solicitante": solic.group(1).strip().replace('“', '').replace('”', '') if solic else "Sin Solicitante",
        "F_Resolu": normalizar_fecha(f_res.group(1).strip() if f_res else "No detectado"),
        "Huso": "19S"
    }

def extraer_coordenadas(texto):
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]+)\s+([\d\.\,]+)"
    coincidencias = re.findall(patron, texto)
    return [(float(c[2].replace(".", "").replace(",", ".")), float(c[1].replace(".", "").replace(",", "."))) for c in coincidencias]

# --- INTERFAZ ---
st.title("⚒️ Sistema Minero: Corrección de Fecha y Join")
archivo_pdf = st.file_uploader("Sube el PDF de Mensura", type=["pdf"])

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        texto_completo = " ".join([p.extract_text() for p in pdf.pages])
    
    datos = extraer_datos_mineros(texto_completo)
    puntos = extraer_coordenadas(texto_completo)
    
    if datos:
        st.subheader("Resultados de Extracción")
        st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
        
        if len(puntos) >= 3:
            # SHAPEFILE CON JOIN DE ATRIBUTOS
            poligono = Polygon(puntos + [puntos[0]])
            gdf = gpd.GeoDataFrame([datos], geometry=[poligono], crs="EPSG:32719")
            
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zf:
                gdf.to_file("export.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    zf.write(f"export{ext}", arcname=f"{datos['Propiedad']}{ext}")
                    os.remove(f"export{ext}")
            
            st.download_button("🌍 Descargar Shapefile (con Datos)", zip_buffer.getvalue(), f"SIG_{datos['Propiedad']}.zip")
