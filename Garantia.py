import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import pytesseract
import fitz
import io

#Modulos
from Estractores import extraer_numero_factura, extraer_fecha_emision
from BusquedaRef import buscar_referencias_en_texto

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\practicante1servicio\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

def leer_pdf_con_ocr(ruta_pdf):
    texto_por_pagina = []
    imagenes = []

    doc = fitz.open(ruta_pdf)
    for pagina in doc:
        pix = pagina.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        imagenes.append(img)

        texto = pytesseract.image_to_string(img, lang="eng")
        texto_por_pagina.append(texto)
    
    return texto_por_pagina, imagenes

def subir_pdf():
    global paginas_pdf, textos_pdf, indice_actual
    ruta = filedialog.askopenfilename(
        title="Seleccionar PDF",
        filetypes=[("Archivos PDF", "*.pdf")]
    )
    if ruta:
        texto, imagen = leer_pdf_con_ocr(ruta)
        paginas_pdf = imagen
        textos_pdf = texto
        indice_actual = 0
        mostrar_pagina(indice_actual)

paginas_pdf = []
textos_pdf = []
indice_actual = 0
zoom_nivel = 1.0

def mostrar_pagina(index):
    global paginas_pdf, etiqueta_imagen, zoom_nivel
    
    imagen = paginas_pdf[index]
    #imagen = imagen.resize((400, 500))
    ancho= int(imagen.width * zoom_nivel)
    alto = int(imagen.height * zoom_nivel)
    imagen_zoom = imagen.resize((ancho, alto))

    imagen_tk = ImageTk.PhotoImage(imagen_zoom)
    etiqueta_imagen.config(image=imagen_tk)
    etiqueta_imagen.image = imagen_tk

    area_texto.delete("1.0", tk.END)
    area_texto.insert(tk.END, textos_pdf[index])

    #Aqui buscamos la referencia desde el excel
    resultados = buscar_referencias_en_texto(textos_pdf[index])
    if resultados:
        referencias = [r["Referencia"] for r in resultados]
        descripciones = [r["Descripcion"] for r in resultados]

        campos[22].delete(0, tk.END)
        campos[22].insert(0, ", ".join(referencias))

        campos[23].delete(0, tk.END)
        campos[23].insert(0, ", ".join(descripciones))


    #Extraer dato Factura
    numero = extraer_numero_factura(textos_pdf[index])
    campos[0].delete(0, tk.END)
    campos[0].insert(0, numero)

    #Extraer fecha de emision
    fecha = extraer_fecha_emision(textos_pdf[index])
    campos[1].delete(0, tk.END)
    campos[1].insert(0, fecha)

    etiqueta_imagen.update_idletasks()
    canvas_imagen.config(scrollregion=canvas_imagen.bbox("all"))

def actualizar_zoom(valor):
    global zoom_nivel
    zoom_nivel = float(valor)
    mostrar_pagina(indice_actual)

def siguiente():
    global indice_actual
    if indice_actual < len(paginas_pdf) - 1:
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

# VENTANA
ventana = tk.Tk()
ventana.title("GARANTÍA - Lector PDF OCR")
ventana.geometry("1200x800")


def scroll_zoom(event):
    global zoom_nivel
    if event.delta > 0:
        zoom_nivel = min(zoom_nivel + 0.1, 3.0)
    else:
        zoom_nivel = max(zoom_nivel - 0.1, 0.5)
    mostrar_pagina(indice_actual)

# BOTONES DE NAVEGACIÓN
btn_anterior = tk.Button(ventana, text="← Anterior", command=anterior, width=12, bg="lightgray")
btn_anterior.place(x=150, y=20)

btn_siguiente = tk.Button(ventana, text="Siguiente →", command=siguiente, width=12, bg="lightgray")
btn_siguiente.place(x=280, y=20)

# BOTÓN SUBIR
btn_subir = tk.Button(ventana, text="SUBIR", command=subir_pdf, bg="lightblue", width=10)
btn_subir.place(x=30, y=20)

