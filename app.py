import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from factura import procesar_factura
from orden_servicio import procesar_orden
import fitz
import io
import pytesseract

# Configurar Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\\Users\\practicante1servicio\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe"

from nit import cargar_concesionarios, buscar_nit_valido
from datetime import datetime

# Variables globales
factura_actual = ""
orden_actual = ""
factura_paginas = []
factura_textos = []
orden_paginas = []
orden_textos = []
indice_actual = 0
modo_vista = "factura"  
zoom_nivel = 0.4
concesionarios = cargar_concesionarios("Agencias.xlsx")

def zoom_in(event=None):
    global zoom_nivel
    zoom_nivel *= 1.1  # aumenta 10%
    mostrar_pagina(indice_actual)

def zoom_out(event=None):
    global zoom_nivel
    zoom_nivel /= 1.1  # reduce 10%
    mostrar_pagina(indice_actual)


# OCR
def leer_pdf_con_ocr(ruta_pdf):
    texto_por_pagina = []
    imagenes = []
    doc = fitz.open(ruta_pdf)
    for pagina in doc:
        pix = pagina.get_pixmap(dpi=180)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        imagenes.append(img)
        texto = pytesseract.image_to_string(img, lang="eng")
        texto_por_pagina.append(texto)
    return texto_por_pagina, imagenes
def mostrar_pagina(index):
    global modo_vista

    if modo_vista == "factura":
        if not factura_paginas or index >= len(factura_paginas):
            return
        imagen = factura_paginas[index]
        texto = factura_textos[index]
        procesar_factura(factura_actual, campos, area_texto, pagina_index=index)
    elif modo_vista == "orden":
        if not orden_paginas or index >= len(orden_paginas):
            return
        imagen = orden_paginas[index]
        texto = orden_textos[index]
        procesar_orden(orden_actual, campos, area_texto, pagina_index=index)
    else:
        return

    ancho = int(imagen.width * zoom_nivel)
    alto = int(imagen.height * zoom_nivel)
    imagen_zoom = imagen.resize((ancho, alto))
    imagen_tk = ImageTk.PhotoImage(imagen_zoom)

    etiqueta_imagen.config(image=imagen_tk)
    etiqueta_imagen.image = imagen_tk
    canvas_imagen.config(scrollregion=canvas_imagen.bbox("all"))

    area_texto.delete("1.0", tk.END)
    area_texto.insert("1.0", texto)

    # Buscar NIT válido (al final del todo)
    texto_factura = "\n".join(factura_textos) if factura_textos else ""
    texto_orden = "\n".join(orden_textos) if orden_textos else ""
    nit, nombre, regional = buscar_nit_valido(texto_factura, texto_orden, concesionarios)

    if nit:
        campos[4].delete(0, "end")
        campos[4].insert(0, nit)

        campos[5].delete(0, "end")
        campos[5].insert(0, nombre)

        campos[6].delete(0, "end")
        campos[6].insert(0, regional)  

    # Fecha actual en campo "Fecha de revisión"
    fecha_actual = datetime.today().strftime('%Y-%m-%d')
    campos[19].delete(0, "end")
    campos[19].insert(0, fecha_actual)

# Funciones principales
def subir_factura():
    global factura_paginas, factura_textos, factura_actual, indice_actual
    archivo = filedialog.askopenfilename(title="Seleccionar factura PDF", filetypes=[("PDF files", "*.pdf")])
    if archivo:
        factura_actual = archivo
        factura_textos, factura_paginas = leer_pdf_con_ocr(archivo)
        indice_actual = 0
        procesar_factura(archivo, campos, area_texto)
        mostrar_pagina(indice_actual)

def subir_orden():
    global orden_paginas, orden_textos, orden_actual, indice_actual
    archivo = filedialog.askopenfilename(title="Seleccionar orden PDF", filetypes=[("PDF files", "*.pdf")])
    if archivo:
        orden_actual = archivo
        orden_textos, orden_paginas = leer_pdf_con_ocr(archivo)
        indice_actual = 0
        procesar_orden(archivo, campos, area_texto)
        mostrar_pagina(indice_actual)

def ver_factura():
    global modo_vista
    modo_vista = "factura"
    mostrar_pagina(indice_actual)

def ver_orden():
    global modo_vista
    modo_vista = "orden"
    mostrar_pagina(indice_actual)

def siguiente():
    global indice_actual
    max_paginas = len(factura_paginas if modo_vista == "factura" else orden_paginas)
    if indice_actual < max_paginas - 1:
        indice_actual += 1
        mostrar_pagina(indice_actual)

def anterior():
    global indice_actual
    if indice_actual > 0:
        indice_actual -= 1
        mostrar_pagina(indice_actual)

def guardar_datos():
    datos = [campo.get() for campo in campos]
    print("Datos guardados:", datos)

