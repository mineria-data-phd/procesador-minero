import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# ==========================================
# 1. HERRAMIENTAS DE LIMPIEZA UNIVERSAL
# ==========================================
def limpiar_texto(t): 
    return re.sub(r'\s+', ' ', t).strip()

def extraer_coordenadas_tabla(texto_bloque):
    """Extrae coordenadas de un bloque, limpiando comillas y puntos"""
    puntos = []
    for linea in texto_bloque.split('\n'):
        nums = re.findall(r'(\d[\d\.\,]{5,12})', linea)
        if len(nums) >= 2:
            try:
                v1 = float(nums[0].replace('"', '').replace('.', '').replace(',', '.'))
                v2 = float(nums[1].replace('"', '').replace('.', '').replace(',', '.'))
                
                norte, este = (v1, v2) if v1 > v2 else (v2, v1)
                
                if 6000000 < norte < 8000000 and 200000 < este < 900000:
                    punto = {"Norte": norte, "Este": este}
                    if punto not in puntos:
                        puntos.append(punto)
            except: 
                continue
    return puntos

# ==========================================
# 2. MÓDULOS ESPECÍFICOS (LAS AUTOPISTAS)
# ==========================================

def procesar_mensura(texto_limpio, texto_crudo, archivo_nombre):
    prop = re.search(r'denominada\s*[“"“]([^”"”]+)[”"”]', texto_limpio, re.IGNORECASE)
    rol = re.search(r"Rol\s+(?:Nacional|N\.?º)\s*([A-Z0-9\-]+)", texto_limpio, re.IGNORECASE)
    juz = re.search(r"((?:Primer|Segundo|Tercer|S\.J\.L\.|Juzgado de Letras)[^\,]+)", texto_limpio, re.IGNORECASE)
    solic = re.search(r"(?:solicitadas? por|representación de)\s+([A-ZÁÉÍÓÚÑ\s\.\&]{3,40})(?:\s*,|\s+mensuradas)", texto_limpio, re.IGNORECASE)
    fecha = re.search(r"(\d{1,2}\s+de\s+[a-zA-Z]+\s+de\s+20\d{2})", texto_limpio)
    cve = re.search(r"CVE\s+(\d+)", texto_limpio)
    
    ficha = {
        "Tipo_PDF": "Mensura",
        "Archivo": archivo_nombre,
        "Propiedad": prop.group(1).strip() if prop else "No detectada",
        "Rol_Nac": rol.group(1).strip() if rol else "Sin Rol",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Fecha_Res": fecha.group(1) if fecha else "No detectada",
        "CVE": cve.group(1) if cve else "No detectado"
    }
    coordenadas = extraer_coordenadas_tabla(texto_crudo)
    return [ficha], [coordenadas]

