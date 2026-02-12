import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
import xlsxwriter

st.set_page_config(page_title="Procesador Minero Profesional", layout="wide")

def limpiar_texto(t):
    # Une las palabras que el PDF separa en distintos renglones
    if not t: return ""
    return re.sub(r'\s+', ' ', t).strip()

def extraer_datos_mineros(texto_sucio):
    texto = limpiar_texto(texto_sucio)
    
    # 1. Propiedad (Valentina 2, Tibu 3, etc)
    prop = re.search(r'(?:denominada|pertenencia|pertenencias)\s+[“"“]([^”"”]+)[”"”]', texto, re.IGNORECASE)
    
    # 2. Rol
    rol = re.search(r"Rol\s+N[°º]?\s*([A-Z0-9\-]+)", texto, re.IGNORECASE)
    
    # 3. Juzgado (Captura 3º EN LO CIVIL DE COPIAPÓ)
    juz = re.search(r"(?:S\.J\.L\.|JUZGADO)\s*(\d+.*? (?:COPIAPÓ|LA SERENA|VALLENAR|SANTIAGO))", texto, re.IGNORECASE)
    
    # 4. Solicitante (Captura el nombre completo sin cortes)
    solic = re.search(r"representación(?:.*? de| de)\s+([^,]+?)(?:\s*,|\s+individualizada|\s+ya|$)", texto, re.IGNORECASE)

    # 5. Fechas
    f_pub = re.search(r"(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto)
    f_sol_m = re.search(r"(?:manifestadas|presentación)\s+con\s+fecha\s+(\d+\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    f_res = re.search(r"(?:Copiapó|La Serena|Santiago|Vallenar),\s+([a-z\s]+de\s+[a-z]+\s+de\s+dos\s+mil\s+[a-z]+)", texto, re.IGNORECASE)

    return {
        "Propiedad": prop.group(1).strip() if prop else "No detectado",
        "Rol": rol.group(1).strip() if rol else "No detectado",
        "Juzgado": juz.group(1).strip() if juz else "No detectado",
        "Solicitante": solic.group(1).strip().replace('“', '').replace('”', '') if solic else "No detectado",
        "Comuna": "Copiapó" if "COPIAPÓ" in texto.upper() else "La Serena",
        "CVE": re.search(r"CVE\s+(\d+)", texto).group(1) if re.search(r"CVE\s+(\d+)", texto) else "No detectado",
        "F_Sol_Mensura": f_sol_m.group(1) if f_sol_m else "No detectado",
        "F_Mensura": f_res.group(1).strip() if f_res else "No detectado",
        "F_Publicacion": f_pub.group(1) if f_pub else "No detectado",
        "Huso": "19"
    }

def extraer_coordenadas(texto):
    # Busca las coordenadas en la tabla
    patron = r"(?:V|L|PI)(\d*)\s+([\d\.\,]+)\s+([\d\.\,]+)"
    coincidencias = re.findall(patron, texto)
    puntos_limpios = []
    for c in coincidencias:
        norte = float(c[1].replace(".", "").replace(",", "."))
        este = float(c[2].replace(".", "").replace(",", "."))
        puntos_limpios.append({"Vértice": f"V{c[0]}" if c[0] else "V", "Norte (Y)": norte, "Este (X)": este})
    return puntos_limpios

st.title("⚒️ Sistema de Fichas Mineras Pro")
archivo_pdf = st.file_uploader("Sube el PDF de Mensura", type=["pdf"])

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + " "
    
    datos = extraer_datos_mineros(texto_completo)
    puntos = extraer_coordenadas(texto_completo)
    
    if datos:
        st.success(f"✅ Ficha procesada con éxito")
        # Mostrar resumen en pantalla
        st.table(pd.DataFrame(list(datos.items()), columns=["Campo", "Valor"]))
        
        # Crear Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pd.DataFrame([datos]).to_excel(writer, sheet_name='Ficha_Tecnica', index=False)
            if puntos:
                pd.DataFrame(puntos).to_excel(writer, sheet_name='Coordenadas', index=False)
        
        st.download_button(
            label="📥 Descargar Excel Completo",
            data=output.getvalue(),
            file_name=f"Ficha_{datos['Propiedad']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
