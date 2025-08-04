import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\practicante1servicio\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

def leer_pdf_ocr(pdf_file):
    texto_total = ""
    doc = fitz.open(pdf_file)
    
    for pagina in doc:
        pix = pagina.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        
        texto_total += pytesseract.image_to_string(img, lang="eng") + "\n"  
        
    return texto_total

pdf_texto = leer_pdf_ocr("prueba10.pdf")

print("TEXTO DETECTADO DEL PDF 2")
print(pdf_texto)