def procesar_pedimento(texto_limpio, texto_crudo, archivo_nombre):
    solic = re.search(r"(?:solicitadas? por|presentada por)\s+([A-ZÁÉÍÓÚÑ\s\.\&]{3,40})(?:\s*,|\s+domiciliado)", texto_limpio, re.IGNORECASE)
    juz = re.search(r"((?:Primer|Segundo|Tercer|S\.J\.L\.|Juzgado de Letras)[^\,]+)", texto_limpio, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", texto_limpio)
    
    ficha = {
        "Tipo_PDF": "Pedimento",
        "Archivo": archivo_nombre,
        "Propiedad": "Ver coordenadas (Pedimento)",
        "Rol_Nac": "N/A en Pedimento",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Fecha_Res": "N/A",
        "CVE": cve.group(1) if cve else "No detectado"
    }
    coordenadas = extraer_coordenadas_tabla(texto_crudo)
    return [ficha], [coordenadas]

def procesar_extracto(texto_limpio, texto_crudo, archivo_nombre):
    fichas = []
    lista_coordenadas = []
    
    juz = re.search(r"((?:Primer|Segundo|Tercer|S\.J\.L\.|Juzgado de Letras)[^\,]+)", texto_limpio, re.IGNORECASE)
    solic = re.search(r"solicitadas por\s+([^,]+)", texto_limpio, re.IGNORECASE)
    fecha = re.search(r"resolución de fecha\s*(\d{1,2}\s+de\s+[a-zA-Z]+\s+de\s+20\d{2})", texto_limpio, re.IGNORECASE)
    cve = re.search(r"CVE\s+(\d+)", texto_limpio)
    
    prop_antigua = re.search(r'denominada\s*\(?s\)?\s*,\s*([^,]+),', texto_limpio, re.IGNORECASE)
    rol_antigua = re.search(r"Rol Nacional\s*([0-9\-A-Z]+)", texto_limpio, re.IGNORECASE)
    
    fichas.append({
        "Tipo_PDF": "Extracto (Afectada)",
        "Archivo": archivo_nombre,
        "Propiedad": prop_antigua.group(1).strip() if prop_antigua else "Antigua no detectada",
        "Rol_Nac": rol_antigua.group(1).strip() if rol_antigua else "Sin Rol",
        "Solicitante": "Ver texto PDF",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Fecha_Res": fecha.group(1) if fecha else "No detectada",
        "CVE": cve.group(1) if cve else "No detectado"
    })
    
    prop_nueva = re.search(r'mensura de autos\s*[“"“]([^”"”]+)[”"”]', texto_limpio, re.IGNORECASE)
    rol_nueva = re.search(r"Rol Nacional N[º°]?\s*([0-9\-A-Z]+)", texto_limpio, re.IGNORECASE)
    
    fichas.append({
        "Tipo_PDF": "Extracto (Nueva)",
        "Archivo": archivo_nombre,
        "Propiedad": prop_nueva.group(1).strip() if prop_nueva else "Nueva no detectada",
        "Rol_Nac": rol_nueva.group(1).strip() if rol_nueva else "Sin Rol",
        "Solicitante": solic.group(1).strip() if solic else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Fecha_Res": fecha.group(1) if fecha else "No detectada",
        "CVE": cve.group(1) if cve else "No detectado"
    })
    
    partes = texto_crudo.lower().split("mensura de autos")
    lista_coordenadas.append(extraer_coordenadas_tabla(partes[0]))
    
    if len(partes) > 1:
         lista_coordenadas.append(extraer_coordenadas_tabla(partes[1]))
    else:
         lista_coordenadas.append([])

    return fichas, lista_coordenadas

# ==========================================
# 3. EL CEREBRO ENRUTADOR
# ==========================================
def motor_enrutador(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto_crudo = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    texto_limpio = limpiar_texto(texto_crudo)
    
    if "EXTRACTO ART" in texto_limpio.upper():
        return procesar_extracto(texto_limpio, texto_crudo, pdf_file.name)
    elif "MENSURA" in texto_limpio.upper():
        return procesar_mensura(texto_limpio, texto_crudo, pdf_file.name)
    else:
        return procesar_pedimento(texto_limpio, texto_crudo, pdf_file.name)

# ==========================================
# 4. INTERFAZ DE USUARIO (STREAMLIT)
# ==========================================
st.set_page_config(page_title="Motor Minero Definitivo", layout="wide")
st.title("⚒️ Motor Minero Modular")
st.success("Arquitectura estável: Processa Pedimentos, Mensuras e Extractos sem omitir dados.")

archivos = st.file_uploader("Arraste aqui os seus arquivos PDF", type=["pdf"], accept_multiple_files=True)

if archivos:
    todas_las_fichas = []
    todas_las_coords = []
    geometrias_mapa = []
    
    with st.spinner("Processando documentos com precisão..."):
        for arc in archivos:
            fichas, lista_coords = motor_enrutador(arc)
            
            for i in range(len(fichas)):
                ficha_actual = fichas[i]
                coords_actuales = lista_coords[i] if i < len(lista_coords) else []
                
                todas_las_fichas.append(ficha_actual)
                
                for idx, pt in enumerate(coords_actuales):
                    todas_las_coords.append({
                        "Propiedad": ficha_actual["Propiedad"],
                        "Rol": ficha_actual["Rol_Nac"],
                        "Vértice": idx + 1,
                        "Norte": pt["Norte"],
                        "Este": pt["Este"]
                    })
                
                if len(coords_actuales) >= 3:
                    puntos_tuplas = [(p["Este"], p["Norte"]) for p in coords_actuales]
                    pol = Polygon(puntos_tuplas + [puntos_tuplas[0]])
                    geometrias_mapa.append(gpd.GeoDataFrame([ficha_actual], geometry=[pol], crs="EPSG:32719"))

    # APENAS MOSTRA AS FICHAS NA TELA (COORDENADAS REMOVIDAS DA INTERFACE)
    if todas_las_fichas:
        df_fichas = pd.DataFrame(todas_las_fichas)
        df_coords = pd.DataFrame(todas_las_coords)
        
        st.write("### 📊 Fichas Técnicas Detectadas")
        st.dataframe(df_fichas)
        
        # Botões de Download
        col1, col2 = st.columns(2)
        with col1:
            buf_excel = BytesIO()
            with pd.ExcelWriter(buf_excel, engine='xlsxwriter') as writer:
                df_fichas.to_excel(writer, sheet_name='Fichas', index=False)
                if not df_coords.empty:
                    df_coords.to_excel(writer, sheet_name='Coordenadas', index=False) # Continua exportando!
            st.download_button("📥 Baixar Excel (2 Abas)", buf_excel.getvalue(), "Reporte_Minero_Modular.xlsx")
            
        with col2:
            if geometrias_mapa:
                gdf_total = pd.concat(geometrias_mapa)
                buf_zip = BytesIO()
                with zipfile.ZipFile(buf_zip, 'w') as zf:
                    gdf_total.to_file("mapa_minero.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"mapa_minero{ext}", arcname=f"SIG_Minero{ext}")
                        os.remove(f"mapa_minero{ext}")
                st.download_button("🌍 Baixar Shapefile (SIG)", buf_zip.getvalue(), "SIG_Minero_Modular.zip")