# IMAGEN PDF
#etiqueta_imagen.place(x=50, y=70) 
canvas_imagen = tk.Canvas(ventana, width=400, height=500, bg="white")
scroll_y_img = tk.Scrollbar(ventana, orient="vertical", command=canvas_imagen.yview)
scroll_x_img = tk.Scrollbar(ventana, orient="horizontal", command=canvas_imagen.xview)

canvas_imagen.configure(yscrollcommand=scroll_y_img.set, xscrollcommand=scroll_x_img.set)
canvas_imagen.place(x=50, y=70)
scroll_y_img.place(x=50 + 400, y=70, height=500)
scroll_x_img.place(x=50, y=570, width=400)

etiqueta_imagen = tk.Label(canvas_imagen, bg="white")
canvas_imagen.create_window((0, 0), window=etiqueta_imagen, anchor="nw")

canvas_imagen.bind("<Enter>", lambda e: canvas_imagen.bind_all("<MouseWheel>", scroll_zoom))
canvas_imagen.bind("<Leave>", lambda e: canvas_imagen.unbind_all("<MouseWheel>"))

# TEXTO OCR
area_texto = tk.Text(ventana, wrap="word", width=50, height=30)
area_texto.place(x=500, y=70)

scroll_texto = tk.Scrollbar(ventana, command=area_texto.yview)
scroll_texto.place(x=500 + 400, y=70, height=480)
area_texto.config(yscrollcommand=scroll_texto.set)

# CAMPOS DE TEXTO SCROLLABLE EN UNA SOLA COLUMNA (AL LADO DERECHO)
frame_contenedor = tk.Frame(ventana)
frame_contenedor.place(x=950, y=70, width=230, height=500)

canvas_campos = tk.Canvas(frame_contenedor, highlightthickness=0)
scroll_y_campos = tk.Scrollbar(frame_contenedor, orient="vertical", command=canvas_campos.yview)
scroll_y_campos.pack(side="right", fill="y")

canvas_campos.pack(side="left", fill="both")  # quitamos expand=True
canvas_campos.configure(yscrollcommand=scroll_y_campos.set, xscrollcommand=lambda *args: None)  # desactiva scroll horizontal

frame_campos = tk.Frame(canvas_campos)
canvas_campos.create_window((0, 0), window=frame_campos, anchor="nw", tags="frame")

def ajustar_ancho(event):
    canvas_campos.itemconfig("frame", width=event.width)

canvas_campos.bind("<Configure>", ajustar_ancho)

# Crear 34 campos verticales
campos = []
nombres = [
    "Numero de Factura",#1
    "Fecha de recepcion",#2
    "Numero de guia - Empresa",#3
    "Numero de solicitud",#4
    "Nit concesionario",#5
    "Concesionario",#6
    "Agencia",#7
    "Regional Responsable",#8
    "Chasis",#9
    "Motor",#10
    "Placa",#11
    "Modelo",#12
    "Modeo especifico",#13
    "Fecha de venta",#14
    "Fecha de daño",#15
    "Periodo de garantia", #16
    "Kilometraje", #17
    "rango de kilometraje", #18
    "Fecha de revision", #19
    "Clasificacion", #20
    "Rereferencia", #21
    "Descripcion", #22
    "Descripcion de la falla", #23
    "clase de daño", #24
    "Cobro de casamatriz", #25
    "Responsable de la falla", #26
    "Observaciones", #27
    "Factura interna", #28
    "Valor total Factura", #29
    "Mano de obra", #30
    "Costo Total de repuestos", #31
    "Fecha expedicion Factura", #32
    "Estado" #33
] 

for i, nombre in enumerate(nombres):
    etiqueta = tk.Label(frame_campos, text=nombre + ":", anchor="w", font=("Arial", 9))
    etiqueta.pack(fill="x", padx=5, pady=2)

    entrada = tk.Entry(frame_campos)
    entrada.pack(fill="x", padx=5, pady=2)

    campos.append(entrada)

def actualizar_scroll():
    frame_campos.update_idletasks()
    canvas_campos.config(scrollregion=canvas_campos.bbox("all"))

ventana.after(500, actualizar_scroll)


# BOTÓN GUARDAR
btn_guardar = tk.Button(ventana, text="GUARDA", command=guardar_datos, bg="lightblue", width=12)
btn_guardar.place(x=800, y=700)

ventana.mainloop()

