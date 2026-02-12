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

def extraer_datos_mineros(texto):
    # 1. Propiedad: Maneja comillas normales (") y curvas (“ ”)
    prop = re.search(r'(?:denominada|pertenencias|pertenencia)\s+(?:"|“)([^"”]+)(?:"|”)', texto, re.IGNORECASE)
    
    # 2. Rol: Busca el código exacto después de N°
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    
    # 3. Juzgado: Captura formatos civiles y de letras
    juz = re.search(r"(\d+º?\s+(?:EN\s+LO\s+CIVIL|Juzgado\s+de\s+Letras)\s+de\s+[\w\sÁÉÍÓÚñáéíóú]+)", texto, re.IGNORECASE)
    
    # 4. Solicitante: Limpia las comillas del nombre
    solic = re.search(r"representación(?:\s+judicial)?\s+(?:según\s+se\s+acreditará\s+de|de)\s+([^,.\n]+)", texto, re.IGNORECASE)
    solicitante_final = solic.group(1).replace('“', '').replace('”', '').replace('"', '').strip() if solic else "No detectado"

    # 5. Fechas
    # Publicación: Encabezado del Diario Oficial
    f_pub = re.search(r"(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto)
    
    # Solicitud Mensura: Fecha de manifestación citada
    f_sol_m = re.search(r"manifestadas\s+with\s+fecha\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    if not f_sol_m: # Alternativa para Valentina 2
        f_sol_m = re.search(r"manifestadas\s+con\s+fecha\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    
    # Mensura (Resolución): Al final junto a la ciudad
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar),\s+([a-záéíóúüñ\s]+de\s+[a-záéíóúüñ]+\s+de\s+dos\s+mil\s+[a-záéíóúüñ\s]+)", texto, re.IGNORECASE)

    return {
        "Propiedad": prop.group(1).strip() if prop else "No detectado",
        "Rol": rol.group(1).strip() if rol else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Solicitante": solicitante_final,
        "Comuna": "Copiapó" if "Copiapó" in texto else "La Serena",
        "CVE": re.search(r"CVE\s+(\d+)", texto).group(1) if re.search(r"CVE\s+(\d+)", texto) else "No detectado",
        "F_Sol_Mensura": f_sol_m.group(1) if f_sol_m else "No detectado",
        "F_Mensura": f_res.group(1).strip() if f_res else "No detectado",
        "F_Publicacion": f_pub.group(1) if f_pub else "No detectado",
        "Huso": "19"
    }

def extraer_coordenadas(texto):
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]+)\s+([\d\.\,]+)"
    coincidencias = re.findall(patron, texto)
    return [(float(c[2].replace(".", "").replace(",", ".")), float(c[1].replace(".", "").replace(",", "."))) for c in coincidencias]

st.title("⚒️ Sistema de Fichas Mineras Pro")
archivo_pdf = st.file_uploader("Sube el PDF de Mensura", type=["pdf"])

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        texto = "".join([p.extract_text() for p in pdf.pages])
    
    datos = extraer_datos_mineros(texto)
    puntos = extraer_coordenadas(texto)
    
    if puntos:
        st.success(f"✅ Ficha generada: {datos['Propiedad']}")
        st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
        
        # Generar Excel
        buffer_ex = BytesIO()
        with pd.ExcelWriter(buffer_ex, engine='xlsxwriter') as writer:
            pd.DataFrame([datos]).to_excel(writer, sheet_name='Ficha_Tecnica', index=False)
            pd.DataFrame(puntos, columns=['Este (X)', 'Norte (Y)']).to_excel(writer, sheet_name='Coordenadas', index=False)
        st.download_button("📥 Descargar Excel Completo", buffer_ex.getvalue(), f"Ficha_{datos['Propiedad']}.xlsx")
        
        # Generar Shapefile
        if len(puntos) >= 3:
            poly = Polygon(puntos)
            gdf = gpd.GeoDataFrame([datos], geometry=[poly], crs="EPSG:32719")
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                gdf.to_file("temp.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    if os.path.exists(f"temp{ext}"): zf.write(f"temp{ext}", arcname=f"{datos['Propiedad']}{ext}")
            st.download_button("🌍 Descargar Shapefile", zip_buf.getvalue(), f"GIS_{datos['Propiedad']}.zip")
