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
    # Usamos pdfplumber para detectar tablas estructuradas mejor que con texto crudo
    for linea in texto_bloque.split('\n'):
        nums = re.findall(r'(\d[\d\.\,]{5,12})', linea)
        if len(nums) >= 2:
            try:
                # Limpiamos el número para que Python lo entienda matemáticamente
                v1 = float(nums[0].replace('"', '').replace('.', '').replace(',', '.'))
                v2 = float(nums[1].replace('"', '').replace('.', '').replace(',', '.'))
                
                # Ordenamos: el mayor es Norte, el menor es Este
                norte, este = (v1, v2) if v1 > v2 else (v2, v1)
                
                # Filtro geográfico estricto para Chile
                if 6000000 < norte < 8000000 and 200000 < este < 900000:
                    punto = {"Norte": norte, "Este": este}
                    if punto not in puntos:
                        puntos.append(punto)
            except: 
                continue
    return puntos

# ==========================================
# 2. MÓDULO EXCLUSIVO PARA EXTRACTOS
# ==========================================
def procesar_extracto_definitivo(texto_crudo, archivo_nombre):
    fichas = []
    lista_coordenadas = []
    
    # 0. Datos Comunes (CVE, Fecha, Juzgado)
    texto_limpio = limpiar_texto(texto_crudo)
    cve = re.search(r"CVE\s+(\d+)", texto_limpio)
    fecha = re.search(r"resolución de fecha\s*(\d{1,2}\s+de\s+[a-zA-Z]+\s+de\s+20\d{2})", texto_limpio, re.IGNORECASE)
    juz = re.search(r"([0-9º°N\.\s]+Juzgado\s+de\s+Letras\s+de\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+)", texto_limpio, re.IGNORECASE)
    
    # --- DIVISIÓN DEL TEXTO EN DOS SECCIONES ---
    # La frase "Las coordenadas de la mensura de autos" es el punto de corte exacto
    partes = texto_crudo.split("Las coordenadas de la mensura de autos")
    
    if len(partes) < 2:
        return [], [] # Si no se puede dividir, el documento no es un extracto estándar
        
    texto_antiguo = partes[0]
    texto_nuevo = partes[1]

    # --- 1. PROPIEDAD ANTIGUA (AFECTADA) ---
    prop_antigua = re.search(r'denominada\s*\(?s\)?\s*,\s*([^,]+),', texto_antiguo, re.IGNORECASE)
    rol_antigua = re.search(r"Rol Nacional\s*([0-9\-A-Z]+)", texto_antiguo, re.IGNORECASE)
    solic_antigua = re.search(r"perteneciente a\s+([^,]+),", texto_antiguo, re.IGNORECASE)
    
    fichas.append({
        "Tipo_Prop": "Afectada (Antigua)",
        "Propiedad": prop_antigua.group(1).strip() if prop_antigua else "Antigua no detectada",
        "Rol_Nac": rol_antigua.group(1).strip() if rol_antigua else "Sin Rol",
        "Solicitante": solic_antigua.group(1).strip() if solic_antigua else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Fecha_Res": fecha.group(1) if fecha else "No detectada",
        "CVE": cve.group(1) if cve else "No detectado",
        "Archivo": archivo_nombre
    })
    
    # --- 2. PROPIEDAD NUEVA (MENSUADA) ---
    prop_nueva = re.search(r'\"([^\"]+)\"\s*Rol Nacional', texto_nuevo, re.IGNORECASE)
    rol_nueva = re.search(r"Rol Nacional N[º°]?\s*([0-9\-A-Z]+)", texto_nuevo, re.IGNORECASE)
    solic_nueva = re.search(r"solicitadas por\s+([^,]+),", texto_crudo, re.IGNORECASE) # Solicitante suele estar arriba
    
    fichas.append({
        "Tipo_Prop": "Mensura (Nueva)",
        "Propiedad": prop_nueva.group(1).strip() if prop_nueva else "Nueva no detectada",
        "Rol_Nac": rol_nueva.group(1).strip() if rol_nueva else "Sin Rol",
        "Solicitante": solic_nueva.group(1).strip() if solic_nueva else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Fecha_Res": fecha.group(1) if fecha else "No detectada",
        "CVE": cve.group(1) if cve else "No detectado",
        "Archivo": archivo_nombre
    })
    
    # --- 3. COORDENADAS SEPARADAS ---
    lista_coordenadas.append(extraer_coordenadas_tabla(texto_antiguo))
    lista_coordenadas.append(extraer_coordenadas_tabla(texto_nuevo))

    return fichas, lista_coordenadas

