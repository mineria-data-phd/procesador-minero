import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# --- 1. LÓGICA DE EXTRACCIÓN ROBUSTA ---
def extraer_todo_el_contenido(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        # Extraemos texto de todas las páginas
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    # Limpiamos el texto para búsquedas lineales
    t_limpio = re.sub(r'\s+', ' ', texto).strip()
    
    # --- FICHA TÉCNICA (Identidad) ---
    # 1. Propiedad: Buscamos entre comillas o después de "denominada"
    prop = re.search(r'(?:denominada|Concesión:|pertenencias mineras|denominadas)\s*[“"“]([^”"”]+)[”"”]', t_limpio, re.IGNORECASE)
    # 2. Rol Nacional: Captura el formato 00000-X000-0
    rol = re.search(r"Rol\s+(?:Nacional|N\.?º)\s*([A-Z0-9\-]+)", t_limpio, re.IGNORECASE)
    # 3. Juzgado: Captura desde el ordinal hasta la ciudad
    juzgado = re.search(r"((?:Primer|Segundo|Tercer|S\.J\.L\.)\s+Juzgado\s+[\w\s]+(?:Copiapó|Vallenar|Santiago|La Serena))", t_limpio, re.IGNORECASE)
    # 4. Solicitante: Quién pide la concesión
    solic = re.search(r"(?:solicitadas? por|representación de|presentada por)\s+([^,]+?)(?:\s*,|\s+individualizada|$)", t_limpio, re.IGNORECASE)
    # 5. CVE: El código de verificación
    cve = re.search(r"CVE\s+(\d+)", t_limpio)

    ficha = {
        "Propiedad": prop.group(1).strip() if prop else "No detectada",
        "Rol_Nac": rol.group(1).strip() if rol else "Sin Rol",
        "Juzgado": juzgado.group(1).strip() if juzgado else "No detectado",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "CVE": cve.group(1) if cve else "No detectado",
        "Tipo_PDF": "Extracto" if "EXTRACTO" in t_limpio.upper() else ("Mensura" if "MENSURA" in t_limpio.upper() else "Pedimento/Manifestación")
    }

    # --- GEOMETRÍA (Coordenadas UTM) ---
    puntos = []
    # Buscamos en el texto original (con saltos de línea) para leer tablas
    for linea in texto.split('\n'):
        # Filtro: Cualquier número que parezca coordenada (6 o 7 dígitos)
        # Esto captura los datos del extracto TOMY 8A aunque tengan comillas '"6.993.700,000"'
        nums = re.findall(r'(\d[\d\.\,]{5,12})', linea)
        if len(nums) >= 2:
            try:
                # Limpieza total de puntos y comas de miles/decimales
                v1 = float(nums[0].replace('.', '').replace(',', '.'))
                v2 = float(nums[1].replace('.', '').replace(',', '.'))
                
                norte = max(v1, v2)
                este = min(v1, v2)
                
                # Validación geográfica: Solo si está en el rango de Chile (Norte 6M-7M, Este 200k-800k)
                if 6000000 < norte < 8000000 and 200000 < este < 900000:
                    if (este, norte) not in puntos:
                        puntos.append((este, norte))
            except:
                continue

    return ficha, puntos

# --- 2. INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Motor Minero Universal", layout="wide")
st.title("⚒️ Extractor Total: Pedimentos, Mensuras y Extractos")
st.info("Sube cualquier tipo de PDF del Boletín Minero para generar el Excel y Shapefile con Join.")

archivos_subidos = st.file_uploader("Arrastra tus archivos aquí", type=["pdf"], accept_multiple_files=True)

if archivos_subidos:
    data_final = []
    geometrias = []
    
    for arc in archivos_subidos:
        ficha, vertices = extraer_todo_el_contenido(arc)
        ficha["Nombre_Archivo"] = arc.name
        data_final.append(ficha)
        
        # Generar Shapefile solo si hay coordenadas suficientes (polígono cerrado)
        if len(vertices) >= 3:
            pol = Polygon(vertices + [vertices[0]])
            gdf = gpd.GeoDataFrame([ficha], geometry=[pol], crs="EPSG:32719")
            geometrias.append(gdf)

    if data_final:
        df = pd.DataFrame(data_final)
        st.write("### 📊 Datos Extraídos")
        st.table(df) # Muestra el Excel antes de descargarlo
        
        col1, col2 = st.columns(2)
        with col1:
            # Excel
            buffer_ex = BytesIO()
            with pd.ExcelWriter(buffer_ex, engine='xlsxwriter') as wr:
                df.to_excel(wr, index=False)
            st.download_button("📥 Descargar Excel Consolidado", buffer_ex.getvalue(), "Consolidado_Minero.xlsx")
            
        with col2:
            # Shapefile Unificado
            if geometrias:
                gdf_total = pd.concat(geometrias)
                buffer_zip = BytesIO()
                with zipfile.ZipFile(buffer_zip, 'w') as zf:
                    gdf_total.to_file("export.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"export{ext}", arcname=f"Mapa_Mineria{ext}")
                        os.remove(f"export{ext}")
                st.download_button("🌍 Descargar Shapefile (Join SIG)", buffer_zip.getvalue(), "SIG_Minero.zip")
            else:
                st.warning("⚠️ No se detectaron coordenadas suficientes para generar el mapa.")
