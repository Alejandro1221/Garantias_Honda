from PIL import Image
import fitz  # PyMuPDF
import io

try:
    import pytesseract
except Exception:
    pytesseract = None  

PDF_DPI = 180

def leer_pdf_con_ocr(ruta_pdf, lang="eng+spa"):
    textos = []
    imagenes = []
    doc = fitz.open(ruta_pdf)
    for page in doc:
        # Render a imagen para el visor
        pix = page.get_pixmap(dpi=PDF_DPI)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        imagenes.append(img)

        # Texto embebido
        txt = page.get_text("text") or ""
        if not txt and pytesseract is not None:
            # Fallback OCR solo si no hay texto
            txt = pytesseract.image_to_string(img, lang=lang) or ""
        textos.append(txt)
    doc.close()
    return textos, imagenes