# -------- INTERFAZ --------
ventana = tk.Tk()
ventana.title("LECTOR DE GARANTÍAS")
ventana.geometry("1200x800")

# Imagen PDF
canvas_imagen = tk.Canvas(ventana, width=400, height=500, bg="white")
scroll_y_img = tk.Scrollbar(ventana, orient="vertical", command=canvas_imagen.yview)
scroll_x_img = tk.Scrollbar(ventana, orient="horizontal", command=canvas_imagen.xview)
canvas_imagen.configure(yscrollcommand=scroll_y_img.set, xscrollcommand=scroll_x_img.set)
canvas_imagen.place(x=50, y=70)
scroll_y_img.place(x=450, y=70, height=500)
scroll_x_img.place(x=50, y=570, width=400)

etiqueta_imagen = tk.Label(canvas_imagen, bg="white")
canvas_imagen.create_window((0, 0), window=etiqueta_imagen, anchor="nw")

# Botones de zoom
tk.Button(ventana, text="Zoom +", command=zoom_in, width=8, bg="lightgray").place(x=950, y=20)
tk.Button(ventana, text="Zoom -", command=zoom_out, width=8, bg="lightgray").place(x=1030, y=20)

# Para Windows y Linux
ventana.bind("<Control-MouseWheel>", lambda e: zoom_in() if e.delta > 0 else zoom_out())

# Texto OCR
area_texto = tk.Text(ventana, wrap="word", width=50, height=30)
area_texto.place(x=500, y=70)
scroll_texto = tk.Scrollbar(ventana, command=area_texto.yview)
scroll_texto.place(x=900, y=70, height=480)
area_texto.config(yscrollcommand=scroll_texto.set)

# Formulario
frame_contenedor = tk.Frame(ventana)
frame_contenedor.place(x=950, y=70, width=230, height=500)
canvas_campos = tk.Canvas(frame_contenedor, highlightthickness=0)
scroll_y_campos = tk.Scrollbar(frame_contenedor, orient="vertical", command=canvas_campos.yview)
scroll_y_campos.pack(side="right", fill="y")
canvas_campos.pack(side="left", fill="both")
canvas_campos.configure(yscrollcommand=scroll_y_campos.set)
frame_campos = tk.Frame(canvas_campos)
canvas_campos.create_window((0, 0), window=frame_campos, anchor="nw", tags="frame")
canvas_campos.bind("<Configure>", lambda e: canvas_campos.itemconfig("frame", width=e.width))

campos = []
nombres = [
    "Numero de Factura",#0
    "Fecha de recepcion",#1
    "Numero de guia - Empresa",#2
    "Numero de solicitud",#3
    "Nit concesionario",#4
    "Concesionario",#5
    "Regional Responsable",#6
    "Agencia",#7
    "Chasis",#9
    "Motor",#10
    "Placa",#11
    "Modelo",#12
    "Modelo especifico",#13
    "Casa Matriz",#14
    "Fecha de venta",#15
    "Fecha de daño",#16
    "Periodo de garantia", #17
    "Kilometraje", #18
    "Rango de kilometraje", #19
    "Fecha de revision", #20
    "Clasificacion", #21
    "Referencia", #22
    "Descripcion", #23
    "Descripcion de la falla", #24
    "clase de daño", #25
    "Cobro de casamatriz", #26
    "Responsable de la falla", #27
    "Observaciones", #28
    "Factura interna", #29
    "Valor total Factura", #30
    "Mano de obra", #31
    "Costo Total de repuestos", #32
    "Fecha expedicion Factura", #33
    "Estado" #34
] 
for nombre in nombres:
    tk.Label(frame_campos, text=nombre + ":", anchor="w", font=("Arial", 9)).pack(fill="x", padx=5, pady=2)
    entrada = tk.Entry(frame_campos)
    entrada.pack(fill="x", padx=5, pady=2)
    campos.append(entrada)

ventana.after(500, lambda: canvas_campos.config(scrollregion=canvas_campos.bbox("all")))

# Botones
tk.Button(ventana, text="Cargar Factura", command=subir_factura, bg="lightblue", width=15).place(x=30, y=20)
tk.Button(ventana, text="Cargar Orden", command=subir_orden, bg="lightgreen", width=15).place(x=180, y=20)
tk.Button(ventana, text="← Anterior", command=anterior, width=12, bg="lightgray").place(x=370, y=20)
tk.Button(ventana, text="Siguiente →", command=siguiente, width=12, bg="lightgray").place(x=500, y=20)
tk.Button(ventana, text="Ver Factura", command=ver_factura, bg="lightblue", width=15).place(x=650, y=20)
tk.Button(ventana, text="Ver Orden", command=ver_orden, bg="lightgreen", width=15).place(x=800, y=20)
tk.Button(ventana, text="GUARDAR", command=guardar_datos, bg="lightgray", width=12).place(x=800, y=700)

ventana.mainloop()
