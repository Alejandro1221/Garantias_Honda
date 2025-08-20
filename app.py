import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from datetime import datetime
from tabla_registros import abrir_tabla_registros

from PIL import Image  

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
        self.doc_cache = {}

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
        self._construir_progreso()
    
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
            "Chasis",#8
            "Motor",#9
            "Placa",#10
            "Modelo",#11
            "Modelo especifico",#12
            "Casa Matriz",#13
            "Fecha de venta",#14
            "Fecha de daño",#15
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
            "Valor total Factura", #329
            "Mano de obra", #30
            "Costo Total de repuestos", #31
            "Fecha expedicion Factura", #32
            "Estado" #33
        ]
        
        for nombre in nombres:
            tk.Label(self.frame_campos, text=nombre + ":", anchor="w", font=("Arial", 9)).pack(fill="x", padx=5, pady=2)
            entrada = tk.Entry(self.frame_campos)
            entrada.pack(fill="x", padx=5, pady=2)

            entrada.bind("<KeyRelease>", self._on_entry_change)
            entrada.bind("<<Paste>>", self._on_entry_change)
            entrada.bind("<<Cut>>", self._on_entry_change)
            entrada.bind("<FocusOut>", self._on_entry_change)
            self.campos.append(entrada)

        self.headers = nombres[:]   # títulos de columnas
        self.registros = []         # acumulador de filas guardadas
        self._actualizar_progreso()

    def _construir_botones(self):
        tk.Button(self.root, text="Cargar Factura", command=self.subir_factura, bg="lightblue", width=15).place(x=30, y=20)
        tk.Button(self.root, text="Cargar Orden", command=self.subir_orden, bg="lightgreen", width=15).place(x=180, y=20)
        tk.Button(self.root, text="← Anterior", command=self.anterior, width=12, bg="lightgray").place(x=370, y=20)
        tk.Button(self.root, text="Siguiente →", command=self.siguiente, width=12, bg="lightgray").place(x=500, y=20)
        tk.Button(self.root, text="Ver Factura", command=self.ver_factura, bg="lightblue", width=15).place(x=650, y=20)
        tk.Button(self.root, text="Ver Orden", command=self.ver_orden, bg="lightgreen", width=15).place(x=800, y=20)
        tk.Button(self.root, text="Zoom +", command=self.viewer.zoom_in, width=8, bg="lightgray").place(x=950, y=20)
        tk.Button(self.root, text="Zoom -", command=self.viewer.zoom_out, width=8, bg="lightgray").place(x=1030, y=20)
        tk.Button(self.root, text="Guardar", command=self.guardar_datos, bg="khaki", width=15).place(x=920, y=600)
        tk.Button(self.root, text="Ver / Exportar", command=self.ver_exportar_tabla,bg="orange", width=15).place(x=1040, y= 600)

    # --- Barra de progreso de completitud ---
    def _construir_progreso(self):
        # Contenedor (ajusta posición/tamaño a tu gusto)
        self.progreso_frame = tk.Frame(self.root)
        self.progreso_frame.place(x=350, y=600, width=430)

        # Label con conteo
        self.lbl_progreso = tk.Label(
            self.progreso_frame,
            text="Campos completados: 0/0 (0.0%)",
            font=("Arial", 10, "bold")
        )
        self.lbl_progreso.pack(fill="x", pady=(0, 4))

        # Progressbar
        self.progreso = ttk.Progressbar(
            self.progreso_frame,
            orient="horizontal",
            mode="determinate"
        )
        self.progreso.pack(fill="x")

        try:
            style = ttk.Style(self.root)
            style.theme_use("clam")
            style.configure("green.Horizontal.TProgressbar",
                            troughcolor="#eeeeee", background="#4CAF50")
            self.progreso.configure(style="green.Horizontal.TProgressbar")
        except Exception:
            pass  # si falla el tema, seguimos igual

        # Primer cálculo
        self._actualizar_progreso()

        # ---------- Helpers de progreso ----------
    def _calcular_progreso(self):
        total = len(self.campos) if hasattr(self, "campos") else 0
        llenos = sum(1 for c in self.campos if c.get().strip()) if total else 0
        pct = (llenos / total) * 100 if total else 0.0
        return llenos, total, pct

    def _actualizar_progreso(self):
        llenos, total, pct = self._calcular_progreso()
        if hasattr(self, "lbl_progreso"):
            self.lbl_progreso.config(
                text=f"Campos completados: {llenos}/{total} ({pct:.1f}%)"
            )
        if hasattr(self, "progreso"):
            self.progreso["maximum"] = total if total else 1
            self.progreso["value"] = llenos

    def _on_entry_change(self, event=None):
        if hasattr(self, "_prog_after_id"):
            self.root.after_cancel(self._prog_after_id)
        self._prog_after_id = self.root.after(80, self._actualizar_progreso)

   #----------------------------------------------------------
    def _configurar_scroll_campos(self):
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
    
    def _snapshot_campos(self):
        return [c.get() for c in self.campos]
    
    def _restore_campos(self, valores):
        """Restaura la lista de valores en los Entry (si coincide el largo)."""
        if not valores or len(valores) != len(self.campos):
            return False
        for entry, val in zip(self.campos, valores):
            entry.delete(0, "end")
            entry.insert(0, val)
        return True  
      
    def _new_cache_entry(self):
        return {"values": None, "has_factura": False, "has_orden": False}
    
    def _save_doc_cache(self, source: str):
        """Guarda snapshot y marca que ya se procesó 'factura' u 'orden' para el índice actual."""
        if not self._paginas_actuales():
            return
        snap = self._snapshot_campos()
        entry = self.doc_cache.get(self.indice)
        if not entry:
            entry = self._new_cache_entry()
        entry["values"] = snap
        if source == "factura":
            entry["has_factura"] = True
        elif source == "orden":
            entry["has_orden"] = True
        self.doc_cache[self.indice] = entry 

    def _restore_or_process(self):
        """
        Si ya hay cache para (indice) y ya se procesó la fuente del modo actual,
        restaura desde cache. Si no, procesa y vuelve a cachear.
        """
        entry = self.doc_cache.get(self.indice)
        if entry and entry.get("values") is not None:
            if (self.modo == "factura" and entry.get("has_factura")) or \
            (self.modo == "orden" and entry.get("has_orden")):
                self._restore_campos(entry["values"])
                return True  # restauró desde cache

        # No había cache suficiente → procesar y cachear
        self._procesar_actual()
        self._save_doc_cache(self.modo)
        return False

    # ---------- Acciones ----------
    def subir_factura(self):
        archivo = filedialog.askopenfilename(title="Seleccionar factura PDF", filetypes=[("PDF files", "*.pdf")])
        if not archivo: 
            return
        self.factura_actual = archivo
        self.factura_textos, self.factura_paginas = leer_pdf_con_ocr(archivo)
        
        if not self.orden_paginas:
            self.doc_cache.clear()
        self.modo, self.indice = "factura", 0
        procesar_factura(
            archivo, self.campos, self.area_texto, pagina_index=self.indice,
            imagen_pagina=self._imagen_actual(), 
            texto_dpi_alto=self._texto_actual()  
        )
        self._save_doc_cache("factura")
        self.viewer.show_page(on_page_change=True)
        self._actualizar_progreso()
        
    def subir_orden(self):
        archivo = filedialog.askopenfilename(title="Seleccionar orden PDF", filetypes=[("PDF files", "*.pdf")])
        if not archivo: 
            return
        self.orden_actual = archivo
        self.orden_textos, self.orden_paginas = leer_pdf_con_ocr(archivo)
        
        if not self.factura_paginas:
            self.doc_cache.clear()
        self.modo, self.indice = "orden", 0

        procesar_orden(
        archivo, self.campos, self.area_texto, pagina_index=self.indice,
        imagen_pagina=self._imagen_actual(),          # <- usa imagen cacheada
        texto_ocr=self._texto_actual()                # <- opcional: evita OCR si ya tienes texto
        )
        self._save_doc_cache("orden")
        self.viewer.show_page(on_page_change=True)
        self._actualizar_progreso()

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

    def guardar_datos(self):
        """Guarda snapshot en cache y agrega registro a la tabla."""
        self._save_doc_cache(self.modo)  
        fila = [c.get() for c in self.campos]
        self.registros.append(fila)
        self.area_texto.insert("end", "\n[OK] Registro guardado.\n")
        self._actualizar_progreso()
        print("Registro guardado:", fila)

    # ---------- Registro y tabla ----------
    def ver_exportar_tabla(self):
        abrir_tabla_registros(self.root, self.headers, self.registros)

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
        self._actualizar_progreso()

    def _procesar_actual(self):
        if self.modo == "factura" and self.factura_actual:
            procesar_factura(
                self.factura_actual, self.campos, self.area_texto, pagina_index=self.indice,
                imagen_pagina=self._imagen_actual(),
                texto_ocr=self._texto_actual()
            )
        elif self.modo == "orden" and self.orden_actual:
            procesar_orden(
                self.orden_actual, self.campos, self.area_texto, pagina_index=self.indice,
                imagen_pagina=self._imagen_actual(),
                texto_ocr=self._texto_actual()
            )

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

if __name__ == "__main__":
    root = tk.Tk()
    app = LectorGarantiasApp(root)
    root.mainloop()
