import re

"""Extrae el número de factura Electronica"""
def extraer_numero_factura(texto):
    
    # Separar el texto por líneas para poder analizarlas individualmente
    lineas = texto.splitlines() 

    for i, linea in enumerate(lineas):
        ## Limpieza de espacios y conversión a mayúsculas para comparar más fácilmente
        l = linea.strip().upper()
        # Verificar si la línea contiene alguna de las frases clave relacionadas con facturas
        if "FACTURA ELECTRÓNICA" in l or "FACTURA DE VENTA" in l or "FACTURA" in l:
            
            match = re.search(r"[A-Z]{3,6}[-]?\d{3,6}", l)
            if match:
                return match.group().replace("-", "")
            
            if i + 1 < len(lineas):
                siguiente = lineas[i + 1].strip()
                #Expresión regular: 3 a 6 letras seguidas de 3 a 6 dígitos

                if re.match(r"^[A-Z]{3,6}[-]?\d{3,6}$", siguiente):
                    return siguiente.replace("-", "")

    # Si no se encontró en líneas cercanas, se buscan patrones directamente en todo el texto
    posibles = re.findall(r"\b[A-Z]{3,6}\d{3,6}\b", texto.upper())
    if posibles:
        return posibles[0]
    # Si no se detecta ningún patrón, retorna mensaje indicativo
    return "No detectado"


def extraer_fecha_emision(texto):
    lineas = texto.splitlines()

    patrones = [
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",                  # 01/08/2025 o 1/8/25
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",                    # 2025-08-01
        r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b",                # 01.08.2025
        r"\b\d{1,2} de [a-zA-Z]+ de \d{4}\b",            # 1 de agosto de 2025
        r"\b\d{1,2} [a-zA-Z]+ \d{4}\b",                  # 1 agosto 2025
    ]

    for linea in lineas:
        for patron in patrones:
            coincidencia = re.search(patron, linea, re.IGNORECASE)
            if coincidencia:
                return coincidencia.group()
    
    return "No detectado"

