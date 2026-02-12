import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

st.set_page_config(page_title="Procesador Minero Profesional", layout="wide")

def extraer_todo_final(texto):
    # 1. Propiedad (Busca entre comillas después de palabras clave)
    nombre = re.search(r'(?:denominada|pertenencias|pertenencia)\s+"([^"]+)"', texto, re.IGNORECASE)
    
    # 2. Rol (Captura formatos como V-1068-2025 o V-35-2022)
    rol = re.search(r"Rol\s+N°?\s*([\w\-]+)", texto, re.IGNORECASE)
    
    # 3. Juzgado (Captura "3º EN LO CIVIL DE COPIAPÓ" o "1º Juzgado...")
    juzgado = re.search(r"(?:S\.J\.L\.|JUZGADO)\s+(\d+º?\s+.*?)(?:CAUSA|ROL|$)", texto, re.IGNORECASE)
    
    # 4. Solicitante (Captura el nombre completo sin cortes)
    solicitante = re.search(r"representación\s+(?:judicial\s+)?(?:según\s+se\s+acreditará\s+de|de)\s+([^,.\n]+?)(?:\s*,|\s*ya|\s*individualizada|\s*del|$)", texto, re.IGNORECASE)
    
    # 5. Comuna y CVE
    comuna = re.search(r"(?:domiciliado\s+en|de\s+la\s+ciudad\s+de)\s+([\w\s]+?)(?:,|\s+Avenida|$)", texto, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", texto)
    
    # 6. FECHAS
    f_publicacion = re.search(r"(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto)
    f_sol_mensura = re.search(r"manifestadas\s+con\s+fecha\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto)
    # Fecha de resolución al final
    f_mensura = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar),\s+([a-z\s]+de\s+[a-z]+\s+de\s+dos\s+mil\s+[a-z\s]+)", texto, re.IGNORECASE)

    return {
        "Propiedad": nombre.group(1).strip() if nombre else "No detectado",
        "Rol": rol.group(1).strip() if rol else "No detectado",
        "Juzgado": juzgado.group(1).strip() if juzgado else "No detectado",
        "Solicitante": solicitante.group(1).strip() if solicitante else "No detectado",
        "Comuna": comuna.group(1).strip() if comuna else "No detectado",
        "CVE": cve.group(1) if cve else "No detectado",
        "F_Sol_Mensura": f_sol_mensura.group(1) if f_sol_mensura else "No detectado",
        "F_Mensura": f_mensura.group(1) if f_mensura else "No detectado",
        "F_Publicacion": f_publicacion.group(1) if f_publicacion else "No detectado",
        "Huso": "19"
    }

def extraer_coordenadas(texto):
    # Detecta V1, L1, etc.
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]+)\s*(?:metros)?\s+([\d\.\,]+)\s*(?:metros)?"
    coincidencias = re.findall(patron, texto)
    puntos = []
    for c in coincidencias:
        norte = float(c[1].replace(".", "").replace(",", "."))
        este = float(c[2].replace(".", "").replace(",", "."))
        puntos.append((este, norte))
    return puntos

st.title("⚒️ Sistema de Fichas Mineras Pro")
archivo_pdf = st.file_uploader("Sube el PDF de Mensura", type=["pdf"])

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        texto = "".join([p.extract_text() for p in pdf.pages])
    
    datos = extraer_todo_final(texto)
    puntos = extraer_coordenadas(texto)
    
    if puntos:
        st.success(f"✅ Ficha generada con éxito")
        st.table(pd.DataFrame(list(datos.items()), columns=["Dato", "Valor"]))
        
        # Botones de descarga
        buffer_ex = BytesIO()
        with pd.ExcelWriter(buffer_ex, engine='xlsxwriter') as writer:
            pd.DataFrame([datos]).to_excel(writer, sheet_name='Ficha_Tecnica', index=False)
            pd.DataFrame(puntos, columns=['Este', 'Norte']).to_excel(writer, sheet_name='Coordenadas', index=False)
        st.download_button("📥 Descargar Excel Completo", buffer_ex.getvalue(), f"Ficha_{datos['Propiedad']}.xlsx")
    else:
        st.error("No se detectaron coordenadas. Revisa el formato del PDF.")
