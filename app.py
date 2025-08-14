# app.py
import tkinter as tk
from tkinter import filedialog
from datetime import datetime

from PIL import Image  
import platform

from viewer import PageViewer
from pdf_io import leer_pdf_con_ocr
from factura import procesar_factura
from orden_servicio import procesar_orden
from nit import cargar_concesionarios, buscar_nit_valido

# Configurar Tesseract (ajusta tu ruta si hace falta)
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\\Users\\practicante1servicio\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe"

class LectorGarantiasApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LECTOR DE GARANTÍAS")
        self.root.geometry("1200x800")

        # estado documentos
        self.factura_actual = ""
        self.orden_actual = ""
        self.factura_textos, self.factura_paginas = [], []
        self.orden_textos, self.orden_paginas = [], []
        self.indice = 0
        self.modo = "factura"  # "factura" | "orden"

        # datos externos
        self.concesionarios = cargar_concesionarios("Agencias.xlsx")

        # UI
        self.viewer = PageViewer(self.root, x=50, y=70, w=400, h=500)
        self.viewer.set_image_getter(self._imagen_actual)
        self.viewer.bind_zoom_shortcuts()

        self._construir_panel_ocr()
        self._construir_panel_campos()
        self._construir_botones()
        self._configurar_scroll_campos()

    # ---------- UI ----------
    def _construir_panel_ocr(self):
        self.area_texto = tk.Text(self.root, wrap="word", width=50, height=30)
        self.area_texto.place(x=500, y=70)
        scroll_texto = tk.Scrollbar(self.root, command=self.area_texto.yview)
        scroll_texto.place(x=900, y=70, height=480)
        self.area_texto.config(yscrollcommand=scroll_texto.set)

    def _construir_panel_campos(self):
        cont = tk.Frame(self.root); cont.place(x=950, y=70, width=230, height=500)
        self.canvas_campos = tk.Canvas(cont, highlightthickness=0)
        scroll_y_campos = tk.Scrollbar(cont, orient="vertical", command=self.canvas_campos.yview)
        scroll_y_campos.pack(side="right", fill="y")
        self.canvas_campos.pack(side="left", fill="both", expand=True)
        self.canvas_campos.configure(yscrollcommand=scroll_y_campos.set)

        self.frame_campos = tk.Frame(self.canvas_campos)
        self.canvas_campos.create_window((0, 0), window=self.frame_campos, anchor="nw", tags="frame")
        self.canvas_campos.bind("<Configure>", lambda e: self.canvas_campos.itemconfig("frame", width=e.width))
        self.frame_campos.bind("<Configure>", lambda e: self.canvas_campos.configure(scrollregion=self.canvas_campos.bbox("all")))

        # Campos
        self.campos = []
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
            tk.Label(self.frame_campos, text=nombre + ":", anchor="w", font=("Arial", 9)).pack(fill="x", padx=5, pady=2)
            entrada = tk.Entry(self.frame_campos)
            entrada.pack(fill="x", padx=5, pady=2)
            self.campos.append(entrada)

    def _construir_botones(self):
        tk.Button(self.root, text="Cargar Factura", command=self.subir_factura, bg="lightblue", width=15).place(x=30, y=20)
        tk.Button(self.root, text="Cargar Orden", command=self.subir_orden, bg="lightgreen", width=15).place(x=180, y=20)
        tk.Button(self.root, text="← Anterior", command=self.anterior, width=12, bg="lightgray").place(x=370, y=20)
        tk.Button(self.root, text="Siguiente →", command=self.siguiente, width=12, bg="lightgray").place(x=500, y=20)
        tk.Button(self.root, text="Ver Factura", command=self.ver_factura, bg="lightblue", width=15).place(x=650, y=20)
        tk.Button(self.root, text="Ver Orden", command=self.ver_orden, bg="lightgreen", width=15).place(x=800, y=20)
        tk.Button(self.root, text="Zoom +", command=self.viewer.zoom_in, width=8, bg="lightgray").place(x=950, y=20)
        tk.Button(self.root, text="Zoom -", command=self.viewer.zoom_out, width=8, bg="lightgray").place(x=1030, y=20)
        tk.Button(self.root, text="GUARDAR", command=self.guardar_datos, bg="lightgray", width=12).place(x=800, y=700)

    def _configurar_scroll_campos(self):
        # Rueda funcional incluso sobre Entry: bind_all SOLO cuando el puntero está encima
        for w in (self.canvas_campos, self.frame_campos):
            w.bind("<Enter>", self._activa_scroll_campos)
            w.bind("<Leave>", self._desactiva_scroll_campos)

    def _activa_scroll_campos(self, *_):
        self.root.bind_all("<MouseWheel>", self._on_scroll_campos)
        self.root.bind_all("<Button-4>", self._on_scroll_campos_linux)
        self.root.bind_all("<Button-5>", self._on_scroll_campos_linux)

    def _desactiva_scroll_campos(self, *_):
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _on_scroll_campos(self, event):
        delta = -1 if event.delta > 0 else 1
        self.canvas_campos.yview_scroll(delta, "units")
        return "break"

    def _on_scroll_campos_linux(self, event):
        self.canvas_campos.yview_scroll(-1 if event.num == 4 else 1, "units")
        return "break"

    # ---------- Acciones ----------
    def subir_factura(self):
        archivo = filedialog.askopenfilename(title="Seleccionar factura PDF", filetypes=[("PDF files", "*.pdf")])
        if not archivo: return
        self.factura_actual = archivo
        self.factura_textos, self.factura_paginas = leer_pdf_con_ocr(archivo)
        self.modo, self.indice = "factura", 0
        procesar_factura(archivo, self.campos, self.area_texto, pagina_index=self.indice)
        self.viewer.show_page(on_page_change=True)

    def subir_orden(self):
        archivo = filedialog.askopenfilename(title="Seleccionar orden PDF", filetypes=[("PDF files", "*.pdf")])
        if not archivo: return
        self.orden_actual = archivo
        self.orden_textos, self.orden_paginas = leer_pdf_con_ocr(archivo)
        self.modo, self.indice = "orden", 0
        procesar_orden(archivo, self.campos, self.area_texto, pagina_index=self.indice)
        self.viewer.show_page(on_page_change=True)

    def ver_factura(self):
        self.modo = "factura"
        self.indice = min(self.indice, max(0, len(self.factura_paginas) - 1))
        self._mostrar_pagina(change=True)

    def ver_orden(self):
        self.modo = "orden"
        self.indice = min(self.indice, max(0, len(self.orden_paginas) - 1))
        self._mostrar_pagina(change=True)

    def siguiente(self):
        pags = self._paginas_actuales()
        if pags and self.indice < len(pags) - 1:
            self.indice += 1
            self._procesar_actual()
            self._mostrar_pagina(change=True)

    def anterior(self):
        if self.indice > 0:
            self.indice -= 1
            self._procesar_actual()
            self._mostrar_pagina(change=True)

    def guardar_datos(self):
        datos = [c.get() for c in self.campos]
        print("Datos guardados:", datos)

    # ---------- Helpers ----------
    def _paginas_actuales(self):
        return self.factura_paginas if self.modo == "factura" else self.orden_paginas

    def _textos_actuales(self):
        return self.factura_textos if self.modo == "factura" else self.orden_textos

    def _imagen_actual(self):
        pags = self._paginas_actuales()
        return pags[self.indice] if pags and self.indice < len(pags) else None

    def _texto_actual(self):
        txts = self._textos_actuales()
        return txts[self.indice] if txts and self.indice < len(txts) else ""

    def _mostrar_pagina(self, change=False):
        # actualizar texto OCR visible
        self.area_texto.delete("1.0", tk.END)
        self.area_texto.insert("1.0", self._texto_actual())
        # NIT + fecha
        self._completar_nit_y_fecha()
        # forzar redibujo
        self.viewer.show_page(on_page_change=change)

    def _procesar_actual(self):
        if self.modo == "factura" and self.factura_actual:
            procesar_factura(self.factura_actual, self.campos, self.area_texto, pagina_index=self.indice)
        elif self.modo == "orden" and self.orden_actual:
            procesar_orden(self.orden_actual, self.campos, self.area_texto, pagina_index=self.indice)

    def _completar_nit_y_fecha(self):
        texto_factura = "\n".join(self.factura_textos) if self.factura_textos else ""
        texto_orden = "\n".join(self.orden_textos) if self.orden_textos else ""
        nit, nombre, regional = buscar_nit_valido(texto_factura, texto_orden, self.concesionarios)
        if nit:
            self.campos[4].delete(0, "end"); self.campos[4].insert(0, nit)
        if nombre:
            self.campos[5].delete(0, "end"); self.campos[5].insert(0, nombre)
        if regional:
            self.campos[6].delete(0, "end"); self.campos[6].insert(0, regional)

        # Fecha de revisión (actual)
        fecha_actual = datetime.today().strftime('%Y-%m-%d')
        self.campos[19].delete(0, "end"); self.campos[19].insert(0, fecha_actual)

    # PageViewer pide esta función:
    def _imagen_actual(self):
        pags = self._paginas_actuales()
        return pags[self.indice] if pags and self.indice < len(pags) else None

if __name__ == "__main__":
    root = tk.Tk()
    app = LectorGarantiasApp(root)
    root.mainloop()
