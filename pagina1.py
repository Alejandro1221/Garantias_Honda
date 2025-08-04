import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import pytesseract
import fitz
import io

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\practicante1servicio\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

def leer_pdf_con_ocr(ruta_pdf):
    texto_total = ""
    imagenes = []

    doc = fitz.open(ruta_pdf)
    for pagina in doc:
        pix = pagina.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        imagenes.append(img)

        texto = pytesseract.image_to_string(img, lang="eng")
        texto_total += texto + "\n"
    
    return texto_total, imagenes[0]  

def subir_pdf():
    ruta = filedialog.askopenfilename(
        title="Seleccionar PDF",
        filetypes=[("Archivos PDF", "*.pdf")]
    )
    if ruta:
        texto, imagen = leer_pdf_con_ocr(ruta)
        area_texto.delete("1.0", tk.END)
        area_texto.insert(tk.END, texto)

        mostrar_imagen(imagen)

        # Opcional: puedes procesar texto para llenar campos automáticos luego

def mostrar_imagen(imagen_pil):
    imagen_pil = imagen_pil.resize((400, 500))
    imagen_tk = ImageTk.PhotoImage(imagen_pil)
    etiqueta_imagen.config(image=imagen_tk)
    etiqueta_imagen.image = imagen_tk


def guardar_datos():
    datos = [campo.get() for campo in campos]
    print("Datos guardados:", datos)

#VENTANA PRINCIPAL 
ventana = tk.Tk()
ventana.title("GARANTÍA - Lector PDF OCR")
ventana.geometry("1200x700")

#BOTÓN SUBIR
btn_subir = tk.Button(ventana, text="SUBIR", command=subir_pdf, bg="lightblue", width=10)
btn_subir.place(x=30, y=100)

#TEXTO EXTRAÍDO
area_texto = tk.Text(ventana, wrap="word", width=40, height=20)
area_texto.place(x=130, y=80)

scroll_texto = tk.Scrollbar(ventana, command=area_texto.yview)
scroll_texto.place(x=130 + 400, y=80, height=320)
area_texto.config(yscrollcommand=scroll_texto.set)

#IMAGEN PDF
etiqueta_imagen = tk.Label(ventana, bg="white", width=400, height=500)
etiqueta_imagen.place(x=130, y=420)

#CAMPOS DE TEXTO
campos = []
for i in range(6):
    entry = tk.Entry(ventana, width=30, bg="white", font=("Arial", 10))
    entry.place(x=600, y=100 + i*40)
    campos.append(entry)

#BOTÓN GUARDAR
btn_guardar = tk.Button(ventana, text="GUARDA", command=guardar_datos, bg="lightblue", width=12)
btn_guardar.place(x=600, y=100 + 6*40)

ventana.mainloop()
