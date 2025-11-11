import re
import pandas as pd

def extraer_nits(texto):
    """Extrae todos los NITs del texto usando expresiones regulares"""
    return re.findall(r'\b\d{7,10}-?\d?\b', texto)

def cargar_concesionarios(path="Agencias.xlsx"):
    """Carga el Excel con NITs válidos, nombre del concesionario y regional"""
    df = pd.read_excel(path)
    df.columns = df.columns.str.upper().str.strip()  # Normaliza nombres de columnas
    concesionarios = {}  # Mapa de NIT → (Razón Social, Regional)
    for _, row in df.iterrows():
        nit = str(row["NIT"]).replace("-", "").strip()
        razon = str(row["RAZON SOCIAL"]).strip()
        regional = str(row["REGIONAL"]) if "REGIONAL" in df.columns else ""
        concesionarios[nit] = (razon, regional)
    return concesionarios

def buscar_nit_valido(texto_factura, texto_orden, concesionarios):
    """Busca un NIT presente en los textos que esté en la lista de concesionarios"""
    posibles_nits = extraer_nits(texto_factura + "\n" + texto_orden)
    for nit in posibles_nits:
        nit_limpio = nit.replace("-", "").strip()
        for valido in concesionarios:
            if nit_limpio.startswith(valido):
                razon_social, regional = concesionarios[valido]
                return valido, razon_social, regional
    return None, None, None
