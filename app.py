def calcular_vertices_y_poly(este_pm, norte_pm, hectareas):
    # Determinamos el largo del lado (raíz cuadrada de superficie en m2)
    # Ejemplo: 100 ha = 1.000.000 m2 -> Lado = 1.000m
    lado = (hectareas * 10000)**0.5
    distancia = lado / 2
    
    v1 = (este_pm - distancia, norte_pm + distancia) # Noroeste
    v2 = (este_pm + distancia, norte_pm + distancia) # Noreste
    v3 = (este_pm + distancia, norte_pm - distancia) # Sureste
    v4 = (este_pm - distancia, norte_pm - distancia) # Suroeste
    
    # Creamos el polígono para el Shapefile
    poly = Polygon([v1, v2, v3, v4, v1])
    
    vertices_dict = {
        "V1_E": v1[0], "V1_N": v1[1],
        "V2_E": v2[0], "V2_N": v2[1],
        "V3_E": v3[0], "V3_N": v3[1],
        "V4_E": v4[0], "V4_N": v4[1]
    }
    return poly, vertices_dict

# En la parte donde se muestra el resultado en Streamlit:
poly, v_coords = calcular_vertices_y_poly(res["PM_E"], res["PM_N"], res["Hectareas"])
st.subheader("📍 Coordenadas de los Vértices (UTM)")
st.write(f"**V1 (NW):** {v_coords['V1_E']} E / {v_coords['V1_N']} N")
st.write(f"**V2 (NE):** {v_coords['V2_E']} E / {v_coords['V2_N']} N")
st.write(f"**V3 (SE):** {v_coords['V3_E']} E / {v_coords['V3_N']} N")
st.write(f"**V4 (SW):** {v_coords['V4_E']} E / {v_coords['V4_N']} N")
