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
import platform


# Parámetros de renderizado / zoom
PDF_DPI = 180
ZOOM_STEP = 1.10
MIN_ZOOM = 0.2          # 20% del tamaño base
MAX_ZOOM = 4.0          # 400% del tamaño base
LANCZOS_DELAY_MS = 160   # debounce para reescalar con LANCZOS al "soltar"


# App
class LectorGarantiasApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LECTOR DE GARANTÍAS")
        self.root.geometry("1200x800")

        # Estado
        self.factura_actual = ""
        self.orden_actual = ""
        self.factura_paginas = []    # List[Image.Image]
        self.factura_textos = []     # List[str]
        self.orden_paginas = []
        self.orden_textos = []
        self.indice_actual = 0
        self.modo_vista = "factura"  # "factura" | "orden"

        # Cache de imágenes y zoom
        self.zoom_nivel = 1.0
        self.zoom_base = 1.0         # zoom para "ajustar a vista"
        self._lanczos_job = None     # id de after() para debounce
        self._is_zooming = False     # flag para interpolación bilinear durante gesto
        self._global_zoom = None

        # Arrastre/pan
        self._drag_start = None      # (x, y) en canvas al presionar
        self._canvas_img_id = None   # item id de la imagen en el canvas
        self._last_draw_size = None  # tamaño último dibujado (w, h) para evitar recomputar PhotoImage si no cambió

        # Datos externos
        self.concesionarios = cargar_concesionarios("Agencias.xlsx")

        # UI
        self._construir_ui()
        self._configurar_bindings()

    # ---------- Construcción UI ----------
    def _construir_ui(self):
        # Canvas imagen + scrollbars
        self.canvas_imagen = tk.Canvas(self.root, width=400, height=500, bg="white")
        self.scroll_y_img = tk.Scrollbar(self.root, orient="vertical", command=self.canvas_imagen.yview)
        self.scroll_x_img = tk.Scrollbar(self.root, orient="horizontal", command=self.canvas_imagen.xview)
        self.canvas_imagen.configure(yscrollcommand=self.scroll_y_img.set, xscrollcommand=self.scroll_x_img.set)
        self.canvas_imagen.place(x=50, y=70)
        self.scroll_y_img.place(x=450, y=70, height=500)
        self.scroll_x_img.place(x=50, y=570, width=400)

        # Un único item imagen en el canvas (se actualiza con zoom/redibujo)
        # Colocamos imagen en (0,0) y usaremos scrollregion para moverse
        self._canvas_img_id = self.canvas_imagen.create_image(0, 0, anchor="nw", image=None)

        # Botones superiores
        tk.Button(self.root, text="Cargar Factura", command=self.subir_factura, bg="lightblue", width=15).place(x=30, y=20)
        tk.Button(self.root, text="Cargar Orden", command=self.subir_orden, bg="lightgreen", width=15).place(x=180, y=20)
        tk.Button(self.root, text="← Anterior", command=self.anterior, width=12, bg="lightgray").place(x=370, y=20)
        tk.Button(self.root, text="Siguiente →", command=self.siguiente, width=12, bg="lightgray").place(x=500, y=20)
        tk.Button(self.root, text="Ver Factura", command=self.ver_factura, bg="lightblue", width=15).place(x=650, y=20)
        tk.Button(self.root, text="Ver Orden", command=self.ver_orden, bg="lightgreen", width=15).place(x=800, y=20)
        tk.Button(self.root, text="Zoom +", command=self.zoom_in, width=8, bg="lightgray").place(x=950, y=20)
        tk.Button(self.root, text="Zoom -", command=self.zoom_out, width=8, bg="lightgray").place(x=1030, y=20)
        tk.Button(self.root, text="GUARDAR", command=self.guardar_datos, bg="lightgray", width=12).place(x=800, y=700)

        # Texto OCR
        self.area_texto = tk.Text(self.root, wrap="word", width=50, height=30)
        self.area_texto.place(x=500, y=70)
        scroll_texto = tk.Scrollbar(self.root, command=self.area_texto.yview)
        scroll_texto.place(x=900, y=70, height=480)
        self.area_texto.config(yscrollcommand=scroll_texto.set)

        # Formulario con scroll
        frame_contenedor = tk.Frame(self.root)
        frame_contenedor.place(x=950, y=70, width=230, height=500)

        self.canvas_campos = tk.Canvas(frame_contenedor, highlightthickness=0)
        scroll_y_campos = tk.Scrollbar(frame_contenedor, orient="vertical", command=self.canvas_campos.yview)
        scroll_y_campos.pack(side="right", fill="y")
        self.canvas_campos.pack(side="left", fill="both", expand=True)
        self.canvas_campos.configure(yscrollcommand=scroll_y_campos.set)

        self.frame_campos = tk.Frame(self.canvas_campos)
        self.canvas_campos.create_window((0, 0), window=self.frame_campos, anchor="nw", tags="frame")

        # Ajuste de ancho del frame al ancho disponible del canvas
        self.canvas_campos.bind("<Configure>", lambda e: self.canvas_campos.itemconfig("frame", width=e.width))

        # Actualizar scrollregion cuando el contenido cambia de tamaño
        self.frame_campos.bind(
            "<Configure>",
            lambda e: self.canvas_campos.configure(scrollregion=self.canvas_campos.bbox("all"))
        )

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

    def _configurar_bindings(self):
        system = platform.system()

        # --- Zoom: Ctrl/Command/Option + rueda ---
        if system == "Darwin":
            self.root.bind("<Command-MouseWheel>", self._on_wheel_zoom)
            self.root.bind("<Option-MouseWheel>", self._on_wheel_zoom)
        else:
            self.root.bind("<Control-MouseWheel>", self._on_wheel_zoom)

        # --- Scroll normal SOLO en el canvas de imagen ---
        if system == "Linux":
            self.canvas_imagen.bind("<Button-4>", lambda e: self.canvas_imagen.yview_scroll(-1, "units"))
            self.canvas_imagen.bind("<Button-5>", lambda e: self.canvas_imagen.yview_scroll(1, "units"))
        else:
            self.canvas_imagen.bind("<MouseWheel>", self._on_wheel_scroll)

        # Arrastre/pan
        self.canvas_imagen.bind("<ButtonPress-1>", self._start_drag)
        self.canvas_imagen.bind("<B1-Motion>", self._on_drag)
        self.canvas_imagen.bind("<ButtonRelease-1>", self._end_drag)

        # Reajustar zoom base si cambia tamaño canvas
        self.canvas_imagen.bind("<Configure>", lambda e: self._ajustar_a_vista_if_needed())

        # Scroll del panel de campos
        for widget in (self.canvas_campos, self.frame_campos):
            widget.bind("<Enter>", self._activate_canvas_campos_scroll)
            widget.bind("<Leave>", self._deactivate_canvas_campos_scroll)

    def _activate_canvas_campos_scroll(self, *_):
        system = platform.system()
        # Usamos bind_all para capturar rueda aunque el mouse esté sobre un Entry
        if system == "Linux":
            self.root.bind_all("<Button-4>", self._on_canvas_campos_scroll_linux)
            self.root.bind_all("<Button-5>", self._on_canvas_campos_scroll_linux)
        else:
            self.root.bind_all("<MouseWheel>", self._on_canvas_campos_scroll)

    def _deactivate_canvas_campos_scroll(self, *_):
        system = platform.system()
        # Soltamos los binds globales al salir del área de campos
        if system == "Linux":
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")
        else:
            self.root.unbind_all("<MouseWheel>")

    def _on_canvas_campos_scroll(self, event):
        # Windows/macOS: delta > 0 = arriba, delta < 0 = abajo
        delta = -1 if event.delta > 0 else 1
        self.canvas_campos.yview_scroll(delta, "units")

    def _on_canvas_campos_scroll_linux(self, event):
        if event.num == 4:
            self.canvas_campos.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas_campos.yview_scroll(1, "units")


    # ---------- OCR ----------
    def leer_pdf_con_ocr(self, ruta_pdf):
        texto_por_pagina = []
        imagenes = []
        doc = fitz.open(ruta_pdf)
        for pagina in doc:
            pix = pagina.get_pixmap(dpi=PDF_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            imagenes.append(img)
            texto = pytesseract.image_to_string(img, lang="eng")
            texto_por_pagina.append(texto)
        return texto_por_pagina, imagenes

    # ---------- Acciones UI ----------
    def subir_factura(self):
        archivo = filedialog.askopenfilename(title="Seleccionar factura PDF", filetypes=[("PDF files", "*.pdf")])
        if archivo:
            self.factura_actual = archivo
            self.factura_textos, self.factura_paginas = self.leer_pdf_con_ocr(archivo)
            self.indice_actual = 0
            self.modo_vista = "factura"
            # Procesar una sola vez (no en cada zoom)
            procesar_factura(archivo, self.campos, self.area_texto, pagina_index=self.indice_actual)
            self._despues_de_cargar_documentos()

    def subir_orden(self):
        archivo = filedialog.askopenfilename(title="Seleccionar orden PDF", filetypes=[("PDF files", "*.pdf")])
        if archivo:
            self.orden_actual = archivo
            self.orden_textos, self.orden_paginas = self.leer_pdf_con_ocr(archivo)
            self.indice_actual = 0
            self.modo_vista = "orden"
            # Procesar una sola vez (no en cada zoom)
            procesar_orden(archivo, self.campos, self.area_texto, pagina_index=self.indice_actual)
            self._despues_de_cargar_documentos()

    def ver_factura(self):
        self.modo_vista = "factura"
        self.indice_actual = min(self.indice_actual, max(0, len(self.factura_paginas) - 1))
        self._mostrar_pagina(change_page=True)

    def ver_orden(self):
        self.modo_vista = "orden"
        self.indice_actual = min(self.indice_actual, max(0, len(self.orden_paginas) - 1))
        self._mostrar_pagina(change_page=True)

    def siguiente(self):
        paginas = self._paginas_actuales()
        if paginas and self.indice_actual < len(paginas) - 1:
            self.indice_actual += 1
            # Solo procesar al cambiar de página
            self._procesar_según_modo()
            self._mostrar_pagina(change_page=True)

    def anterior(self):
        if self.indice_actual > 0:
            self.indice_actual -= 1
            # Solo procesar al cambiar de página
            self._procesar_según_modo()
            self._mostrar_pagina(change_page=True)

    def guardar_datos(self):
        datos = [campo.get() for campo in self.campos]
        print("Datos guardados:", datos)

    # ---------- Zoom / Pan ----------
    def zoom_in(self, event=None):
        self._is_zooming = True
        self._cambiar_zoom(self.zoom_nivel * ZOOM_STEP, interim=True)
        self._global_zoom = self.zoom_nivel  

    def zoom_out(self, event=None):
        self._is_zooming = True
        self._cambiar_zoom(self.zoom_nivel / ZOOM_STEP, interim=True)
        self._global_zoom = self.zoom_nivel

    def _on_wheel_zoom(self, event):
        # Delta positivo = acercar, negativo = alejar
        factor = ZOOM_STEP if event.delta > 0 else (1 / ZOOM_STEP)
        self._is_zooming = True
        self._cambiar_zoom(self.zoom_nivel * factor, pivot=(event.x, event.y), interim=True)
        self._global_zoom = self.zoom_nivel

    def _on_wheel_scroll(self, event):
        # Scroll vertical normal del canvas
        units = -1 if event.delta > 0 else 1
        self.canvas_imagen.yview_scroll(units, "units")

    def _cambiar_zoom(self, nuevo_zoom, pivot=None, interim=False):
        if not self._imagen_actual():
            return

        # Limitar zoom relativo al zoom_base (para impedir imágenes gigantes)
        min_zoom_abs = self.zoom_base * MIN_ZOOM
        max_zoom_abs = self.zoom_base * MAX_ZOOM
        nuevo_zoom = max(min(nuevo_zoom, max_zoom_abs), min_zoom_abs)

        if abs(nuevo_zoom - self.zoom_nivel) < 1e-4:
            return

        # Reescalar con BILINEAR durante el gesto
        self.zoom_nivel = nuevo_zoom
        self._redibujar(interim=True)

        # Mantener el punto pivot visible (si se provee)
        if pivot:
            # Calculamos un pequeño ajuste de scroll manteniendo el punto pivot tras el reescalado
            self.canvas_imagen.update_idletasks()

        # Programar upscale final con LANCZOS tras pequeña pausa
        if self._lanczos_job:
            self.root.after_cancel(self._lanczos_job)
        self._lanczos_job = self.root.after(LANCZOS_DELAY_MS, self._zoom_finalize)

    def _zoom_finalize(self):
        if not self._imagen_actual():
            return
        self._is_zooming = False
        self._redibujar(interim=False)  
        self._global_zoom = self.zoom_nivel  
        self._lanczos_job = None

    def _start_drag(self, event):
        self.canvas_imagen.scan_mark(event.x, event.y)
        self._drag_start = (event.x, event.y)

    def _on_drag(self, event):
        if self._drag_start:
            self.canvas_imagen.scan_dragto(event.x, event.y, gain=1)

    def _end_drag(self, event):
        self._drag_start = None

    # ---------- Render ----------
    def _mostrar_pagina(self, change_page=False):
        img = self._imagen_actual()
        txt = self._texto_actual()
        if not img:
            return

        # Recalcula base por si cambió el tamaño del canvas
        self._calcular_zoom_base_fit(img)

        if change_page or self._last_draw_size is None:
            # Actualiza el texto OCR mostrado
            self.area_texto.delete("1.0", tk.END)
            if txt is not None:
                self.area_texto.insert("1.0", txt)
            # NIT + fecha
            self._completar_nit_y_fecha()

            # === Clave: aplicar zoom global si ya existe ===
            if self._global_zoom is None:
                # Primera vez: empezar en "fit a vista"
                self.zoom_nivel = self.zoom_base
                self._global_zoom = self.zoom_nivel
            else:
                # Usa el zoom global pero dentro de los límites nuevos
                min_zoom_abs = self.zoom_base * MIN_ZOOM
                max_zoom_abs = self.zoom_base * MAX_ZOOM
                self.zoom_nivel = max(min(self._global_zoom, max_zoom_abs), min_zoom_abs)

        self._redibujar(interim=False)


    def _redibujar(self, interim=False):
        """Redibuja la imagen cacheada aplicando self.zoom_nivel con interpolación adecuada.
        interim=True usa BILINEAR (gesto); interim=False usa LANCZOS (reposo)."""
        base_img = self._imagen_actual()
        if not base_img:
            return

        # Tamaño destino
        w = int(base_img.width * self.zoom_nivel)
        h = int(base_img.height * self.zoom_nivel)
        w = max(1, w)
        h = max(1, h)

        # Evitar recomputar si no cambia tamaño (ahorra CPU al arrastrar)
        if self._last_draw_size == (w, h) and hasattr(self, "_photo_img"):
            self.canvas_imagen.itemconfig(self._canvas_img_id, image=self._photo_img)
            return

        resample = Image.BILINEAR if interim else Image.LANCZOS
        img_resized = base_img.resize((w, h), resample=resample)

        # Convertir a PhotoImage y dibujar
        self._photo_img = ImageTk.PhotoImage(img_resized)
        self.canvas_imagen.itemconfig(self._canvas_img_id, image=self._photo_img)
        self.canvas_imagen.coords(self._canvas_img_id, 0, 0)
        self.canvas_imagen.config(scrollregion=(0, 0, w, h))
        self._last_draw_size = (w, h)

    def _calcular_zoom_base_fit(self, img: Image.Image):
        """Calcula un zoom base para que la imagen quepa cómodamente en el canvas."""
        cw = int(self.canvas_imagen.winfo_width() or 1)
        ch = int(self.canvas_imagen.winfo_height() or 1)
        if cw <= 1 or ch <= 1:
            # Si todavía no se ha medido el canvas, intentar de nuevo luego
            self.root.after(50, lambda: self._calcular_zoom_base_fit(img))
            return
        fw = cw * 0.95   # margen
        fh = ch * 0.95
        zx = fw / img.width
        zy = fh / img.height
        z = max(0.1, min(zx, zy))
        # No arrancar demasiado grande
        z = min(z, 1.2)
        self.zoom_base = z

    def _ajustar_a_vista_if_needed(self):
        # Re-ajusta el fit si no estamos en un gesto de zoom y hay imagen
        if not self._is_zooming and self._imagen_actual():
            prev_base = self.zoom_base
            self._calcular_zoom_base_fit(self._imagen_actual())
            # Si el canvas cambió mucho de tamaño y el zoom actual era el base, mantener "fit"
            if abs(self.zoom_nivel - prev_base) < 1e-3:
                self.zoom_nivel = self.zoom_base
                self._redibujar(interim=False)

    # ---------- Helpers de datos ----------
    def _paginas_actuales(self):
        return self.factura_paginas if self.modo_vista == "factura" else self.orden_paginas

    def _textos_actuales(self):
        return self.factura_textos if self.modo_vista == "factura" else self.orden_textos

    def _imagen_actual(self):
        paginas = self._paginas_actuales()
        if not paginas or self.indice_actual >= len(paginas):
            return None
        return paginas[self.indice_actual]

    def _texto_actual(self):
        textos = self._textos_actuales()
        if not textos or self.indice_actual >= len(textos):
            return None
        return textos[self.indice_actual]

    def _procesar_según_modo(self):
        """Llama a procesar_factura/orden solo al cambiar de página o documento."""
        if self.modo_vista == "factura" and self.factura_actual:
            procesar_factura(self.factura_actual, self.campos, self.area_texto, pagina_index=self.indice_actual)
        elif self.modo_vista == "orden" and self.orden_actual:
            procesar_orden(self.orden_actual, self.campos, self.area_texto, pagina_index=self.indice_actual)

    def _completar_nit_y_fecha(self):
        # Unir textos de documentos para buscar NIT
        texto_factura = "\n".join(self.factura_textos) if self.factura_textos else ""
        texto_orden = "\n".join(self.orden_textos) if self.orden_textos else ""
        nit, nombre, regional = buscar_nit_valido(texto_factura, texto_orden, self.concesionarios)

        if nit:
            self.campos[4].delete(0, "end")
            self.campos[4].insert(0, nit)
        if nombre:
            self.campos[5].delete(0, "end")
            self.campos[5].insert(0, nombre)
        if regional:
            self.campos[6].delete(0, "end")
            self.campos[6].insert(0, regional)

        # Fecha actual en "Fecha de revisión"
        fecha_actual = datetime.today().strftime('%Y-%m-%d')
        self.campos[19].delete(0, "end")
        self.campos[19].insert(0, fecha_actual)

    def _despues_de_cargar_documentos(self):
        """Acciones comunes tras cargar un PDF (factura u orden)."""
        self._mostrar_pagina(change_page=True)

# Main
if __name__ == "__main__":
    ventana = tk.Tk()
    app = LectorGarantiasApp(ventana)
    ventana.mainloop()
