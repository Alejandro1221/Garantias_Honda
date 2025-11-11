import os, sys, subprocess, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from clasificador import ClasificadorService
import threading

class ClasificadorView(ttk.Frame):
    title = "Clasificador (Facturas / Órdenes)"

    def __init__(self, parent=None, controller=None,
                 base_out="Garantias",
                 tesseract_cmd=r"C:\Users\practicante1servicio\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"):
        super().__init__(parent, padding=14)
        self.controller = controller
        self._files = []
        self.service = ClasificadorService(base_out=base_out, tesseract_cmd=tesseract_cmd)
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill="x")
        ttk.Button(top, text="Subir PDFs…", command=self._pick_pdfs).pack(side="left")
        ttk.Button(top, text="Quitar seleccionados", command=self._remove_selected).pack(side="left", padx=(8,0))
        ttk.Button(top, text="Limpiar lista", command=self._clear).pack(side="left", padx=(8,0))
        ttk.Button(top, text="Analizar (OCR) – contar", command=self._analyze).pack(side="left", padx=(8,0))
        ttk.Button(top, text="Ver texto (seleccionado)", command=self._ver_texto_pdf).pack(side="left", padx=(8,0))
        ttk.Button(top, text="Separar y renombrar", command=self._separar_y_renombrar).pack(side="left", padx=(8,0))

        self.modo_var = tk.StringVar(value="separados")
        ttk.Label(top, text="Modo:").pack(side="left", padx=(12,4))
        ttk.Combobox(top, textvariable=self.modo_var, width=18, state="readonly",
                    values=("separados", "unido (por páginas)")).pack(side="left")

        self.lbl_info = ttk.Label(top, text="0 archivo(s)")
        self.lbl_info.pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=8)

        # --- contenedor de la tabla + scrollbars (usa GRID, no place) ---
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True)

        # columnas del Treeview
        cols = ("archivo", "carpeta", "tamano")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=14)

        self.tree.heading("archivo", text="Archivo")
        self.tree.heading("carpeta", text="Carpeta")
        self.tree.heading("tamano",  text="Tamaño")

        self.tree.column("archivo", width=360, anchor="w", stretch=True)
        self.tree.column("carpeta", width=420, anchor="w", stretch=True)
        self.tree.column("tamano",  width=100, anchor="e",  stretch=False)

        # scrollbars
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        # grid layout para que no se “salga”
        table_frame.grid_columnconfigure(0, weight=1)  # Treeview se estira a lo ancho
        table_frame.grid_rowconfigure(0, weight=1)     # Treeview se estira a lo alto

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        # doble clic para abrir PDF
        self.tree.bind("<Double-1>", self._open_pdf)

        # Consola simple de logs
        ttk.Label(self, text="Salida:").pack(anchor="w", pady=(8,0))
        self.txt_out = tk.Text(self, height=10)
        self.txt_out.pack(fill="both", expand=False)

    # ---------- UI helpers ----------
    def _append_log(self, line: str):
        self.txt_out.insert("end", line + "\n")
        self.txt_out.see("end")

    def _refresh_info(self):
        self.lbl_info.config(text=f"{len(self._files)} archivo(s)")

    def _pick_pdfs(self):
        paths = filedialog.askopenfilenames(title="Selecciona PDFs", filetypes=[("PDF", "*.pdf")])
        if not paths: return
        nuevos = [p for p in paths if p not in self._files]
        self._files.extend(nuevos)
        for p in nuevos:
            nombre = os.path.basename(p)
            carpeta = os.path.dirname(p)
            try:
                size = os.path.getsize(p)
                tam = self.service.human_size(size)
            except Exception:
                tam = "—"
            self.tree.insert("", "end", values=(nombre, carpeta, tam))
        self._refresh_info()

    def _open_pdf(self, _evt):
        sel = self.tree.selection()
        if not sel: return
        nombre, carpeta, _ = self.tree.item(sel[0], "values")
        ruta = os.path.join(carpeta, nombre)
        if not os.path.exists(ruta):
            messagebox.showerror("Abrir", "No se encontró el archivo.")
            return
        try:
            if os.name == "nt": os.startfile(ruta)
            elif sys.platform == "darwin": subprocess.Popen(["open", ruta])
            else: subprocess.Popen(["xdg-open", ruta])
        except Exception: pass

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Selecciona una o más filas para quitar.")
            return
        for iid in sel:
            vals = self.tree.item(iid, "values")
            nombre, carpeta = vals[0], vals[1]
            full = os.path.join(carpeta, nombre)
            if full in self._files:
                self._files.remove(full)
            self.tree.delete(iid)
        self._refresh_info()

    def _clear(self):
        self.tree.delete(*self.tree.get_children())
        self._files = []
        self._refresh_info()

    # ---------- Botones que usan el servicio ----------
    def _ver_texto_pdf(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Texto", "Selecciona un PDF en la tabla.")
            return
        nombre, carpeta, _ = self.tree.item(sel[0], "values")
        ruta = os.path.join(carpeta, nombre)
        if not os.path.exists(ruta):
            messagebox.showerror("Texto", "No se encontró el archivo.")
            return
        try:
            texto = self.service.leer_texto_pdf(ruta, modo=self.modo_var.get().lower())
        except Exception as e:
            messagebox.showerror("Texto", f"Error extrayendo texto:\n{e}")
            return

        top = tk.Toplevel(self); top.title(f"Texto: {nombre}"); top.geometry("900x600")
        bar = ttk.Frame(top); bar.pack(fill="x", pady=6, padx=8)
        txt = tk.Text(top, wrap="word"); txt.pack(fill="both", expand=True, padx=8, pady=(0,8))
        ybar = ttk.Scrollbar(txt.master, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ybar.set); ybar.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
        txt.insert("1.0", texto or "(sin texto)"); txt.focus_set()

        def _copiar():
            top.clipboard_clear(); top.clipboard_append(txt.get("1.0","end-1c")); top.update()
            messagebox.showinfo("Copiar", "Texto copiado al portapapeles.")
        def _guardar():
            default = os.path.splitext(nombre)[0] + ".txt"
            path = filedialog.asksaveasfilename(title="Guardar texto como…", defaultextension=".txt",
                                                filetypes=[("Texto", "*.txt")], initialfile=default)
            if not path: return
            try:
                with open(path, "w", encoding="utf-8") as f: f.write(txt.get("1.0","end-1c"))
                messagebox.showinfo("Guardar", f"Guardado:\n{path}")
            except Exception as e:
                messagebox.showerror("Guardar", f"No se pudo guardar:\n{e}")

        ttk.Button(bar, text="Copiar", command=_copiar).pack(side="left")
        ttk.Button(bar, text="Guardar .txt", command=_guardar).pack(side="left", padx=(6,0))

    def _analyze(self):
        if not self._files:
            messagebox.showinfo("Análisis", "No hay PDFs.")
            return

        modo = self.modo_var.get().lower()

        def factory():
            return self.service.analizar_contar_stream(self._files, modo)

        def on_summary(c_fact, c_orden, c_rev, c_err):
            pass  

        self._run_stream_with_modal(
            title="Analizando…",
            message="Ejecutando OCR y clasificación.",
            stream_gen_factory=factory,
            on_summary=on_summary
        )

    def _separar_y_renombrar(self):
        if not self._files:
            messagebox.showinfo("Separar y renombrar", "Primero carga uno o más PDFs.")
            return

        modo = self.modo_var.get().lower()

        def factory():
            return self.service.separar_y_renombrar_stream(self._files, modo)

        def on_summary(c_fact, c_orden, c_rev, c_err):
        
            pass

        self._run_stream_with_modal(
            title="Separando y renombrando…",
            message="Procesando documentos y exportando PDFs.",
            stream_gen_factory=factory,
            on_summary=on_summary
        )

    def _run_with_modal(self, title, message, target, on_done):
        modal = ProgressModal(self, title=title, message=message)

        def worker():
            try:
                result = target()
            except Exception as e:
                result = e
            self.after(0, lambda: self._finish_modal(modal, result, on_done))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_modal(self, modal, result, on_done):
        modal.close()
        if isinstance(result, Exception):
            messagebox.showerror("Error", str(result))
            return
        on_done(result)

    def _run_stream_with_modal(self, title, message, stream_gen_factory, on_summary):
        modal = ProgressModal(self, title=title, message=message, determinate=True)
        self.txt_out.delete("1.0", "end")

        def worker():
            try:
                for update in stream_gen_factory():
                    if isinstance(update, dict):
                        prog = update.get("progress", 0.0)
                        msg = update.get("msg", "")
                        # actualizar UI desde hilo principal
                        self.after(0, lambda p=prog, m=msg: (
                            modal.update_progress(p, m),
                            self._append_log(m) if m else None
                        ))
                    elif isinstance(update, tuple) and update and update[0] == "__SUMMARY__":
                        _, c_fact, c_orden, c_rev, c_err = update
                        def finish():
                            self._append_log("\n===== RESUMEN =====")
                            es_separados = self.modo_var.get().lower().startswith("separados")
                            label_pag = "" if es_separados else " (páginas)"
                            self._append_log(f"Facturas detectadas{label_pag}:        {c_fact}")
                            self._append_log(f"Ordenes de servicio detect.{label_pag}: {c_orden}")
                            self._append_log(f"Revision (no reconocido){label_pag}:   {c_rev}")
                            self._append_log(f"Errores (archivos):                   {c_err}\n")
                            on_summary(c_fact, c_orden, c_rev, c_err)
                            modal.close()
                        self.after(0, finish)
            except Exception as e:
                self.after(0, lambda: (modal.close(), messagebox.showerror("Error", str(e))))

        threading.Thread(target=worker, daemon=True).start()


class ProgressModal(tk.Toplevel):
    def __init__(self, parent, title="Procesando…", message="Por favor espera…", determinate=False):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        frm = ttk.Frame(self, padding=16); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=message, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0,10))

        mode = "determinate" if determinate else "indeterminate"
        self.pb = ttk.Progressbar(frm, mode=mode, length=300, maximum=100)
        self.pb.pack(fill="x")
        self.lbl = ttk.Label(frm, text="0%") if determinate else None
        if self.lbl: self.lbl.pack(anchor="e", pady=(6,0))

        if not determinate:
            self.pb.start(12)

        # centrar
        parent.update_idletasks(); self.update_idletasks()
        w, h = 360, 130 if determinate else 120
        pw = max(parent.winfo_width(), 600); ph = max(parent.winfo_height(), 400)
        x = parent.winfo_rootx() + pw//2 - w//2
        y = parent.winfo_rooty() + ph//2 - h//2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.grab_set()

    def update_progress(self, progress: float, msg: str = ""):
        # progress: 0.0 – 1.0
        val = max(0, min(1, float(progress))) * 100.0
        try:
            self.pb["value"] = val
            if self.lbl:
                self.lbl.config(text=f"{int(val)}%")
        except Exception:
            pass
        self.update_idletasks()

    def close(self):
        try: self.pb.stop()
        except Exception: pass
        self.grab_release()
        self.destroy()

