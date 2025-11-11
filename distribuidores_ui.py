import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os, shutil, time, subprocess, sys
from PIL import Image, ImageTk  
import re, unicodedata

# importa las constantes del repo
from distribuidores import (
    DistribuidoresRepo,
    VISIBLE_COLUMNS,  
    EXTRA_COLUMNS,   
)

SI_NO = ("", "SI", "NO")

class DistribuidoresView(ttk.Frame):
    title = "Distribuidores"

    def __init__(self, parent, controller=None, excel_path="Distribuidores.xlsx"):
        super().__init__(parent, padding=10)
        self.repo = DistribuidoresRepo(excel_path, sheet_name="Hoja1")
        self.columns = VISIBLE_COLUMNS
        self._build_ui()
        self._load_table()

    # ---------- UI ----------
    def _build_ui(self):

        # barra superior: búsqueda + progreso
        top = ttk.Frame(self); top.pack(fill="x", pady=(0,8))
        ttk.Label(top, text="Buscar:").pack(side="left")
        self.var_search = tk.StringVar()
        self.ent_search = ttk.Entry(top, textvariable=self.var_search, width=40)
        self.ent_search.pack(side="left", padx=6)
        self.ent_search.bind("<KeyRelease>", lambda e: self._load_table())

        ttk.Button(top, text="🧹", width=3, command=self._limpiar_busqueda).pack(side="left", padx=2)

        self.progress_var = tk.StringVar(value="0 de 0 (0%)")
        ttk.Label(top, textvariable=self.progress_var).pack(side="right")

        # --- FORMULARIO ---------------------------------------------------------
        form = ttk.LabelFrame(self, text="Formulario")
        form.pack(fill="x", pady=(0,8))
        self.vars = {c: tk.StringVar() for c in self.columns}
        if "FOTO" not in self.vars:
            self.vars["FOTO"] = tk.StringVar()
        self.vars["NIT"].trace_add("write", lambda *a: self._update_save_state())


        for c in (0,2,3,8):
            form.grid_columnconfigure(c, weight=0)
        for c in (1,4,5,6,7,9,10,11):
            form.grid_columnconfigure(c, weight=1)

        # Fila 1: NIT + Razon Social 
        r = 0
        ttk.Label(form, text="NIT:", anchor="w").grid(row=r, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.vars["NIT"], width=30, state="readonly")\
            .grid(row=r, column=1, sticky="ew", padx=5, pady=4)

        ttk.Label(form, text="Razón Social:", anchor="w").grid(row=r, column=3, sticky="w", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.vars["RAZON SOCIAL"], width=50, state="readonly")\
            .grid(row=r, column=4, columnspan=4, sticky="ew", padx=5, pady=4)

        # Observaciones ARRIBA a la derecha (ocupa filas 0 y 1)
        ttk.Label(form, text="Observaciones:", anchor="w")\
            .grid(row=0, column=8, sticky="nw", padx=5, pady=(6,0))
        self.txt_obs = tk.Text(form, height=4, width=36, wrap="word")
        self.txt_obs.grid(row=0, column=9, columnspan=3, rowspan=2, sticky="nsew", padx=5, pady=(6,4))

        # Fila 2: Agencia 
        r = 1
        ttk.Label(form, text="Agencia:", anchor="w").grid(row=r, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.vars["AGENCIA"], state="readonly")\
            .grid(row=r, column=1, columnspan=7, sticky="ew", padx=5, pady=4)

        # Fila 3: los 4 combos cortos 
        r = 2
        def make_bool_combo(parent, label, varname, col, row):
            ttk.Label(parent, text=label + ":", anchor="e").grid(row=row, column=col, sticky="e", padx=5, pady=4)
            combo = ttk.Combobox(parent, textvariable=self.vars[varname], width=8,
                                state="readonly", values=SI_NO)
            combo.grid(row=row, column=col+1, sticky="w", padx=5, pady=4)
            return combo

        make_bool_combo(form, "Factura legible", "FACTURA_LEGIBLE", 0, r)  
        make_bool_combo(form, "Orden Fanalca",   "ORDEN_FANALCA",   2, r)  
        make_bool_combo(form, "Orden legible",   "ORDEN_LEGIBLE",   6, r) 
        make_bool_combo(form, "Texto manual",    "TEXTO_MANUAL",    8, r) 
        make_bool_combo(form, "QR", "QR", 10, r)
        
        r = 3
        ttk.Label(form, text="Foto:", anchor="w").grid(row=r, column=0, sticky="w", padx=0.5, pady=4)

        # entrada solo lectura para la ruta relativa
        self.ent_foto = ttk.Entry(form, textvariable=self.vars["FOTO"], state="readonly")
        self.ent_foto.grid(row=r, column=1, columnspan=7, sticky="ew", padx=5, pady=4)

        # botones a la derecha, mismos estilos que los demás
        wrap_foto_btns = ttk.Frame(form)
        wrap_foto_btns.grid(row=r, column=8, columnspan=3, sticky="w", padx=5, pady=4)

        btn_subir = ttk.Button(wrap_foto_btns, text="Subir Foto", command=self._subir_foto)
        btn_subir.pack(side="left", padx=(0,6))

        self.btn_ver_foto = ttk.Button(wrap_foto_btns, text="Ver Foto", command=self._abrir_foto, state="disabled")
        self.btn_ver_foto.pack(side="left")

        btn_borrar_foto = ttk.Button(wrap_foto_btns, text="Eliminar Foto", command=self._eliminar_foto)
        btn_borrar_foto.pack(side="left", padx=(6,0))

        self.vars["FOTO"].trace_add("write", lambda *a: self.btn_ver_foto.config(
            state="normal" if self._sanitize_rel(self.vars["FOTO"].get()) else "disabled"))

        # botones
        btns = ttk.Frame(self); btns.pack(fill="x", pady=(0,8))

        self.btn_save = ttk.Button(btns, text="Guardar / Actualizar",command=self._guardar, state="disabled")
        self.btn_save.pack(side="left", padx=6)

        self.btn_delete = ttk.Button(btns, text="Eliminar",command=self._eliminar, state="disabled")
        self.btn_delete.pack(side="left", padx=6)

        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(btns, text="Importar desde Excel", command=self._importar).pack(side="left", padx=6)
        ttk.Button(btns, text="Exportar", command=self._exportar_all).pack(side="left", padx=6)

        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(btns, text="Refrescar", command=self._load_table).pack(side="left", padx=6)


        # tabla
        table_wrap = ttk.Frame(self); table_wrap.pack(fill="both", expand=True)

        # usar grid dentro de table_wrap
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_wrap, columns=self.columns, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Scroll vertical
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")

        # Scroll horizontal
        xscroll = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")

        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        # IMPORTANTE: que no se estiren; así el ancho total supera al viewport
        for c in self.columns:
            width = 160 if c not in ("OBSERVACIONES", "RAZON SOCIAL", "AGENCIA") else 220
            self.tree.column(c, width=width, anchor="w", stretch=False)
            self.tree.heading(c, text=c)
        self.tree.bind("<Double-1>", self._on_row_double_click)

        # atajos
        self.bind_all("<Control-s>", lambda e: self._guardar())
        # Ctrl+F ahora SOLO enfoca el cuadro de búsqueda
        self.bind_all("<Control-f>", lambda e: (self.ent_search.focus_set(), self.ent_search.select_range(0, 'end')))

    def _foto_abs_path(self):
        rel = (self.vars.get("FOTO").get() if "FOTO" in self.vars else "").strip().strip('"').strip("'")
        if not rel:
            return "", False
        rel = rel.replace("\\", "/").replace("//", "/")

        base = self._base_dir()
        cand = []
        # si ya viene absoluta
        if os.path.isabs(rel):
            cand.append(rel)
        else:
            # relativa al Excel
            cand.append(os.path.abspath(os.path.join(base, rel)))
            # dentro de /fotos (por si solo guardaron nombre o subcarpeta distinta)
            cand.append(os.path.abspath(os.path.join(base, "fotos", rel)))
            cand.append(os.path.abspath(os.path.join(base, "fotos", os.path.basename(rel))))

        for c in cand:
            if os.path.exists(c):
                return c, True
        return cand[0], False
    
    def _sanitize_rel(self, p):
        if p is None: return ""
        s = str(p).strip().strip('"').strip("'")
        return s.replace("\\","/").replace("//","/")
    
    def _safe_filename(self, s: str) -> str:
        if not s:
            return ""
        # quita acentos y normaliza
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = s.strip().lower()
        # reemplaza espacios por guion bajo
        s = re.sub(r"\s+", "_", s)
        # deja solo [a-z0-9._-]
        s = re.sub(r"[^a-z0-9._-]", "", s)
        # evita nombre vacío
        return s or "sin_nombre"


    def _fill_form(self, data: dict):
        for k in self.columns:
            v = data.get(k, "")
            if k == "FOTO":
                v = self._sanitize_rel(v)
            self.vars[k].set("" if pd.isna(v) else str(v))

        # Cargar Observaciones en el Text
        if hasattr(self, "txt_obs"):
            self.txt_obs.delete("1.0", "end")
            self.txt_obs.insert("1.0", data.get("OBSERVACIONES", ""))

        # Habilitar/Deshabilitar "Ver Foto"
        has_photo = bool(self._sanitize_rel(self.vars.get("FOTO", tk.StringVar()).get()))
        if hasattr(self, "btn_ver_foto"):
            self.btn_ver_foto.config(state=("normal" if has_photo else "disabled"))

        # Actualizar estado de Guardar/Eliminar
        self._update_save_state()

    def _read_form_extras(self):
        # lee extras desde el formulario y normaliza
        out = {k: self.vars[k].get().strip() for k in EXTRA_COLUMNS if k != "OBSERVACIONES"}
        out["OBSERVACIONES"] = self.txt_obs.get("1.0", "end").strip() if hasattr(self, "txt_obs") else ""
        # sanitiza la ruta de la foto
        out["FOTO"] = self._sanitize_rel(out.get("FOTO", ""))
        # normaliza SI/NO
        for k in ("FACTURA_LEGIBLE", "ORDEN_FANALCA", "ORDEN_LEGIBLE", "TEXTO_MANUAL", "QR"):
            v = out.get(k, "").upper()
            out[k] = v if v in ("", "SI", "NO") else ""
        return out

    def _base_dir(self):
        return os.path.dirname(os.path.abspath(self.repo.path))

    def _subir_foto(self):
        # 1) Si ya hay una foto, preguntar si desea reemplazarla
        old_rel = self._sanitize_rel(self.vars.get("FOTO").get() if "FOTO" in self.vars else "")
        old_abs = None
        if old_rel:
            # resolver absoluta ANTES de cambiar nada
            abs_try, ok = self._foto_abs_path()
            if ok:
                old_abs = abs_try
            # confirmar reemplazo
            if not messagebox.askyesno("Reemplazar imagen", "¿Deseas reemplazar la imagen existente?"):
                return  # usuario canceló

        # 2) Elegir nueva imagen
        path = filedialog.askopenfilename(
            title="Selecciona imagen",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"), ("Todos", "*.*")]
        )
        if not path:
            return

        base_dir  = self._base_dir()
        fotos_dir = os.path.join(base_dir, "fotos")
        os.makedirs(fotos_dir, exist_ok=True)

        # 3) Construir nombre <nit>_<agencia>.<ext> (seguro)
        nit = (self.vars.get("NIT").get().strip() if "NIT" in self.vars else "")
        agencia = (self.vars.get("AGENCIA").get().strip() if "AGENCIA" in self.vars else "")
        nit_safe = self._safe_filename(nit) or "sin_nit"
        agencia_safe = self._safe_filename(agencia) or "sin_agencia"
        base_name = f"{nit_safe}_{agencia_safe}"
        ext = os.path.splitext(path)[1].lower() or ".jpg"

        dst_name = f"{base_name}{ext}"
        dst_path = os.path.join(fotos_dir, dst_name)
        i = 1
        while os.path.exists(dst_path):
            dst_name = f"{base_name}-{i}{ext}"
            dst_path = os.path.join(fotos_dir, dst_name)
            i += 1

        # 5) Copiar y actualizar campo FOTO
        try:
            shutil.copy2(path, dst_path)
            rel = os.path.relpath(dst_path, start=base_dir).replace("\\", "/")
            self.vars["FOTO"].set(rel)
            messagebox.showinfo("Foto", f"Imagen guardada y renombrada a:\n{dst_name}")
            # 6) Si había foto previa y el usuario aceptó reemplazar, márcala para borrado tras Guardar
            self._pending_delete_old_photo = old_abs if old_rel else None
        except Exception as e:
            messagebox.showerror("Foto", f"No se pudo copiar la imagen:\n{e}")

    
    def _abrir_foto(self):
        abs_path, ok = self._foto_abs_path()
        if not ok:
            if not abs_path:
                messagebox.showinfo("Foto", "No hay imagen asociada.")
            else:
                messagebox.showerror("Foto", f"No se encontró el archivo:\n{abs_path}")
            return

        try:
            self._preview_in_app(abs_path)
            return
        except Exception as e:
            pass

        try:
            if os.name == "nt":
                os.startfile(abs_path)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, abs_path])
        except Exception:
            # 3) Último recurso: URL file://
            import webbrowser
            webbrowser.open(f"file:///{abs_path.replace('\\','/')}")

    def _eliminar_foto(self):
        if messagebox.askyesno("Eliminar foto", "¿Quieres quitar la foto asociada?"):
            self.vars["FOTO"].set("")  # limpiar el campo
            if hasattr(self, "btn_ver_foto"):
                self.btn_ver_foto.config(state="disabled")
            messagebox.showinfo("Foto", "Se eliminó la foto del registro (debes Guardar para aplicar).")

    #----Visor imagen con zoom -------
    def _preview_in_app(self, abs_path):
        top = tk.Toplevel(self)
        top.title(os.path.basename(abs_path))

        # --- Estado: abrir a 0.5x ---
        top._img_orig = Image.open(abs_path)
        w0, h0 = top._img_orig.size
        top._zoom = 0.5        # << abre a 0.5x
        top._min_zoom = 0.1
        top._max_zoom = 8.0

        # --- Toolbar (sin botón "Cerrar") ---
        bar = ttk.Frame(top); bar.pack(fill="x", padx=8, pady=6)

        # --- Área scrollable (Canvas + barras) ---
        wrap = ttk.Frame(top); wrap.pack(fill="both", expand=True, padx=0, pady=0)
        canvas = tk.Canvas(wrap, bg=top.cget("bg"), highlightthickness=0, bd=0)
        vbar = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        hbar = ttk.Scrollbar(wrap, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        # --- Helpers ---
        def _render():
            w, h = top._img_orig.size
            nw, nh = max(1, int(w * top._zoom)), max(1, int(h * top._zoom))
            im = top._img_orig.resize((nw, nh), Image.LANCZOS)
            top._tkimg = ImageTk.PhotoImage(im)
            canvas.delete("IMG")
            canvas.create_image(0, 0, image=top._tkimg, anchor="nw", tags="IMG")
            canvas.config(scrollregion=(0, 0, nw, nh))
            return nw, nh  

        def _zoom_to(z):
            top._zoom = max(top._min_zoom, min(top._max_zoom, z))
            _render()

        def _zoom_by(f):
            _zoom_to(top._zoom * f)

        def _fit_to_window():
            cw, ch = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
            w, h = top._img_orig.size
            s = min(cw / w, ch / h)
            _zoom_to(max(top._min_zoom, min(s, top._max_zoom)))

        # Botones de zoom
        ttk.Button(bar, text="−", width=3, command=lambda: _zoom_by(0.9)).pack(side="left")
        ttk.Button(bar, text="+", width=3, command=lambda: _zoom_by(1.1)).pack(side="left")
        ttk.Button(bar, text="100%", command=lambda: _zoom_to(1.0)).pack(side="left", padx=(6,0))
        ttk.Button(bar, text="Ajustar", command=_fit_to_window).pack(side="left", padx=(6,0))

        # Pan con arrastre
        def _pan_mark(e): canvas.scan_mark(e.x, e.y)
        def _pan_drag(e): canvas.scan_dragto(e.x, e.y, gain=1)
        canvas.bind("<ButtonPress-1>", _pan_mark)
        canvas.bind("<B1-Motion>", _pan_drag)

        # Rueda: scroll / Shift: horizontal / Ctrl: ZOOM (Windows)
        def _on_wheel_scroll(e): canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        def _on_wheel_scroll_h(e): canvas.xview_scroll(-1 if e.delta > 0 else 1, "units")
        def _on_wheel_zoom(e): _zoom_by(1.1 if e.delta > 0 else 0.9)
        canvas.bind("<MouseWheel>", _on_wheel_scroll)
        canvas.bind("<Shift-MouseWheel>", _on_wheel_scroll_h)
        canvas.bind("<Control-MouseWheel>", _on_wheel_zoom)

        # Atajos útiles
        top.bind("<Control-plus>",  lambda e: _zoom_by(1.1))
        top.bind("<Control-minus>", lambda e: _zoom_by(0.9))
        top.bind("<Control-0>",     lambda e: _zoom_to(1.0))
        top.bind("<Escape>",        lambda e: top.destroy())

        nw, nh = _render()
        top.update_idletasks()

        # Medidas reales ya calculadas por Tk
        vbar_w = vbar.winfo_reqwidth()
        hbar_h = hbar.winfo_reqheight()
        bar_w  = bar.winfo_reqwidth()
        bar_h  = bar.winfo_reqheight()

        # El contenido debe caber: ancho = max(imagen+scrollbar, barra)
        content_w = max(nw + vbar_w, bar_w)
        content_h = bar_h + nh + hbar_h

        # Pequeño margen para bordes; cap a pantalla
        extra_w, extra_h = 10,10
        screen_w, screen_h = top.winfo_screenwidth(), top.winfo_screenheight()
        win_w = min(content_w + extra_w, screen_w - 30)
        win_h = min(content_h + extra_h, screen_h - 80)
        top.geometry(f"{int(win_w)}x{int(win_h)}+50+50")

        # Evita que el Canvas arranque más grande que la imagen
        canvas.config(width=nw, height=nh)

        cx = (screen_w - win_w) // 2
        cy = (screen_h - win_h) // 2
        top.geometry(f"{int(win_w)}x{int(win_h)}+{int(cx)}+{int(cy)}")

        
    def _update_save_state(self):
        nit = self.vars["NIT"].get().strip()
        if nit:
            self.btn_save.config(state="normal")
            self.btn_delete.config(state="normal")
        else:
            self.btn_save.config(state="disabled")
            self.btn_delete.config(state="disabled")

    def _limpiar_busqueda(self):
        """Limpia la caja de búsqueda y recarga la tabla."""
        self.var_search.set("")
        self._load_table()
        self.ent_search.focus_set()

    # ---------- actions ----------
    def _load_table(self):
        # limpiar tabla
        for i in self.tree.get_children():
            self.tree.delete(i)

        df = self.repo.list_visible()

        # filtro de texto simple sobre columnas visibles
        q = self.var_search.get().strip().lower()
        if q:
            mask = pd.Series([False]*len(df))
            for c in self.columns:
                mask = mask | df[c].astype(str).str.lower().str.contains(q, na=False)
            df = df[mask]

        for _, row in df.iterrows():
            values = []
            for c in self.columns:
                v = row.get(c, "")
                if c == "FOTO":
                    v = self._sanitize_rel(v)
                values.append(v)
            self.tree.insert("", "end", values=values)

        # actualizar progreso
        done, total, pct = self.repo.completion_stats()
        self.progress_var.set(f"{done} de {total} ({pct:.0f}%)")

    def _guardar(self):
        try:
            nit = self.vars["NIT"].get().strip()
            if not nit:
                messagebox.showinfo("Guardar", "Selecciona un registro (doble clic en la tabla) o filtra y selecciona.")
                return

            # tomar SIEMPRE los datos base desde el repo (solo lectura)
            current = self.repo.get_by_nit(nit) or {"NIT": nit}
            base = {b: current.get(b, "") for b in ("NIT", "RAZON SOCIAL", "AGENCIA")}
            extras = self._read_form_extras()
            payload = {**current, **base, **extras}

            self.repo.upsert(payload)
            self.repo.save()

            # --- borrar la foto anterior de forma segura  ---
            try:
                old_path = getattr(self, "_pending_delete_old_photo", None)
                self._pending_delete_old_photo = None  # limpiar marcador

                if old_path and os.path.exists(old_path):
                    base_dir  = self._base_dir()
                    fotos_dir = os.path.join(base_dir, "fotos")
                    old_abs   = os.path.abspath(old_path)

                    # 1) solo borra si está dentro de /fotos
                    try:
                        if os.path.commonpath([old_abs, os.path.abspath(fotos_dir)]) != os.path.abspath(fotos_dir):
                            old_path = None  # fuera de fotos -> no borrar
                    except ValueError:
                        old_path = None

                    if old_path:
                        # 2) no borres si es el mismo archivo que acabas de dejar
                        new_rel = self._sanitize_rel(self.vars.get("FOTO").get() if "FOTO" in self.vars else "")
                        new_abs = os.path.abspath(os.path.join(base_dir, new_rel)) if new_rel else ""
                        if os.path.normcase(new_abs) != os.path.normcase(old_abs):
                            # 3) no borres si otro registro sigue referenciándolo
                            rel_old_canon = os.path.relpath(old_abs, start=base_dir).replace("\\", "/")
                            df = self.repo.df.copy()
                            # filas que apuntan al mismo rel (sanitizado)
                            same_ref = df["FOTO"].astype(str).str.replace("\\", "/").str.strip() == rel_old_canon
                            # ¿algún otro NIT lo usa?
                            nit = self.vars.get("NIT").get().strip()
                            used_by_others = df[same_ref & (df["NIT"].astype(str).str.strip() != nit)]
                            if used_by_others.empty:
                                try:
                                    os.remove(old_abs)
                                except Exception:
                                    # no interrumpas el guardado si falla el borrado
                                    pass
            except Exception:
                pass
            # --- fin borrado seguro ---

            self._load_table()
            messagebox.showinfo("Guardar", "Registro guardado/actualizado.")

            updated = self.repo.get_by_nit(nit)
            if updated:
                self._fill_form(updated)
            for iid in self.tree.get_children():
                vals = self.tree.item(iid, "values")
                if vals and str(vals[0]).strip() == nit:
                    self.tree.selection_set(iid)
                    self.tree.see(iid)
                    break

             # --- limpiar formulario ---
            for k in self.columns:
                if k != "NIT":  # si también quieres limpiar NIT, quita esta condición
                    self.vars[k].set("")
            if hasattr(self, "txt_obs"):
                self.txt_obs.delete("1.0", "end")
            self.vars["NIT"].set("")   # limpiar NIT
            self._update_save_state()

            for item in self.tree.selection():
                self.tree.selection_remove(item)
            self.ent_search.focus_set()

            if "FOTO" in self.vars:
                self.vars["FOTO"].set("")
            if hasattr(self, "btn_ver_foto"):
                self.btn_ver_foto.config(state="disabled")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _eliminar(self):
        nit = self.vars["NIT"].get().strip()
        if not nit:
            messagebox.showinfo("Eliminar", "Selecciona un registro primero.")
            return
        if not self.repo.exists_nit(nit):
            messagebox.showinfo("Eliminar", f"No existe el NIT {nit}.")
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar NIT {nit}?"):
            self.repo.delete(nit)
            self.repo.save()
            self._load_table()
            messagebox.showinfo("Eliminar", "Registro eliminado.")

            for k in self.columns:
                self.vars[k].set("")
            if hasattr(self, "txt_obs"):
                self.txt_obs.delete("1.0", "end")
            self._update_save_state()

            for item in self.tree.selection():
                self.tree.selection_remove(item)
            self.ent_search.focus_set()

            if "FOTO" in self.vars:
                self.vars["FOTO"].set("")
            if hasattr(self, "btn_ver_foto"):
                self.btn_ver_foto.config(state="disabled")

    def _importar(self):
        path = filedialog.askopenfilename(
            title="Selecciona Excel a importar",
            filetypes=[("Excel", "*.xlsx *.xlsm")]  # openpyxl no abre .xls
        )
        if not path:
            return
        try:
            # upsert para no perder tus extras
            self.repo.import_from_excel(path, mode="upsert", keep_repo_path=True)
            self.repo.save()
            self._load_table()
            messagebox.showinfo("Importar", "Datos importados correctamente.")
        except Exception as e:
            messagebox.showerror("Error al importar", str(e))

    # Exportar TODO en un solo botón
    def _exportar_all(self):
        path = filedialog.asksaveasfilename(
            title="Exportar (todas las columnas)...",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")]
        )
        if not path:
            return
        try:
            self.repo.export_to_excel(path, only_visible=False)
            messagebox.showinfo("Exportar", "Archivo exportado correctamente.")
        except Exception as e:
            messagebox.showerror("Error al exportar", str(e))

    def _on_row_double_click(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self._fill_form(dict(zip(self.columns, values)))
    
    

