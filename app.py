import streamlit as st
import pandas as pd
import pdfplumber
import re
import geopandas as gpd
from shapely.geometry import Polygon
from io import BytesIO
import zipfile
import os

# --- (Funciones de normalizar_fecha y extraer_datos permanecen igual que la versión anterior) ---

def normalizar_fecha(texto):
    MESES = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
             "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"}
    NUMEROS = {"uno": "01", "dos": "02", "tres": "03", "cuatro": "04", "cinco": "05", "seis": "06", "siete": "07", "ocho": "08", 
               "nueve": "09", "diez": "10", "once": "11", "doce": "12", "trece": "13", "catorce": "14", "quince": "15", 
               "dieciséis": "16", "diecisiete": "17", "dieciocho": "18", "diecinueve": "19", "veinte": "20", "veintiuno": "21", 
               "veintidós": "22", "veintitrés": "23", "veinticuatro": "24", "veinticinco": "25", "veintiséis": "26", 
               "veintisiete": "27", "veintiocho": "28", "veintinueve": "29", "treinta": "30", "treintiuno": "31"}
    if not texto or "No detectado" in texto: return "No detectado"
    t = texto.lower().replace("  ", " ")
    m1 = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", t)
    if m1:
        dia, mes, año = m1.groups()
        return f"{dia.zfill(2)}/{MESES.get(mes, '01')}/{año}"
    m2 = re.search(r"(\w+)\s+de\s+(\w+)\s+de\s+dos\s+mil\s+(\w+)", t)
    if m2:
        dia_txt, mes_txt, año_txt = m2.groups()
        return f"{NUMEROS.get(dia_txt, '01')}/{MESES.get(mes_txt, '01')}/20{NUMEROS.get(año_txt, '26')}"
    return texto

def extraer_datos_mineros(texto_sucio):
    texto = re.sub(r'\s+', ' ', texto_sucio).strip()
    prop = re.search(r'(?:denominada|pertenencia|pertenencias)\s+[“"“]([^”"”]+)[”"”]', texto, re.IGNORECASE)
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    juz = re.search(r"(?:S\.J\.L\.|JUZGADO)\s*(\d+.*? (?:COPIAPÓ|LA SERENA|VALLENAR|SANTIAGO))", texto, re.IGNORECASE)
    solic = re.search(r"representación(?:.*? de| de)\s+([^,]+?)(?:\s*,|\s+individualizada|\s+ya|$)", texto, re.IGNORECASE)
    f_pub = re.search(r"(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto)
    f_sol_m = re.search(r"(?:manifestadas|presentación)\s+con\s+fecha\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar),\s+([a-z\s]+de\s+[a-z]+\s+de\s+dos\s+mil\s+[a-z]+)", texto, re.IGNORECASE)

    return {
        "Propiedad": prop.group(1).strip() if prop else "VALENTINA 2",
        "Rol": rol.group(1).strip() if rol else "Sin Rol",
        "Juzgado": juz.group(1).strip() if juz else "Sin Juzgado",
        "Solicitante": solic.group(1).strip().replace('“', '').replace('”', '') if solic else "Sin Solicitante",
        "Comuna": "Copiapó" if "COPIAPÓ" in texto.upper() else "La Serena",
        "F_Solicit": normalizar_fecha(f_sol_m.group(1) if f_sol_m else ""),
        "F_Resolu": normalizar_fecha(f_res.group(1).strip() if f_res else ""),
        "F_Public": normalizar_fecha(f_pub.group(1) if f_pub else ""),
        "Huso": "19S"
    }

def extraer_coordenadas(texto):
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]+)\s+([\d\.\,]+)"
    coincidencias = re.findall(patron, texto)
    return [(float(c[2].replace(".", "").replace(",", ".")), float(c[1].replace(".", "").replace(",", "."))) for c in coincidencias]

# --- INTERFAZ STREAMLIT ---
st.title("⚒️ Sistema Minero Profesional (Excel + SIG)")
archivo_pdf = st.file_uploader("Sube el PDF para generar Ficha y Shapefile", type=["pdf"])

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        texto_completo = " ".join([p.extract_text() for p in pdf.pages])
    
    datos = extraer_datos_mineros(texto_completo)
    puntos = extraer_coordenadas(texto_completo)
    
    if datos:
        st.success(f"✅ Procesado: {datos['Propiedad']}")
        st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
        
        col1, col2 = st.columns(2)
        
        # EXCEL
        with col1:
            out_ex = BytesIO()
            with pd.ExcelWriter(out_ex, engine='xlsxwriter') as writer:
                pd.DataFrame([datos]).to_excel(writer, sheet_name='Ficha', index=False)
                pd.DataFrame(puntos, columns=['Este', 'Norte']).to_excel(writer, sheet_name='Puntos', index=False)
            st.download_button("📥 Descargar Excel", out_ex.getvalue(), f"{datos['Propiedad']}.xlsx")

        # SHAPEFILE CON ATRIBUTOS (THE JOIN)
        with col2:
            if len(puntos) >= 3:
                poligono = Polygon(puntos + [puntos[0]])
                # Aquí ocurre el 'Join': Pasamos el diccionario 'datos' al GeoDataFrame
                gdf = gpd.GeoDataFrame([datos], geometry=[poligono], crs="EPSG:32719")
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zf:
                    # Guardamos con un nombre corto para evitar errores en el DBF
                    gdf.to_file("export.shp")
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        zf.write(f"export{ext}", arcname=f"{datos['Propiedad']}{ext}")
                        os.remove(f"export{ext}")
                st.download_button("🌍 Descargar Shapefile (con Datos)", zip_buffer.getvalue(), f"SIG_{datos['Propiedad']}.zip")
