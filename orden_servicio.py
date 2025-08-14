import re
import fitz
import pytesseract
import io
from PIL import Image

from busqueda_motor import (
    extraer_motor_cerca_vin,
    obtener_modelo,
    obtener_casa_matriz,
    obtener_cobro_casamatriz,
    obtener_responsable,
)

def extraer_vin(texto):
    texto = texto.upper()
    patrones = [
        r"VIN[:\s-]*([A-HJ-NPR-Z0-9]{17})",
        r"CHASIS[:\s-]*([A-HJ-NPR-Z0-9]{17})",
        r"\b([A-HJ-NPR-Z0-9]{17})\b"
    ]
    for patron in patrones:
        m = re.search(patron, texto)
        if m:
            return m.group(1)
    return "No detectado"

def extraer_texto_dpi_alto(ruta_pdf, pagina_index, dpi=150):
    # cierra el PDF correctamente
    with fitz.open(ruta_pdf) as doc:
        pagina = doc[pagina_index]
        pix = pagina.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang="eng+spa")

def procesar_orden(archivo_pdf, campos, area_texto, pagina_index=0):
    # Usa el mismo OCR (DPI alto) para VIN y MOTOR
    texto_ocr = extraer_texto_dpi_alto(archivo_pdf, pagina_index, dpi=700)

    area_texto.delete("1.0", "end")
    area_texto.insert("end", texto_ocr)

    # VIN 
    vin = extraer_vin(texto_ocr)
    if vin != "No detectado":
        campos[8].delete(0, "end")
        campos[8].insert(0, vin)

    motor = extraer_motor_cerca_vin(texto_ocr, vin if vin != "No detectado" else "")
    if motor != "No detectado":
        campos[9].delete(0, "end")     
        campos[9].insert(0, motor)

        modelo = obtener_modelo(motor)
        if modelo:
            campos[12].delete(0, "end")  
            campos[12].insert(0, modelo)

        casamatriz = obtener_casa_matriz(motor)
        if casamatriz:
            campos[13].delete(0, "end")  
            campos[13].insert(0, casamatriz)
        
        cobro_casamatriz = obtener_cobro_casamatriz(motor)
        if cobro_casamatriz:
            campos[25].delete(0, "end")  
            campos[25].insert(0, cobro_casamatriz)
        
        responsable = obtener_responsable(motor)
        if responsable:
            campos[26].delete(0, "end")  
            campos[26].insert(0, responsable)

      
