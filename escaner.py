import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from datetime import datetime

from tabla_registros import abrir_tabla_registros
from viewer import PageViewer
from pdf_io import leer_pdf_con_ocr
from factura import procesar_factura
from orden_servicio import procesar_orden
from nit import cargar_concesionarios, buscar_nit_valido

# Configurar Tesseract (ajusta tu ruta si hace falta)
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\\Users\\practicante1servicio\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe"

class LectorGarantiasApp:
    def __init__(self, root: tk.Tk, host: tk.Widget = None):
        self.standalone = host is None
        self.parent = host if host is not None else root

        if self.standalone:
            self.parent.title("LECTOR DE GARANTÍAS")
            self.parent.geometry("1200x800")
            try:
                self.parent.state('zoomed')               
            except Exception:
                try:
                    self.parent.attributes('-zoomed', True) 
                except Exception:
                    pass

        # --------- Estado documentos ---------
        self.factura_actual = ""
        self.orden_actual = ""
        self.factura_textos, self.factura_paginas = [], []
        self.orden_textos,  self.orden_paginas  = [], []
        self.indice = 0
        self.modo = "factura"  # "factura" | "orden"
        self.doc_cache = {}

        # --------- Datos externos ---------
        try:
            self.concesionarios = cargar_concesionarios("Agencias.xlsx")
        except Exception as e:
            self.concesionarios = {}
            print(f"[WARN] No se pudo cargar Agencias.xlsx: {e}")

        # --------- LAYOUT: Grid de alto nivel ---------
        # Fila 0: Topbar (botones)
        # Fila 1: Cuerpo (3 columnas: visor | OCR | formulario)
        # Fila 2: Barra de progreso
        self.parent.grid_rowconfigure(1, weight=1)
        # Visor (col 0) más ancho:  minsize asegura base; weight reparte lo extra
        self.parent.grid_columnconfigure(0, weight=3, minsize=500)   # visor PDF
        self.parent.grid_columnconfigure(1, weight=2, minsize=300)   # OCR
        self.parent.grid_columnconfigure(2, weight=2, minsize=320)   # formulario

        # Topbar
        self._build_topbar()

        # Cuerpo
        self._build_viewer()       # col 0
        self._build_ocr()          # col 1
        self._build_form_fields()  # col 2

        # Barra de progreso
        self._build_progressbar()

    # ------------------- UI: Topbar -------------------
    def _build_topbar(self):
        self.topbar = ttk.Frame(self.parent, padding=(8, 6))
        self.topbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.topbar.grid_columnconfigure(99, weight=1)  # separador elástico

        tk.Button(self.topbar, text="Cargar Factura", command=self.subir_factura, bg="lightblue").grid(row=0, column=0, padx=4)
        tk.Button(self.topbar, text="Cargar Orden",   command=self.subir_orden, bg="lightgreen").grid(row=0, column=1, padx=4)
        ttk.Button(self.topbar, text="← Anterior",    command=self.anterior).grid(row=0, column=2, padx=4)
        ttk.Button(self.topbar, text="Siguiente →",   command=self.siguiente).grid(row=0, column=3, padx=4)
        tk.Button(self.topbar, text="Ver Factura",    command=self.ver_factura, bg="lightblue").grid(row=0, column=4, padx=4)
        tk.Button(self.topbar, text="Ver Orden",      command=self.ver_orden, bg="lightgreen").grid(row=0, column=5, padx=4)

    # ------------------- UI: Visor (col 0) -------------------
    def _build_viewer(self):
        viewer_wrap = ttk.Frame(self.parent, padding=(8, 8))
        viewer_wrap.grid(row=1, column=0, sticky="nsew")
        viewer_wrap.grid_rowconfigure(0, weight=1)
        viewer_wrap.grid_columnconfigure(0, weight=1)

        # Host del visor
        self.viewer_host = ttk.Frame(viewer_wrap)
        self.viewer_host.grid(row=0, column=0, sticky="nsew")
        self.viewer_host.grid_rowconfigure(0, weight=1)
        self.viewer_host.grid_columnconfigure(0, weight=1)

        # Scrollbars discretos (ocultos por defecto)
        self.vscroll = tk.Scrollbar(
            self.viewer_host, orient="vertical", width=8, relief="flat",
            highlightthickness=0, bd=0
        )
        self.hscroll = tk.Scrollbar(
            self.viewer_host, orient="horizontal", width=8, relief="flat",
            highlightthickness=0, bd=0
        )
        # Colocados pero los ocultamos hasta que hagan falta
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.hscroll.grid(row=1, column=0, sticky="ew")
        self.vscroll.grid_remove()
        self.hscroll.grid_remove()

        # Crea el PageViewer (tamaño inicial mínimo; se ajusta en <Configure>)
        self.viewer = PageViewer(self.viewer_host, x=0, y=0, w=10, h=10)
        # Si PageViewer expone un widget (Frame/Canvas), pégalo al grid
        try:
            self.viewer.grid(row=0, column=0, sticky="nsew")
        except Exception:
            pass

        self.viewer.set_image_getter(self._imagen_actual)
        self.viewer.bind_zoom_shortcuts()

        # Vincula scrollbars al canvas interno del PageViewer (si existe)
        if hasattr(self.viewer, "canvas"):
            cv = self.viewer.canvas
            cv.configure(
                xscrollcommand=self.hscroll.set,
                yscrollcommand=self.vscroll.set,
                highlightthickness=0, bd=0
            )
            self.vscroll.configure(command=cv.yview)
            self.hscroll.configure(command=cv.xview)

            # Cuando cambie el tamaño del canvas, re-evalúa necesidad de barras
            cv.bind("<Configure>", lambda e: self._refresh_viewer_scrollbars())

            # (IMPORTANTE) Si tu PageViewer crea sus propias barras internas,
            # intenta ocultarlas si existen:
            for attr in ("vbar", "hbar"):
                try:
                    bar = getattr(self.viewer, attr, None)
                    if bar and hasattr(bar, "pack_forget"):
                        bar.pack_forget()
                except Exception:
                    pass

        # Ajuste dinámico al redimensionar el contenedor
        def _on_resize(_event=None):
            w = max(1, self.viewer_host.winfo_width())
            h = max(1, self.viewer_host.winfo_height())

            if hasattr(self.viewer, "set_size"):
                self.viewer.set_size(w, h)
            elif hasattr(self.viewer, "resize"):
                self.viewer.resize(w, h)
            elif hasattr(self.viewer, "set_bounds"):
                self.viewer.set_bounds(0, 0, w, h)
            else:
                try:
                    self.viewer.w = w; self.viewer.h = h
                    if hasattr(self.viewer, "canvas"):
                        self.viewer.canvas.config(width=w, height=h)
                except Exception:
                    pass

            self.viewer.show_page(on_page_change=False)
            self._refresh_viewer_scrollbars()

        self.viewer_host.bind("<Configure>", _on_resize)
        self._refresh_viewer_scrollbars()


    # ------------------- UI: OCR (col 1) -------------------
    def _build_ocr(self):
        ocr_wrap = ttk.Frame(self.parent, padding=(8, 8))
        ocr_wrap.grid(row=1, column=1, sticky="nsew")
        ocr_wrap.grid_rowconfigure(0, weight=1)
        ocr_wrap.grid_columnconfigure(0, weight=1)

        self.area_texto = tk.Text(ocr_wrap, wrap="word")
        self.area_texto.grid(row=0, column=0, sticky="nsew")

        scroll_texto = tk.Scrollbar(
        ocr_wrap, orient="vertical", command=self.area_texto.yview,
        width=8, relief="flat", highlightthickness=0, bd=0
        )
        scroll_texto.grid(row=0, column=1, sticky="ns")
        self.area_texto.configure(yscrollcommand=scroll_texto.set)

    # ------------------- UI: Formulario (col 2) -------------------
    def _build_form_fields(self):
        cont = ttk.Frame(self.parent, padding=(8, 8))
        cont.grid(row=1, column=2, sticky="nsew")
        cont.grid_rowconfigure(0, weight=1)
        cont.grid_columnconfigure(0, weight=1)

        self.canvas_campos = tk.Canvas(cont, highlightthickness=0)
        self.canvas_campos.grid(row=0, column=0, sticky="nsew")
        scroll_y_campos = ttk.Scrollbar(cont, orient="vertical", command=self.canvas_campos.yview)
        scroll_y_campos.grid(row=0, column=1, sticky="ns")
        self.canvas_campos.configure(yscrollcommand=scroll_y_campos.set)

        self.frame_campos = ttk.Frame(self.canvas_campos)
        self.canvas_campos.create_window((0, 0), window=self.frame_campos, anchor="nw", tags="frame")

        # Ajustar ancho del frame interno al del canvas
        self.canvas_campos.bind("<Configure>", lambda e: self.canvas_campos.itemconfigure("frame", width=e.width))
        self.frame_campos.bind("<Configure>", lambda e: self.canvas_campos.configure(scrollregion=self.canvas_campos.bbox("all")))

        # ------- Campos -------
        self.campos = []
        nombres = [
            "Numero de Factura",  #0
            "Fecha de recepcion", #1
            "Numero de guia - Empresa", #2
            "Numero de solicitud", #3
            "Nit concesionario", #4
            "Concesionario", #5
            "Regional Responsable", #6
            "Agencia", #7
            "Chasis", #8
            "Motor", #9
            "Placa", #10
            "Modelo", #11
            "Modelo especifico", #12
            "Casa Matriz", #13
            "Fecha de venta", #14
            "Fecha de daño", #15
            "Periodo de garantia", #16
            "Kilometraje", #17
            "Rango de kilometraje", #18
            "Fecha de revision", #19
            "Clasificacion", #20
            "Referencia", #21
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

        for nombre in nombres:
            ttk.Label(self.frame_campos, text=nombre + ":", anchor="w").pack(fill="x", padx=5, pady=(6, 2))
            entrada = ttk.Entry(self.frame_campos)
            entrada.pack(fill="x", padx=5, pady=(0, 6))

            entrada.bind("<KeyRelease>", self._on_entry_change)
            entrada.bind("<<Paste>>", self._on_entry_change)
            entrada.bind("<<Cut>>", self._on_entry_change)
            entrada.bind("<FocusOut>", self._on_entry_change)
            self.campos.append(entrada)

        # Inicializar progreso y cálculos
        self.headers = nombres[:]
        self.registros = []
        self._actualizar_progreso()

        # Default mano de obra = 0
        if not self.campos[30].get().strip():
            self.campos[30].insert(0, "0")

        # Recalcular repuestos al cambiar total o mano de obra
        for i in (29, 30):
            self.campos[i].bind("<KeyRelease>", self._recalc_repuestos, add="+")
            self.campos[i].bind("<FocusOut>",  self._recalc_repuestos, add="+")

        # Scroll solo dentro del canvas, no global
        self.canvas_campos.bind("<Enter>", self._activa_scroll_campos)
        self.canvas_campos.bind("<Leave>", self._desactiva_scroll_campos)

    # ------------------- UI: Progreso (fila 2) -------------------
    def _build_progressbar(self):
        # contenedor inferior de 3 columnas
        bottom = ttk.Frame(self.parent, padding=(8, 8))
        bottom.grid(row=2, column=0, columnspan=3, sticky="ew")

        # columnas: [0]=izq (zoom)  [1]=centro (progreso)  [2]=der (acciones)
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=2)
        bottom.grid_columnconfigure(2, weight=1)

        # --- IZQUIERDA: Zoom ---
        left = ttk.Frame(bottom)
        left.grid(row=0, column=0, sticky="w")
        ttk.Button(left, text="Zoom -", command=self._zoom_out).pack(side="left", padx=(0,6))
        ttk.Button(left, text="Zoom +", command=self._zoom_in).pack(side="left")

        # --- CENTRO: Progreso ---
        center = ttk.Frame(bottom)
        center.grid(row=0, column=1, sticky="ew")
        center.grid_columnconfigure(1, weight=1)

        self.lbl_progreso = ttk.Label(center, text="Campos completados: 0/0 (0.0%)")
        self.lbl_progreso.grid(row=0, column=0, sticky="w", padx=(0,10))

        self.progreso = ttk.Progressbar(center, orient="horizontal", mode="determinate")
        self.progreso.grid(row=0, column=1, sticky="ew")

        try:
            style = ttk.Style(self.parent)
            style.theme_use("clam")
            style.configure("green.Horizontal.TProgressbar", troughcolor="#eeeeee", background="#4CAF50")
            self.progreso.configure(style="green.Horizontal.TProgressbar")
        except Exception:
            pass

        # --- DERECHA: Acciones ---
        right = ttk.Frame(bottom)
        right.grid(row=0, column=2, sticky="e")
        tk.Button(right, text="Ver / Exportar", command=self.ver_exportar_tabla,bg="orange").pack(side="left", padx=(0,6))
        tk.Button(right, text="Guardar", command=self.guardar_datos,bg="khaki").pack(side="left")

        # primer cálculo
        self._actualizar_progreso()

    # =================== LÓGICA ===================
    # ---- Navegación visor/órdenes ----
    def ver_factura(self):
        self._save_doc_cache(self.modo)
        self.modo = "factura"
        self.indice = min(self.indice, max(0, len(self.factura_paginas) - 1))
        self._restore_or_process()
        self._mostrar_pagina(change=True)

    def ver_orden(self):
        self._save_doc_cache(self.modo)
        self.modo = "orden"
        self.indice = min(self.indice, max(0, len(self.orden_paginas) - 1))
        self._restore_or_process()
        self._mostrar_pagina(change=True)

    def siguiente(self):
        pags = self._paginas_actuales()
        if pags and self.indice < len(pags) - 1:
            self._save_doc_cache(self.modo)
            self.indice += 1
            self._restore_or_process()
            self._mostrar_pagina(change=True)

    def anterior(self):
        if self.indice > 0:
            self._save_doc_cache(self.modo)
            self.indice -= 1
            self._restore_or_process()
            self._mostrar_pagina(change=True)

    # ---- Acciones: cargar PDFs ----
    def subir_factura(self):
        archivo = filedialog.askopenfilename(title="Seleccionar factura PDF", filetypes=[("PDF files", "*.pdf")])
        if not archivo:
            return
        self.factura_actual = archivo
        self.factura_textos, self.factura_paginas = leer_pdf_con_ocr(archivo, lang="eng+spa")

        if not self.orden_paginas:
            self.doc_cache.clear()
        self.modo, self.indice = "factura", 0
        procesar_factura(
            archivo, self.campos, self.area_texto, pagina_index=self.indice,
            imagen_pagina=self._imagen_actual(),
            texto_ocr=self._texto_actual(),
            
        )
        self._completar_nit_y_fecha()
        self._recalc_repuestos()
        self._save_doc_cache("factura")
        self.viewer.show_page(on_page_change=True)
        self._actualizar_progreso()

    def subir_orden(self):
        archivo = filedialog.askopenfilename(title="Seleccionar orden PDF", filetypes=[("PDF files", "*.pdf")])
        if not archivo:
            return
        self.orden_actual = archivo
        self.orden_textos, self.orden_paginas = leer_pdf_con_ocr(archivo, lang="eng+spa")

        if not self.factura_paginas:
            self.doc_cache.clear()
        self.modo, self.indice = "orden", 0

        procesar_orden(
            archivo, self.campos, self.area_texto, pagina_index=self.indice,
            imagen_pagina=self._imagen_actual(),
            texto_ocr=self._texto_actual()
        )
        self._completar_nit_y_fecha()
        self._save_doc_cache("orden")
        self.viewer.show_page(on_page_change=True)
        self._actualizar_progreso()

    # ---- Guardar/tabla ----
    def guardar_datos(self):
        self._save_doc_cache(self.modo)
        fila = [c.get() for c in self.campos]
        self.registros.append(fila)
        self.area_texto.insert("end", "\n[OK] Registro guardado.\n")
        self._actualizar_progreso()
        print("Registro guardado:", fila)

    def ver_exportar_tabla(self):
        abrir_tabla_registros(self.parent, self.headers, self.registros)

    # ---- Helpers: páginas/textos/imagen ----
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
        self.area_texto.delete("1.0", tk.END)
        self.area_texto.insert("1.0", self._texto_actual())
        self._completar_nit_y_fecha()
        self.viewer.show_page(on_page_change=change)
        self._actualizar_progreso()

    def _procesar_actual(self):
        if self.modo == "factura" and self.factura_actual:
            procesar_factura(
                self.factura_actual, self.campos, self.area_texto,
                pagina_index=self.indice,
                imagen_pagina=self._imagen_actual(),
                texto_ocr=self._texto_actual(),
            )
        elif self.modo == "orden" and self.orden_actual:
            procesar_orden(
                self.orden_actual, self.campos, self.area_texto,
                pagina_index=self.indice,
                imagen_pagina=self._imagen_actual(),
                texto_ocr=self._texto_actual()
            )

    # ---- Cache por página/mode ----
    def _snapshot_campos(self):
        return [c.get() for c in self.campos]

    def _restore_campos(self, valores):
        if not valores or len(valores) != len(self.campos):
            return False
        for entry, val in zip(self.campos, valores):
            entry.delete(0, "end")
            entry.insert(0, val)
        return True

    def _new_cache_entry(self):
        return {"values_factura": None, "values_orden": None, "has_factura": False, "has_orden": False}

    def _save_doc_cache(self, source: str):
        if not self._paginas_actuales():
            return
        snap = self._snapshot_campos()
        entry = self.doc_cache.get(self.indice) or self._new_cache_entry()
        if source == "factura":
            entry["values_factura"] = snap
            entry["has_factura"] = True
        elif source == "orden":
            entry["values_orden"] = snap
            entry["has_orden"] = True
        self.doc_cache[self.indice] = entry

    def _restore_or_process(self):
        entry = self.doc_cache.get(self.indice)
        if entry:
            if self.modo == "factura" and entry.get("has_factura") and entry.get("values_factura"):
                self._restore_campos(entry["values_factura"]); return True
            if self.modo == "orden" and entry.get("has_orden") and entry.get("values_orden"):
                self._restore_campos(entry["values_orden"]);   return True
        self._procesar_actual()
        self._save_doc_cache(self.modo)
        return False

    # ---- NIT + Fecha revisión ----
    def _completar_nit_y_fecha(self):
        texto_factura = "\n".join(self.factura_textos) if self.factura_textos else ""
        texto_orden   = "\n".join(self.orden_textos)   if self.orden_textos   else ""
        nit, nombre, regional = buscar_nit_valido(texto_factura, texto_orden, self.concesionarios)
        if nit and not self.campos[4].get().strip():
            self.campos[4].insert(0, nit)
        if nombre and not self.campos[5].get().strip():
            self.campos[5].insert(0, nombre)
        if regional and not self.campos[6].get().strip():
            self.campos[6].insert(0, regional)

        fecha_actual = datetime.today().strftime('%Y-%m-%d')
        self.campos[19].delete(0, "end"); self.campos[19].insert(0, fecha_actual)

    # ---- Progressbar ----
    def _calcular_progreso(self):
        total = len(self.campos) if hasattr(self, "campos") else 0
        llenos = sum(1 for c in self.campos if c.get().strip()) if total else 0
        pct = (llenos / total) * 100 if total else 0.0
        return llenos, total, pct

    def _actualizar_progreso(self):
        llenos, total, pct = self._calcular_progreso()
        if hasattr(self, "lbl_progreso"):
            self.lbl_progreso.config(text=f"Campos completados: {llenos}/{total} ({pct:.1f}%)")
        if hasattr(self, "progreso"):
            self.progreso["maximum"] = total if total else 1
            self.progreso["value"] = llenos

    def _on_entry_change(self, _event=None):
        if hasattr(self, "_prog_after_id"):
            self.parent.after_cancel(self._prog_after_id)
        self._prog_after_id = self.parent.after(80, self._actualizar_progreso)

    # ---- Cálculos COP ----
    def _parse_cop(self, s: str) -> int:
        import re
        s = (s or "").strip()
        s = s.replace(".", "").replace(",", "")
        s = re.sub(r"[^\d-]", "", s)
        try:
            return int(s) if s else 0
        except Exception:
            return 0

    def _format_cop(self, n: int) -> str:
        return f"{max(n, 0):,}"

    def _recalc_repuestos(self, *_):
        total = self._parse_cop(self.campos[29].get())
        mano  = self._parse_cop(self.campos[30].get())
        rep   = max(total - mano, 0)
        self.campos[31].delete(0, "end")
        self.campos[31].insert(0, str(int(rep)))

    # ---- Scroll lista de campos (solo dentro del canvas) ----
    def _activa_scroll_campos(self, *_):
        self.canvas_campos.bind("<MouseWheel>", self._on_scroll_campos)
        self.canvas_campos.bind("<Button-4>",  self._on_scroll_campos_linux)
        self.canvas_campos.bind("<Button-5>",  self._on_scroll_campos_linux)

    def _desactiva_scroll_campos(self, *_):
        self.canvas_campos.unbind("<MouseWheel>")
        self.canvas_campos.unbind("<Button-4>")
        self.canvas_campos.unbind("<Button-5>")

    def _on_scroll_campos(self, event):
        delta = -1 if event.delta > 0 else 1
        self.canvas_campos.yview_scroll(delta, "units")
        return "break"

    def _on_scroll_campos_linux(self, event):
        self.canvas_campos.yview_scroll(-1 if event.num == 4 else 1, "units")
        return "break"
    
    def _refresh_viewer_scrollbars(self, *_):
        try:
            if not (hasattr(self, "viewer") and hasattr(self.viewer, "canvas")):
                return
            cv = self.viewer.canvas

            # Actualizar región de scroll según el contenido
            region = cv.bbox("all")
            if region is None:
                # Si no hay contenido, oculta barras
                self.vscroll.grid_remove()
                self.hscroll.grid_remove()
                return

            cv.configure(scrollregion=region)

            # Tamaños visibles del canvas
            cw = cv.winfo_width()  or 1
            ch = cv.winfo_height() or 1
            # Tamaños del contenido
            x0, y0, x1, y1 = region
            rw = max(1, x1 - x0)
            rh = max(1, y1 - y0)

            # Mostrar/ocultar según necesidad
            if rh > ch:
                self.vscroll.grid()       # mostrar
            else:
                self.vscroll.grid_remove() # ocultar

            if rw > cw:
                self.hscroll.grid()       # mostrar
            else:
                self.hscroll.grid_remove() # ocultar
        except Exception:
            # Nunca revientes la UI por un detalle de scroll
            pass


    # ---- Zoom wrappers (para botones) ----
    def _zoom_in(self):
        try:
            self.viewer.zoom_in()
        except Exception:
            pass

    def _zoom_out(self):
        try:
            self.viewer.zoom_out()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = LectorGarantiasApp(root)
    root.mainloop()
