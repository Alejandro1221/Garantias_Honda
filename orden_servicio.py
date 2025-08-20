import re
import fitz
import pytesseract
import io
from PIL import Image
from ia_client import extraer_descripcion_falla
import threading

from busqueda_motor import (
    extraer_motor_cerca_vin,
    obtener_modelo,
    obtener_casa_matriz,
    obtener_cobro_casamatriz,
    obtener_responsable,
)

def extraer_vin(texto: str) -> str:
    texto = texto.upper()
    patrones = [
        r"VIN[:\s-]*([A-HJ-NPR-Z0-9]{17})",
        r"CHASIS[:\s-]*([A-HJ-NPR-Z0-9]{17})",
        r"\b([A-HJ-NPR-Z0-9]{17})\b",
    ]
    for patron in patrones:
        m = re.search(patron, texto)
        if m:
            return m.group(1)
    return "No detectado"

def _normalizar_motor(s: str) -> str:
    if not s:
        return s
    s = s.upper().replace("—","-").replace("–","-")  # guiones raros → '-'
    # Cambios solo cuando hay dígitos cerca (evita tocar letras puras)
    s = re.sub(r'(?<=\d)O|O(?=\d)', '0', s)  # O junto a dígitos → 0
    s = re.sub(r'(?<=\d)I|I(?=\d)', '1', s)  # I junto a dígitos → 1
    s = re.sub(r'(?<=\d)S|S(?=\d)', '5', s)  # S junto a dígitos → 5 (por si acaso)
    return s

def extraer_texto_dpi_alto(ruta_pdf: str, pagina_index: int, dpi: int = 700) -> str:
    # Render de la página a 700 DPI y OCR con eng+spa tal como lo tenías
    with fitz.open(ruta_pdf) as doc:
        pagina = doc[pagina_index]
        pix = pagina.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang="eng+spa")

def procesar_orden(
        archivo_pdf: str, 
        campos, 
        area_texto, 
        pagina_index: int = 0,
        *,
        imagen_pagina=None,     # <- para que no truene al recibirlo
        texto_ocr=None,         # <- idem
        lang: str = "eng+spa",):
    # OCR de página completa a 700 DPI (igual que antes)
    texto_ocr = extraer_texto_dpi_alto(archivo_pdf, pagina_index, dpi=700)

    # Muestra el OCR en el área de texto
    area_texto.delete("1.0", "end")
    area_texto.insert("end", texto_ocr)

    # VIN
    vin = extraer_vin(texto_ocr)
    campos[8].delete(0, "end")
    if vin != "No detectado":
        campos[8].insert(0, vin)

            # --- Lanzar IA en segundo plano para "Descripción de la falla" ---
    def _rellenar_desc_async(texto, campos_ref, area_ref):
        try:
            desc = extraer_descripcion_falla(texto)
            if desc:
                # Actualizar el Entry desde el hilo principal
                area_ref.after(0, lambda: (
                    campos_ref[23].delete(0, "end"),
                    campos_ref[23].insert(0, desc)
                ))
        except Exception as e:
            print("[IA] Error:", e)

    threading.Thread(
        target=_rellenar_desc_async,
        args=(texto_ocr, campos, area_texto),
        daemon=True
    ).start()


    # MOTOR cerca del VIN
    motor = extraer_motor_cerca_vin(texto_ocr, vin if vin != "No detectado" else "")
    campos[9].delete(0, "end")
    if motor != "No detectado":
        motor = _normalizar_motor(motor)
        campos[9].insert(0, motor)

        # Derivados del motor
        modelo = obtener_modelo(motor)
        campos[12].delete(0, "end")
        if modelo:
            campos[12].insert(0, modelo)

        casamatriz = obtener_casa_matriz(motor)
        campos[13].delete(0, "end")
        if casamatriz:
            campos[13].insert(0, casamatriz)

        cobro_casamatriz = obtener_cobro_casamatriz(motor)
        campos[25].delete(0, "end")
        if cobro_casamatriz:
            campos[25].insert(0, cobro_casamatriz)

        responsable = obtener_responsable(motor)
        campos[26].delete(0, "end")        
        if responsable:
            campos[26].insert(0, responsable)


