import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os
from concesionarios import cargar_excel, cargar_guardada, transformar_tabla,guardar_en_tablas, path_guardado


class ConcesionariosView(ttk.Frame):
    title = "Concesionarios"
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller
        self._df = None
        self.build_ui()
        self.auto_cargar_guardada()

    def auto_cargar_guardada(self):
        df = cargar_guardada()
        if df is None:
            return
        if df.empty:
            self._pintar(df)
            self.lbl.config(text=os.path.basename(path_guardado()))
            messagebox.showinfo("Sin datos", "La tabla guardada no tiene filas válidas.")
            return
        self._pintar(df)
        self.lbl.config(text=os.path.basename(path_guardado()))


    def build_ui(self):
        top = ttk.Frame(self, padding=(8,8))
        top.pack(side="top", fill="x")
        ttk.Button(top, text="Cargar Excel", command=self._cargar).pack(side="left")
        self.lbl = ttk.Label(top, text="Sin archivo")
        self.lbl.pack(side="left", padx=12)

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, show="headings")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

    def _cargar(self):
        path = filedialog.askopenfilename(title="Seleccionar Excel", filetypes=[("Excel", "*.xlsx *.xls")])
        if not path:
            return
        if os.path.exists(path_guardado()):
            ok = messagebox.askyesno("Confirmar", "Ya existe una tabla guardada. ¿Deseas reemplazarla?")
            if not ok:
                return
        try:
            cargar_excel(path)
            df = transformar_tabla()
            if df is None or df.empty:
                messagebox.showinfo("Sin datos", "La tabla no tiene filas válidas tras el filtrado.")
                return
            saved = guardar_en_tablas()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo procesar el archivo:\n{e}")
            return
        self._pintar(df)
        self.lbl.config(text=os.path.basename(saved) if saved else "tabla_concesionarios")

    def _pintar(self, df: pd.DataFrame):
        for i in self.tree.get_children():
            self.tree.delete(i)
        cols = list(map(str, df.columns))
        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=140, stretch=True, anchor="w")
        for row in df.astype(object).where(pd.notna(df), "").astype(str).itertuples(index=False, name=None):
            self.tree.insert("", "end", values=row)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Concesionarios")
    try:
        root.state("zoomed")
    except:
        try:
            root.attributes("-zoomed", True)
        except:
            root.geometry("1100x700")
    app = ConcesionariosView(root)
    app.pack(fill="both", expand=True)
    root.mainloop()