# ==========================================
# 3. INTERFAZ DE USUARIO (STREAMLIT)
# ==========================================
st.set_page_config(page_title="Motor Minero FINAL", layout="wide")
st.title("⚒️ Motor Minero - Extractos Art. 83")
st.success("Analizando extractos y separando pertenencias antiguas de nuevas.")

archivos = st.file_uploader("Arrastra aquí tus archivos PDF Extracto", type=["pdf"], accept_multiple_files=True)

if archivos:
    todas_las_fichas = []
    todas_las_coords = []
    geometrias_mapa = []
    
    with st.spinner("Procesando con bisturí..."):
        for arc in archivos:
            with pdfplumber.open(arc) as pdf:
                texto_crudo = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            
            fichas, lista_coords = procesar_extracto_definitivo(texto_crudo, arc.name)
            
            # Asociar coordenadas a sus respectivas fichas para el Excel y el Mapa
            for i in range(len(fichas)):
                ficha_actual = fichas[i]
                coords_actuales = lista_coords[i] if i < len(lista_coords) else []
                
                todas_las_fichas.append(ficha_actual)
                
                # Preparar datos para la "Segunda Hoja" de Excel
                for idx, pt in enumerate(coords_actuales):
                    todas_las_coords.append({
                        "Propiedad": ficha_actual["Propiedad"],
                        "Rol": ficha_actual["Rol_Nac"],
                        "Vértice": idx + 1,
                        "Norte": pt["Norte"],
                        "Este": pt["Este"]
                    })
                
                # Generar polígono para el Shapefile
                if len(coords_actuales) >= 3:
                    puntos_tuplas = [(p["Este"], p["Norte"]) for p in coords_actuales]
                    # Cerrar el polígono
                    puntos_tuplas.append(puntos_tuplas[0])
                    pol = Polygon(puntos_tuplas)
                    geometrias_mapa.append(gpd.GeoDataFrame([ficha_actual], geometry=[pol], crs="EPSG:32719"))

    # MOSTRAR RESULTADOS
    if todas_las_fichas:
        df_fichas = pd.DataFrame(todas_las_fichas)
        df_coords = pd.DataFrame(todas_las_coords)
        
        st.write("### 📊 Fichas Técnicas Detectadas (Dos filas por Extracto)")
        st.dataframe(df_fichas)
        
        # Botones de Descarga
        col1, col2 = st.columns(2)
        with col1:
            buf_excel = BytesIO()
            with pd.ExcelWriter(buf_excel, engine='xlsxwriter') as writer:
                df_fichas.to_excel(writer, sheet_name='Fichas', index=False)
                if not df_coords.empty:
                    df_coords.to_excel(writer, sheet_name='Coordenadas', index=False)
            st.download_button("📥 Descargar Excel (2 Abas)", buf_excel.getvalue(), "Reporte_Extractos.xlsx")
            
        with col2:
            if geometrias_mapa:
                gdf_total = pd.concat(geometrias_mapa)
                buf_zip = BytesIO()
                with zipfile.ZipFile(buf_zip, 'w') as zf:
                    gdf_total.to_file("mapa_extractos.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"mapa_extractos{ext}", arcname=f"SIG_Extractos{ext}")
                        os.remove(f"mapa_extractos{ext}")
                st.download_button("🌍 Baixar Shapefile (SIG)", buf_zip.getvalue(), "SIG_Extractos.zip")
