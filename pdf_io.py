import io
import fitz
from PIL import Image
import pytesseract

PDF_DPI = 160

def leer_pdf_con_ocr(ruta_pdf, lang="eng+spa"):
    textos = []
    imagenes = []

    with fitz.open(ruta_pdf) as doc:
        for page in doc:
            t = (page.get_text("text") or "").strip()
            if t:
                textos.append(t)
                imagenes.append(None)
                continue

            pix = page.get_pixmap(dpi=PDF_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            imagenes.append(img)
            t = pytesseract.image_to_string(img, lang=lang, config="--oem 3 --psm 6") or ""
            textos.append(t.strip())

    return textos, imagenes

def leer_primera_pagina(ruta_pdf, lang="eng+spa"):
    with fitz.open(ruta_pdf) as doc:
        if len(doc) == 0:
            return ""
        page = doc[0]
        t = (page.get_text("text") or "").strip()
        if t:
            return t
        pix = page.get_pixmap(dpi=PDF_DPI)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        return (pytesseract.image_to_string(img, lang=lang, config="--oem 3 --psm 6") or "").strip()

def leer_pdf_aumentado(ruta_pdf, lang="eng+spa", dpi_retry=200):
    textos = []
    with fitz.open(ruta_pdf) as doc:
        for page in doc:
            # Si la página tiene texto embebido, úsalo directamente.
            t = (page.get_text("text") or "").strip()
            if t:
                textos.append(t)
                continue

            # OCR con resolución aumentada
            pix = page.get_pixmap(dpi=dpi_retry)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

            # Lectura con Tesseract en modo estándar
            t = pytesseract.image_to_string(
                img, lang=lang, config="--oem 3 --psm 6"
            ) or ""
            textos.append(t.strip())

    return textos
