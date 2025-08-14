from Extractores import (
    extraer_numero_factura,
    extraer_fecha_emision,
    extraer_valor_total_factura
)
from BusquedaRef import buscar_referencias_en_texto
from nit import cargar_concesionarios, buscar_nit_valido

from PIL import Image
import pytesseract
import fitz
import io

def extraer_texto_dpi_alto(ruta_pdf, pagina_index, dpi=300):
    doc = fitz.open(ruta_pdf)
    pagina = doc[pagina_index]
    pix = pagina.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang="eng")

def procesar_factura(archivo_pdf, campos, area_texto, pagina_index=0):
    # Texto completo de la página con dpi alto (para mejores resultados en valores)
    texto_dpi_alto = extraer_texto_dpi_alto(archivo_pdf, pagina_index, dpi=300)

    area_texto.delete("1.0", "end")
    area_texto.insert("end", texto_dpi_alto)

    # Buscar referencias en el texto
    resultados = buscar_referencias_en_texto(texto_dpi_alto)
    if resultados:
        referencias = [r["Referencia"] for r in resultados]
        descripciones = [r["Descripcion"] for r in resultados]
        campos[21].delete(0, "end")
        campos[21].insert(0, ", ".join(referencias))
        campos[22].delete(0, "end")
        campos[22].insert(0, ", ".join(descripciones))

    # Número de factura con dpi menor (para mejor lectura de encabezados grandes)
    texto_dpi_factura = extraer_texto_dpi_alto(archivo_pdf, pagina_index, dpi=100)
    numero = extraer_numero_factura(texto_dpi_factura)
    campos[0].delete(0, "end")
    campos[0].insert(0, numero)

    # Valor total de factura
    valor_total = extraer_valor_total_factura(texto_dpi_alto)
    campos[29].delete(0, "end")
    campos[29].insert(0, valor_total)

    # Fecha de emisión
    fecha = extraer_fecha_emision(texto_dpi_alto)
    campos[32].delete(0, "end")
    campos[32].insert(0, fecha)

