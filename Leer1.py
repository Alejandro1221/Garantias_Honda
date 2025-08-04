import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\practicante1servicio\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"


imagen = Image.open("pruebaimg.png")
texto = pytesseract.image_to_string(imagen, lang="eng")


print(texto)