import tkinter as tk
from tkinter import ttk, filedialog
from viewer import PageViewer
from PIL import Image
import csv, os, re
from tkinter import Toplevel, messagebox
from pdf_io import leer_pdf_con_ocr

from ia_factura_gsm import extraer_numero_factura_gsm
from campos import calcular_valores_campos
from BusquedaRef import buscar_referencias_en_texto, unir_lineas_cortadas
from items_costos import imprimir_top_costosos, item_mas_costoso, extraer_mano_obra

class LectorGSMApp:
    def __init__(self, root: tk.Tk = None, host: tk.Widget = None):
        self.standalone = host is None
        self.parent = host if host is not None else root
        if self.standalone:
            self.parent.title("LECTOR GSM")
            self.parent.geometry("1200x800")
            try:
                self.parent.state("zoomed")
            except:
                try:
                    self.parent.attributes("-zoomed", True)
                except:
                    pass

        self.modo_lectura = tk.StringVar(value="separados")  # "separados" | "juntos"
        self.factura_docs = []
        self.orden_docs = []
        self.factura_index = []  
        self.orden_index = []    
        self.idx_factura = 0
        self.idx_orden = 0
        self.pos = 0

        self.modo = "factura"          
        self.doc_cache = {}
        self.parent.grid_rowconfigure(1, weight=1)
        self.parent.grid_columnconfigure(0, weight=3, minsize=500)
        self.parent.grid_columnconfigure(1, weight=2, minsize=300)
        self.parent.grid_columnconfigure(2, weight=2, minsize=320)
        self._build_topbar()
        self._build_viewer()
        self._build_ocr()
        self._build_form_fields()
        self._build_progressbar()

    def _build_topbar(self):
        self.topbar = ttk.Frame(self.parent, padding=(8, 6))
        self.topbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.topbar.grid_columnconfigure(99, weight=1)
        tk.Button(self.topbar, text="Cargar Factura", command=self.subir_factura, bg="lightblue").grid(row=0, column=0, padx=4)
        tk.Button(self.topbar, text="Cargar Orden", command=self.subir_orden, bg="lightgreen").grid(row=0, column=1, padx=4)
        ttk.Button(self.topbar, text="← Anterior", command=self.anterior).grid(row=0, column=2, padx=4)
        ttk.Button(self.topbar, text="Siguiente →", command=self.siguiente).grid(row=0, column=3, padx=4)
        tk.Button(self.topbar, text="Ver Factura", command=self.ver_factura, bg="lightblue").grid(row=0, column=4, padx=4)
        tk.Button(self.topbar, text="Ver Orden", command=self.ver_orden, bg="lightgreen").grid(row=0, column=5, padx=4)

        tk.Button(self.topbar, text="Extraer (OCR)", command=self.extraer_ocr, bg="#e6e6e6").grid(row=0, column=6, padx=8)
        tk.Button(self.topbar, text="Extraer (IA)",  command=self.extraer_ia,  bg="#fff6bf").grid(row=0, column=7, padx=4)

        ttk.Label(self.topbar, text="Modo:").grid(row=0, column=8, padx=(12,4))
        cb = ttk.Combobox(self.topbar, textvariable=self.modo_lectura, values=["separados","juntos"], width=11, state="readonly")
        cb.grid(row=0, column=9)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._reconstruir_indices())

    def _build_viewer(self):
        viewer_wrap = ttk.Frame(self.parent, padding=(8, 8))
        viewer_wrap.grid(row=1, column=0, sticky="nsew")
        viewer_wrap.grid_rowconfigure(0, weight=1)
        viewer_wrap.grid_columnconfigure(0, weight=1)

        self.viewer_host = ttk.Frame(viewer_wrap)
        self.viewer_host.grid(row=0, column=0, sticky="nsew")
        self.viewer_host.grid_rowconfigure(0, weight=1)
        self.viewer_host.grid_columnconfigure(0, weight=1)


        self.viewer = PageViewer(self.viewer_host, x=0, y=0, w=800, h=1000)

        self.viewer.set_image_getter(self._imagen_actual)
        self.viewer.bind_zoom_shortcuts()

        def _on_resize(_e=None):
            w = max(1, self.viewer_host.winfo_width())
            h = max(1, self.viewer_host.winfo_height())
            try:
                self.viewer.canvas.config(width=w, height=h)
            except:
                pass
            self.viewer.show_page(on_page_change=False)

        self.viewer_host.bind("<Configure>", _on_resize)

    def _abrir_varios_pdfs(self) -> tuple:
        paths = filedialog.askopenfilenames(
            title="Seleccionar PDF(s)",
            filetypes=[("PDF", "*.pdf")]
        )
        return tuple(p for p in paths if p)

    def _leer_doc(self, path: str):
        try:
            textos, imgs = leer_pdf_con_ocr(path, lang="eng+spa")
        except Exception as e:
            print(f"[OCR] error {path}: {e}")
            textos, imgs = [], []
        name = os.path.basename(path)
        n = min(len(textos), len(imgs)) if imgs else len(textos)
        return {"path": path, "name": name, "textos": textos, "imgs": imgs, "n": max(n, 0)}

    def _rebuild_index_side(self, docs: list) -> list:
        idx = []
        if self.modo_lectura.get() == "separados":
            for i, d in enumerate(docs):
                if d["n"] > 0:
                    idx.append((i, 0))  # solo 1ra página
        else:
            for i, d in enumerate(docs):
                for p in range(d["n"]):
                    idx.append((i, p))
        return idx
    
    def _resolver_actual(self):
        pos = self.pos  
        if self.modo == "factura":
            if not self.factura_index or not self.factura_docs:
                return None, 0
            doc_idx, page_idx = self.factura_index[min(pos, len(self.factura_index)-1)]
            return self.factura_docs[doc_idx], page_idx
        else:  # "orden"
            if not self.orden_index or not self.orden_docs:
                return None, 0
            doc_idx, page_idx = self.orden_index[min(pos, len(self.orden_index)-1)]
            return self.orden_docs[doc_idx], page_idx
        
    def _conteo_lado(self, lado: str) -> int:
        if lado == "factura":
            return len(self.factura_docs) if self.modo_lectura.get() == "separados" else len(self.factura_index)
        else:
            return len(self.orden_docs) if self.modo_lectura.get() == "separados" else len(self.orden_index)

    def _pair_len(self) -> int:
        # número de parejas disponibles (por índice ya expandido)
        return min(len(self.factura_index), len(self.orden_index))

    def _validar_pairs_listos(self) -> tuple[bool, int]:
        nf = self._conteo_lado("factura")
        no = self._conteo_lado("orden")
        if nf == 0 or no == 0:
            messagebox.showwarning("Faltan archivos", "Debes cargar facturas y órdenes antes de extraer.")
            return False, 0
        if nf != no:
            messagebox.showwarning("Desbalance", f"La cantidad no coincide:\nFacturas: {nf}\nÓrdenes: {no}")
            return False, 0
        return True, nf

    def _texto_img_por_pos(self, lado: str, pos: int):
        if lado == "factura":
            if self.modo_lectura.get() == "separados":
                if 0 <= pos < len(self.factura_docs):
                    d = self.factura_docs[pos]
                    txt = d["textos"][0] if d["n"] > 0 else ""
                    img = d["imgs"][0] if d["n"] > 0 and d["imgs"] and d["imgs"][0] is not None else None
                    return txt or "", img
            else:  # juntos
                if 0 <= pos < len(self.factura_index):
                    doc_idx, page_idx = self.factura_index[pos]
                    d = self.factura_docs[doc_idx]
                    txt = d["textos"][page_idx] if page_idx < d["n"] else ""
                    img = d["imgs"][page_idx] if d["imgs"] and page_idx < len(d["imgs"]) else None
                    return txt or "", img
        else:  # lado == "orden"
            if self.modo_lectura.get() == "separados":
                if 0 <= pos < len(self.orden_docs):
                    d = self.orden_docs[pos]
                    txt = d["textos"][0] if d["n"] > 0 else ""
                    img = d["imgs"][0] if d["n"] > 0 and d["imgs"] and d["imgs"][0] is not None else None
                    return txt or "", img
            else:  # juntos
                if 0 <= pos < len(self.orden_index):
                    doc_idx, page_idx = self.orden_index[pos]
                    d = self.orden_docs[doc_idx]
                    txt = d["textos"][page_idx] if page_idx < d["n"] else ""
                    img = d["imgs"][page_idx] if d["imgs"] and page_idx < len(d["imgs"]) else None
                    return txt or "", img
        return "", None

    def _fila_desde_pairs(self, pairs: list[tuple[int, str]]) -> list[str]:
        fila = ["" for _ in range(len(self.headers))]
        for idx, val in pairs:
            if 0 <= idx < len(fila):
                fila[idx] = str(val or "")
        return fila

    def _post_ocr_enriquecer(self, texto_plano: str):
        try:
            # Ranking (sólo imprime en consola)
            imprimir_top_costosos(texto_plano, k=3)
            mx = item_mas_costoso(texto_plano)
            if mx:
                print(f"[COSTO][max_only] {mx['ref']} | {mx['desc']} | valor={mx['valor']:,}")
        except Exception as e:
            print(f"[WARN] ranking costos: {e}")

        try:
            mo = extraer_mano_obra(texto_plano) or 0
            if mo:
                # Campo 30 = Mano de obra (según tu orden actual)
                self.campos[30].delete(0, "end")
                self.campos[30].insert(0, str(mo))
            self._recalc_repuestos()
            self.parent.after_idle(self._recalc_repuestos)
        except Exception as e:
            print(f"[WARN] mano de obra: {e}")


    def _reconstruir_indices(self):
        self.factura_index = self._rebuild_index_side(self.factura_docs)
        self.orden_index   = self._rebuild_index_side(self.orden_docs)

        # Ajusta self.pos a los límites válidos de parejas
        n = self._pair_len()
        if n > 0:
            self.pos = min(self.pos, n - 1)
        else:
            self.pos = 0

        # Mantén los índices de lado alineados con pos
        self.idx_factura = min(self.pos, len(self.factura_index) - 1) if self.factura_index else 0
        self.idx_orden   = min(self.pos, len(self.orden_index) - 1)   if self.orden_index   else 0

        self.mostrar_pagina(change=True)

    def _build_ocr(self):
        ocr_wrap = ttk.Frame(self.parent, padding=(8, 8))
        ocr_wrap.grid(row=1, column=1, sticky="nsew")
        ocr_wrap.grid_rowconfigure(0, weight=1)
        ocr_wrap.grid_columnconfigure(0, weight=1)
        self.area_texto = tk.Text(ocr_wrap, wrap="word")
        self.area_texto.grid(row=0, column=0, sticky="nsew")
        scroll_texto = tk.Scrollbar(ocr_wrap, orient="vertical", command=self.area_texto.yview, width=8, relief="flat", highlightthickness=0, bd=0)
        scroll_texto.grid(row=0, column=1, sticky="ns")
        self.area_texto.configure(yscrollcommand=scroll_texto.set)

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
        self.canvas_campos.bind("<Configure>", lambda e: self.canvas_campos.itemconfigure("frame", width=e.width))
        self.frame_campos.bind("<Configure>", lambda e: self.canvas_campos.configure(scrollregion=self.canvas_campos.bbox("all")))
        self.campos = []
        nombres = [
            "Numero de Factura","Fecha de recepcion","Numero de guia - Empresa","Numero de solicitud",
            "Nit concesionario","Concesionario","Regional Responsable","Agencia","Chasis","Motor","Placa",
            "Modelo","Modelo especifico","Casa Matriz","Fecha de venta","Fecha de daño","Periodo de garantia",
            "Kilometraje","Rango de kilometraje","Fecha de revision","Clasificacion","Referencia","Descripcion",
            "Descripcion de la falla","clase de daño","Cobro de casamatriz","Responsable de la falla",
            "Observaciones","Factura interna","Valor total Factura","Mano de obra","Costo Total de repuestos",
            "Fecha expedicion Factura","Estado"
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
        self.headers = nombres[:]
        self.registros = []
        self._actualizar_progreso()
        if not self.campos[30].get().strip():
            self.campos[30].insert(0, "0")
        for i in (29, 30):
            self.campos[i].bind("<KeyRelease>", self._recalc_repuestos, add="+")
            self.campos[i].bind("<FocusOut>", self._recalc_repuestos, add="+")
        self.canvas_campos.bind("<Enter>", self._activa_scroll_campos)
        self.canvas_campos.bind("<Leave>", self._desactiva_scroll_campos)

    def _build_progressbar(self):
        bottom = ttk.Frame(self.parent, padding=(8, 8))
        bottom.grid(row=2, column=0, columnspan=3, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=2)
        bottom.grid_columnconfigure(2, weight=1)
        left = ttk.Frame(bottom)
        left.grid(row=0, column=0, sticky="w")
        ttk.Button(left, text="Zoom -", command=self._zoom_out).pack(side="left", padx=(0,6))
        ttk.Button(left, text="Zoom +", command=self._zoom_in).pack(side="left")
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
        except:
            pass
        right = ttk.Frame(bottom)
        right.grid(row=0, column=2, sticky="e")
        tk.Button(right, text="Ver / Exportar", command=self.ver_exportar_tabla, bg="orange").pack(side="left", padx=(0,6))
        tk.Button(right, text="Guardar", command=self.guardar_datos, bg="khaki").pack(side="left")
        self._actualizar_progreso()

    def ver_factura(self):
        self._save_doc_cache(self.modo)
        self.modo = "factura"
        self.idx_factura = min(self.pos, len(self.factura_index) - 1) if self.factura_index else 0
        self.mostrar_pagina(change=True)

    def ver_orden(self):
        self._save_doc_cache(self.modo)
        self.modo = "orden"
        self.idx_orden = min(self.pos, len(self.orden_index) - 1) if self.orden_index else 0
        self.mostrar_pagina(change=True)

    def siguiente(self):
        self._save_doc_cache(self.modo)
        n = self._pair_len()
        if n <= 0:
            return
        self.pos = min(self.pos + 1, n - 1)
        self.idx_factura = min(self.pos, len(self.factura_index) - 1) if self.factura_index else 0
        self.idx_orden   = min(self.pos, len(self.orden_index) - 1)   if self.orden_index   else 0
        self.mostrar_pagina(change=True)

    def anterior(self):
        self._save_doc_cache(self.modo)
        n = self._pair_len()
        if n <= 0:
            return
        self.pos = max(self.pos - 1, 0)
        self.idx_factura = min(self.pos, len(self.factura_index) - 1) if self.factura_index else 0
        self.idx_orden   = min(self.pos, len(self.orden_index) - 1)   if self.orden_index   else 0
        self.mostrar_pagina(change=True)

    
    def subir_factura(self):
        paths = self._abrir_varios_pdfs()
        if not paths: return
        self.factura_docs = [self._leer_doc(p) for p in paths]
        self.modo = "factura"
        self.idx_factura = 0
        self._reconstruir_indices()

    def mostrar_pagina(self, change=False):
        for e in getattr(self, "campos", []):
            e.delete(0, "end")
        try:
            entry = self.doc_cache.get(self._cache_key())
            if entry:
                if self.modo == "factura" and entry.get("values_factura"):
                    self._restore_campos(entry["values_factura"])
                elif self.modo == "orden" and entry.get("values_orden"):
                    self._restore_campos(entry["values_orden"])
        except Exception as e:
            print("[cache] warn:", e)

        # texto OCR visible
        self.area_texto.delete("1.0", "end")
        self.area_texto.insert("end", self._texto_actual())

        # imagen visible
        self.viewer.show_page(on_page_change=change)
        self._actualizar_progreso()

    def subir_orden(self):
        paths = self._abrir_varios_pdfs()
        if not paths: return
        self.orden_docs = [self._leer_doc(p) for p in paths]
        self.modo = "orden"
        self.idx_orden = 0
        self._reconstruir_indices()
        
    def guardar_datos(self):
        fila = [c.get() for c in self.campos]
        self.registros.append(fila)
        self._save_doc_cache(self.modo)
        self.area_texto.insert("end", "\n[OK] Registro guardado (diseño).")
        self._actualizar_progreso()

    def ver_exportar_tabla(self):
        win = Toplevel(self.parent)
        win.title("Registros guardados")
        win.geometry("800x500")
        frm = ttk.Frame(win, padding=8)
        frm.pack(fill="both", expand=True)

        tree = ttk.Treeview(frm, columns=[f"c{i}" for i in range(len(self.headers))], show="headings")
        tree.pack(fill="both", expand=True)
        for i, h in enumerate(self.headers):
            tree.heading(f"c{i}", text=h)
            tree.column(f"c{i}", width=120, anchor="w")
        for row in self.registros:
            tree.insert("", "end", values=row)

        def _export_csv():
            try:
                ruta = filedialog.asksaveasfilename(
                    title="Exportar CSV",
                    defaultextension=".csv",
                    filetypes=[("CSV", "*.csv")]
                )
                if not ruta:
                    return
                with open(ruta, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(self.headers)
                    w.writerows(self.registros)
                messagebox.showinfo("Exportación", f"Archivo guardado:\n{ruta}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo exportar: {e}")

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Exportar CSV", command=_export_csv).pack(side="right")

    def _imagen_actual(self):
        try:
            d, p = self._resolver_actual()
            if d and 0 <= p < len(d.get("imgs", [])) and d["imgs"][p] is not None:
                return d["imgs"][p]
        except:
            pass
        if not hasattr(self, "_placeholder_img"):
            self._placeholder_img = Image.new("RGB", (900, 1200), "#f6f6f6")
        return self._placeholder_img
    
    def _texto_de_lado(self, lado: str, primera_pagina=True) -> str:
        docs = self.factura_docs if lado == "factura" else self.orden_docs
        if not docs:
            return ""
        if primera_pagina:
            d = docs[0]
            return (d["textos"][0] if d["n"] > 0 else "") or ""
        modo = self.modo
        self.modo = lado
        txt = self._texto_actual()
        self.modo = modo
        return txt or ""

    def _texto_actual(self):
        d, p = self._resolver_actual()
        if d and 0 <= p < len(d.get("textos", [])):
            return d["textos"][p] or ""
        return ""

    def extraer_ocr(self):
        # 1) Validación de pares
        ok, n = self._validar_pairs_listos()
        if not ok:
            txt_actual = self._texto_actual() or ""
            img_actual = self._imagen_actual()
            txt_fact_ref = self._texto_de_lado("factura", primera_pagina=True) if hasattr(self, "_texto_de_lado") else ""
            txt_ord_ref  = self._texto_de_lado("orden", primera_pagina=True)   if hasattr(self, "_texto_de_lado") else ""

            pairs = calcular_valores_campos(
                modo=self.modo,
                texto_actual=txt_actual,
                imagen_actual=img_actual,
                texto_factura=txt_fact_ref,
                img_factura=None,
                texto_orden=txt_ord_ref,
                img_orden=None,
                estrategia="prefer_modo",
            )
            for idx, val in pairs:
                if 0 <= idx < len(self.campos):
                    self.campos[idx].delete(0, "end")
                    self.campos[idx].insert(0, val)

            self._post_ocr_enriquecer(txt_actual)
            self._actualizar_progreso()
            return

        if not messagebox.askyesno("Confirmar", f"¿Deseas escanear {n} pareja(s) Factura–Orden?"):
            txt_actual = self._texto_actual() or ""
            img_actual = self._imagen_actual()
            txt_fact_ref = self._texto_de_lado("factura", primera_pagina=True) if hasattr(self, "_texto_de_lado") else ""
            txt_ord_ref  = self._texto_de_lado("orden", primera_pagina=True)   if hasattr(self, "_texto_de_lado") else ""

            pairs = calcular_valores_campos(
                modo=self.modo,
                texto_actual=txt_actual,
                imagen_actual=img_actual,
                texto_factura=txt_fact_ref,
                img_factura=None,
                texto_orden=txt_ord_ref,
                img_orden=None,
                estrategia="prefer_modo",
            )
            for idx, val in pairs:
                if 0 <= idx < len(self.campos):
                    self.campos[idx].delete(0, "end")
                    self.campos[idx].insert(0, val)

            self._post_ocr_enriquecer(txt_actual)
            self._actualizar_progreso()
            return

        procesadas = 0
        for pos in range(n):
            txt_fact, img_fact = self._texto_img_por_pos("factura", pos)
            txt_ord,  img_ord  = self._texto_img_por_pos("orden",   pos)

         
            pairs = calcular_valores_campos(
                modo="factura",
                texto_actual=txt_fact or "",
                imagen_actual=img_fact,
                texto_factura=txt_fact or "",
                img_factura=img_fact,
                texto_orden=txt_ord or "",
                img_orden=img_ord,
                estrategia="prefer_modo",
            )
            fila = self._fila_desde_pairs(pairs)

            texto_plano = (txt_ord or "") + "\n" + (txt_fact or "")

            for idx, val in enumerate(fila):
                if 0 <= idx < len(self.campos):
                    self.campos[idx].delete(0, "end")
                    self.campos[idx].insert(0, val)
            self._post_ocr_enriquecer(texto_plano)

            for idx, entry in enumerate(self.campos):
                if 0 <= idx < len(fila):
                    fila[idx] = entry.get()
            
            self._set_cache_for_pos(pos, fila)

            # Guardar en registros
            self.registros.append(fila)
            procesadas += 1

        messagebox.showinfo("Listo", f"Escaneo completado: {procesadas} pareja(s). Puedes revisar o exportar.")

        
    def extraer_ia(self):
        """
        Modo consola:
        - Si hay pares Factura–Orden listos: procesa TODO el lote y solo imprime resultados.
        - Si no hay pares: procesa la página visible actual y la imprime.
        No modifica UI ni registros.
        """
        try:
            ok, n = self._validar_pairs_listos()
        except Exception as e:
            print("[IA] Validación falló:", e)
            ok, n = False, 0

        # --- LOTE: mismas parejas que usas en OCR ---
        if ok and n > 0:
            print(f"[IA] Escaneando {n} pareja(s) Factura–Orden...\n")
            total_ok = 0

            # helper opcional para mostrar nombre de archivo de la factura
            def _nombre_factura_por_pos(pos: int) -> str:
                try:
                    if self.modo_lectura.get() == "separados":
                        return self.factura_docs[pos]["name"]
                    else:
                        doc_idx, _page_idx = self.factura_index[pos]
                        return self.factura_docs[doc_idx]["name"]
                except Exception:
                    return f"factura_pos_{pos+1}"

            for pos in range(n):
                try:
                    txt_fact, img_fact = self._texto_img_por_pos("factura", pos)
                    if img_fact is None:
                        print(f"[IA] ({pos+1}/{n}) { _nombre_factura_por_pos(pos) } -> (sin imagen)")
                        continue

                    data = extraer_numero_factura_gsm(img_fact, texto_hint=txt_fact) or {}
                    num = (data.get("numero_factura") or "").strip()
                    if num:
                        total_ok += 1
                    print(f"[IA] ({pos+1}/{n}) { _nombre_factura_por_pos(pos) } -> { num or '—' }")

                except Exception as e:
                    print(f"[IA] ({pos+1}/{n}) error:", e)

            print(f"\n[IA] Listo. Detectadas {total_ok}/{n} facturas con número.")
            return

        # --- PÁGINA ACTUAL: si no hay pares cargados ---
        try:
            img = self._imagen_actual()
            txt = self._texto_actual() or ""
            data = extraer_numero_factura_gsm(img, texto_hint=txt) or {}
            num = (data.get("numero_factura") or "").strip()
            print(f"[IA] Página actual -> { num or '—' }")
        except Exception as e:
            print("[IA] Error página actual:", e)

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
    
    def _cache_key(self, modo=None, pos=None):
        lado = modo or self.modo
        if pos is None:
            pos = self.pos

        if lado == "factura":
            if 0 <= pos < len(self.factura_index):
                doc_idx, page_idx = self.factura_index[pos]
            else:
                doc_idx, page_idx = -1, -1
        else:  # orden
            if 0 <= pos < len(self.orden_index):
                doc_idx, page_idx = self.orden_index[pos]
            else:
                doc_idx, page_idx = -1, -1

        return (lado, doc_idx, page_idx)
    
    def _set_cache_for_pos(self, pos: int, fila: list[str]):
        # Guarda la misma fila como valores para 'factura' y 'orden' en la posición pos
        for lado in ("factura", "orden"):
            key = self._cache_key(modo=lado, pos=pos)
            entry = self.doc_cache.get(key) or self._new_cache_entry()
            if lado == "factura":
                entry["values_factura"] = fila[:]
                entry["has_factura"] = True
            else:
                entry["values_orden"] = fila[:]
                entry["has_orden"] = True
            self.doc_cache[key] = entry

    def _save_doc_cache(self, source: str):
        snap = self._snapshot_campos()
        key = self._cache_key()
        entry = self.doc_cache.get(key) or self._new_cache_entry()
        if source == "factura":
            entry["values_factura"] = snap
            entry["has_factura"] = True
        elif source == "orden":
            entry["values_orden"] = snap
            entry["has_orden"] = True
        self.doc_cache[key] = entry

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

    def _parse_cop(self, s: str) -> int:
        s = (s or "").strip()
        s = s.replace(".", "").replace(",", "")
        s = re.sub(r"[^\d-]", "", s)
        try:
            return int(s) if s else 0
        except:
            return 0

    def _format_cop(self, n: int) -> str:
        return f"{max(n, 0):,}"

    def _recalc_repuestos(self, *_):
        total = self._parse_cop(self.campos[29].get())
        mano = self._parse_cop(self.campos[30].get())
        rep = max(total - mano, 0)
        self.campos[31].delete(0, "end")
        self.campos[31].insert(0, str(int(rep)))

    def _activa_scroll_campos(self, *_):
        self.canvas_campos.bind("<MouseWheel>", self._on_scroll_campos)
        self.canvas_campos.bind("<Button-4>", self._on_scroll_campos_linux)
        self.canvas_campos.bind("<Button-5>", self._on_scroll_campos_linux)

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

    def _zoom_in(self):
        try:
            self.viewer.zoom_in()
        except:
            pass

    def _zoom_out(self):
        try:
            self.viewer.zoom_out()
        except:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = LectorGSMApp(root)
    root.mainloop()
