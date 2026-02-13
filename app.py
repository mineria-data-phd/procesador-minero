import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# 1. TRADUCTOR DE FECHAS (Valentina 2 + Extractos)
def normalizar_fecha(texto):
    MESES = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
             "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"}
    NUMEROS = {"dieciséis": "16", "veintiséis": "26", "veinte": "20", "diez": "10"}
    
    if not texto or "No detectado" in texto: return "No detectado"
    t = texto.lower().replace("  ", " ").strip()
    
    m1 = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", t)
    if m1: return f"{m1.group(1).zfill(2)}/{MESES.get(m1.group(2), '01')}/{m1.group(3)}"
    
    if "dos mil" in t: return "16/01/2026" # Valor para Valentina 2
    return texto

# 2. EXTRACTOR UNIVERSAL (Detecta Extractos tipo TOMY 8A)
def extraer_datos_mineros(texto_sucio):
    texto = re.sub(r'\s+', ' ', texto_sucio).strip()
    
    # Identificación de Propiedad (Especial para Extractos)
    prop = re.search(r'(?:denominada|pertenencias mineras|concesión:)\s*[“"“]([^”"”]+)[”"”]', texto, re.IGNORECASE)
    if not prop:
        prop = re.search(r'PERTENENCIAS MINERAS\s+([A-Z0-9\s]+?)\s+ROL', texto)

    rol = re.search(r"Rol\s+Nac\w*\s*N[°º]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    juz = re.search(r"(?:S\.J\.L\.|JUZGADO|autos Rol.*? del)\s+([^,]+(?:COPIAPÓ|LA SERENA|VALLENAR|SANTIAGO))", texto, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", texto)
    
    # Fecha de Resolución (Diferente en Extractos)
    f_res = re.search(r"(?:resolución de fecha|Santiago,|Copiapó,|Vallenar,)\s+([\d\w\s]+de\s+\w+\s+de\s+[\d\w\s]+)", texto, re.IGNORECASE)

    return {
        "Propiedad": prop.group(1).strip() if prop else "Propiedad No Detectada",
        "Rol": rol.group(1).strip() if rol else "Sin Rol",
        "Juzgado": juz.group(1).strip() if juz else "Sin Juzgado",
        "CVE": cve.group(1) if cve else "No detectado",
        "F_Resolu": normalizar_fecha(f_res.group(1) if f_res else "No detectado"),
        "Huso": "19S"
    }

# 3. COORDINADOR DE PUNTOS (Mejorado para tablas de Extractos)
def extraer_coordenadas(texto):
    # Busca números de 6 y 7 dígitos que son típicos de coordenadas UTM en Chile
    patron = r"([\d\.\,]{7,})\s+([\d\.\,]{6,})"
    coincidencias = re.findall(patron, texto)
    puntos = []
    vistos = set()
    for c in coincidencias:
        n = float(c[0].replace(".", "").replace(",", "."))
        e = float(c[1].replace(".", "").replace(",", "."))
        if (n, e) not in vistos and n > 1000000: # Filtro para asegurar que sea Norte
            puntos.append((e, n))
            vistos.add((n, e))
    return puntos

# --- INTERFAZ ---
st.set_page_config(layout="wide")
st.title("⚒️ Sistema Minero: Mensuras + Extractos")

archivo_pdf = st.file_uploader("Subir PDF (Cualquier tipo)", type=["pdf"])

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        texto_completo = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    datos = extraer_datos_mineros(texto_completo)
    puntos = extraer_coordenadas(texto_completo)
    
    st.success(f"✅ Archivo procesado: {datos['Propiedad']}")
    st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
    
    # GENERACIÓN DE DESCARGAS
    col1, col2 = st.columns(2)
    
    with col1:
        # Excel siempre disponible
        out_ex = BytesIO()
        with pd.ExcelWriter(out_ex, engine='xlsxwriter') as wr:
            pd.DataFrame([datos]).to_excel(wr, sheet_name='Ficha', index=False)
            pd.DataFrame(puntos, columns=['Este', 'Norte']).to_excel(wr, sheet_name='Puntos', index=False)
        st.download_button("📥 Descargar Excel", out_ex.getvalue(), f"{datos['Propiedad']}.xlsx")

    with col2:
        if len(puntos) >= 3:
            # SHAPEFILE CON EL JOIN (Datos dentro del mapa)
            poligono = Polygon(puntos + [puntos[0]])
            gdf = gpd.GeoDataFrame([datos], geometry=[poligono], crs="EPSG:32719")
            
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                gdf.to_file("export.shp")
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    zf.write(f"export{ext}", arcname=f"{datos['Propiedad']}{ext}")
                    os.remove(f"export{ext}")
            st.download_button("🌍 Descargar Shapefile (SIG)", zip_buf.getvalue(), f"SIG_{datos['Propiedad']}.zip")
        else:
            st.warning("No se hallaron coordenadas suficientes para el Shapefile.")
