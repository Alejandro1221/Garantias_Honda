# tabla_registros.py
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
from datetime import datetime
import os

def abrir_tabla_registros(parent: tk.Tk, headers: list[str], registros: list[list[str]]):
    
    top = tk.Toplevel(parent)
    top.title("Registros guardados")
    top.geometry("1000x500")

    # --- Tabla ---
    frame = tk.Frame(top); frame.pack(fill="both", expand=True)
    cols = list(range(len(headers)))
    tv = ttk.Treeview(frame, columns=cols, show="headings", height=15)

    for i, h in enumerate(headers):
        tv.heading(i, text=h)
        tv.column(i, width=150, anchor="w")

    sy = tk.Scrollbar(frame, orient="vertical", command=tv.yview)
    sx = tk.Scrollbar(frame, orient="horizontal", command=tv.xview)
    tv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

    tv.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    def recargar_tabla():
        tv.delete(*tv.get_children())
        for fila in registros:
            row = fila + [""] * (len(headers) - len(fila))
            tv.insert("", "end", values=row[:len(headers)])

    recargar_tabla()

    # --- Botonera ---
    btns = tk.Frame(top); btns.pack(fill="x", pady=8)

    def exportar():
        if not registros:
            messagebox.showwarning("Exportar", "No hay registros guardados.")
            return

        ruta = filedialog.asksaveasfilename(
            title="Exportar",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
            initialfile=f"garantias_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        )
        if not ruta:
            return
        try:
            ext = os.path.splitext(ruta)[1].lower()
            if ext == ".xlsx":
                try:
                    import pandas as pd
                    df = pd.DataFrame(registros, columns=headers[:len(registros[0])])
                    if len(df.columns) < len(headers):
                        for _ in range(len(headers) - len(df.columns)):
                            df[headers[len(df.columns)]] = ""
                    df = df[headers]
                    df.to_excel(ruta, index=False)
                except Exception:
                    # fallback a CSV si falla pandas
                    ruta = os.path.splitext(ruta)[0] + ".csv"
                    _exportar_csv(ruta, headers, registros)
            else:
                _exportar_csv(ruta, headers, registros)

            messagebox.showinfo("Exportar", f"Archivo exportado:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Exportar", f"Error exportando:\n{e}")

    tk.Button(btns, text="Exportar", command=exportar, bg="lightgreen").pack(side="left", padx=6)
    tk.Button(btns, text="Recargar", command=recargar_tabla, bg="lightblue").pack(side="left", padx=6)
    tk.Button(btns, text="Cerrar", command=top.destroy, bg="lightgray").pack(side="right", padx=6)


def _exportar_csv(ruta: str, headers: list[str], registros: list[list[str]]):
    import csv
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for fila in registros:
            row = fila + [""] * (len(headers) - len(fila))
            w.writerow(row[:len(headers)])
