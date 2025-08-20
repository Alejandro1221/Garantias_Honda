from Extractores import (
    extraer_numero_factura,
    extraer_fecha_emision,
    extraer_valor_total_factura
)
from BusquedaRef import buscar_referencias_en_texto

from PIL import Image
import pytesseract
import fitz
import io

def _ocr_desde_pdf(ruta_pdf: str, pagina_index: int, dpi: int = 700, lang: str = "eng+spa") -> str:
    with fitz.open(ruta_pdf) as doc:
        if not (0 <= pagina_index < len(doc)):
            return ""
        pagina = doc[pagina_index]
        pix = pagina.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return pytesseract.image_to_string(img, lang=lang)

def _ocr_desde_imagen(img_base: Image.Image, dpi_objetivo: int = 300, lang: str = "eng") -> str:
    base_dpi = 180.0  # aprox del render base que usa tu app
    escala = max(0.5, min(dpi_objetivo / base_dpi, 2.0))  # límites para no explotar RAM
    w = max(1, int(img_base.width * escala))
    h = max(1, int(img_base.height * escala))
    img = img_base.resize((w, h), resample=Image.LANCZOS)
    return pytesseract.image_to_string(img, lang=lang)

def procesar_factura(
    archivo_pdf: str,
    campos,
    area_texto,
    pagina_index: int = 0,
    imagen_pagina: Image.Image = None,   
    texto_ocr: str = None, 
    texto_dpi_alto: str = None,          
    texto_dpi_bajo: str = None          
):
    if texto_ocr is not None and not texto_dpi_alto:
        texto_dpi_alto = texto_ocr
    if texto_dpi_alto is None:
        if imagen_pagina is not None:
            texto_dpi_alto = _ocr_desde_imagen(imagen_pagina, dpi_objetivo=300)
        else:
            texto_dpi_alto = _ocr_desde_pdf(archivo_pdf, pagina_index, dpi=300)
    
    area_texto.delete("1.0", "end")
    area_texto.insert("end", texto_dpi_alto)

    # Buscar referencias en el texto
    resultados = buscar_referencias_en_texto(texto_dpi_alto) or []
    if resultados:
        referencias = [r["Referencia"] for r in resultados]
        descripciones = [r["Descripcion"] for r in resultados]
        
        campos[21].delete(0, "end")
        campos[21].insert(0, ", ".join(referencias))
        
        campos[22].delete(0, "end")
        campos[22].insert(0, ", ".join(descripciones))

    if texto_dpi_bajo is None:
        if imagen_pagina is not None:
            texto_dpi_bajo = _ocr_desde_imagen(imagen_pagina, dpi_objetivo=100)
        else:
            texto_dpi_bajo = _ocr_desde_pdf(archivo_pdf, pagina_index, dpi=100)

    # Número de factura con dpi menor (para mejor lectura de encabezados grandes)
    numero = extraer_numero_factura(texto_dpi_bajo) or ""
    campos[0].delete(0, "end")
    campos[0].insert(0, numero)

    campos[3].delete(0, "end")
    campos[3].insert(0, numero)

    campos[3].delete(0, "end")
    campos[3].insert(0, numero)

    campos[28].delete(0, "end")
    campos[28].insert(0, numero) 

    # Valor total de factura
    valor_total = extraer_valor_total_factura(texto_dpi_alto) or ""
    campos[29].delete(0, "end")
    campos[29].insert(0, valor_total)

    # Fecha de emisión
    fecha = extraer_fecha_emision(texto_dpi_alto) or ""
    campos[32].delete(0, "end")
    campos[32].insert(0, fecha)

