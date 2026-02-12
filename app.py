import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

st.set_page_config(page_title="Prospecciones Mineras PRO", layout="wide")

def normalizar_fecha(texto):
    MESES = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
             "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"}
    if not texto: return ""
    t = texto.lower().strip()
    m_num = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", t)
    if m_num: return f"{m_num.group(1).zfill(2)}/{m_num.group(2).zfill(2)}/{m_num.group(3)}"
    m_txt = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", t)
    if m_txt:
        dia, mes, año = m_txt.groups()
        return f"{dia.zfill(2)}/{MESES.get(mes, '01')}/{año}"
    return texto

def extraer_datos_mineros(texto_sucio):
    texto = re.sub(r'\s+', ' ', texto_sucio).strip()
    
    # Identificación según documentos [cite: 107, 170]
    tipo = "EXTRACTO EM/EP" if "EXTRACTO ART. 83" in texto.upper() else "SOLICITUD MENSURA"
    prop = re.search(r'(?:pertenencias mineras|denominada)\s+[“"“]?([^”"”\n]+)[”"”]?', texto, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º.]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    juz = re.search(r"(?:S\.J\.L\.|JUZGADO|autos Rol N.º.*? del)\s+([^,]+(?:COPIAPÓ|LA SERENA|VALLENAR))", texto, re.IGNORECASE)
    solic = re.search(r"(?:representación judicial.*? de|solicitadas por)\s+([^,]+)", texto, re.IGNORECASE)
    
    # Fechas [cite: 151, 172]
    f_sentencia = re.search(r"resolución de fecha\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    f_publicacion = re.search(r"(?:Miércoles|Jueves|Viernes)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)

    return {
        "Tipo": tipo,
        "Propiedad": prop.group(1).strip() if prop else "No detectado",
        "Rol": rol.group(1).strip() if rol else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "Sentencia": normalizar_fecha(f_sentencia.group(1)) if f_sentencia else "",
        "Publicación": normalizar_fecha(f_publicacion.group(1)) if f_publicacion else "",
        "CVE": re.search(r"CVE\s+(\d+)", texto).group(1) if re.search(r"CVE\s+(\d+)", texto) else ""
    }

def extraer_coordenadas(texto):
    # Mejora para detectar tablas en Mensuras [cite: 111] y Extractos [cite: 177]
    patron = r"(?:V|L|PI|LI)(\d*)\s+([\d\.\,]+)\s+([\d\.\,]+)"
    coincidencias = re.findall(patron, texto)
    puntos = []
    vistos = set()
    for c in coincidencias:
        norte = float(c[1].replace(".", "").replace(",", "."))
        este = float(c[2].replace(".", "").replace(",", "."))
        # Evitar duplicados si hay dos tablas iguales en el PDF
        if (norte, este) not in vistos:
            puntos.append((este, norte))
            vistos.add((norte, este))
    return puntos

# --- INTERFAZ ---
st.title("⚒️ Prospecciones Mineras: Procesador Oficial")

archivo_pdf = st.file_uploader("Sube el PDF de Mensura o Extracto", type=["pdf"])

if archivo_pdf:
    try:
        with pdfplumber.open(archivo_pdf) as pdf:
            texto_completo = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
        datos = extraer_datos_mineros(texto_completo)
        puntos = extraer_coordenadas(texto_completo)
        
        if datos:
            st.success(f"✅ Archivo procesado correctamente")
            st.subheader("Datos Extraídos")
            st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
            
            if len(puntos) >= 3:
                # Generación de Shapefile con Atributos (Join)
                poligono = Polygon(puntos + [puntos[0]])
                gdf = gpd.GeoDataFrame([datos], geometry=[poligono], crs="EPSG:32719")
                
                # ZIP de descarga
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zf:
                    gdf.to_file("temp_shp.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"temp_shp{ext}", arcname=f"{datos['Propiedad']}{ext}")
                        os.remove(f"temp_shp{ext}")
                
                st.download_button("🌍 Descargar Shapefile para ArcGIS", zip_buffer.getvalue(), f"GIS_{datos['Propiedad']}.zip")
            else:
                st.warning("⚠️ Se detectaron datos, pero no se encontraron coordenadas suficientes para el polígono.")
                
    except Exception as e:
        st.error(f"❌ Ocurrió un error al procesar el PDF: {e}")
        st.info("Asegúrate de que el PDF sea un documento original del Diario Oficial.")
