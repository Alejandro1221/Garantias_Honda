import os, sys
import tkinter as tk
from tkinter import ttk
from escaner import LectorGarantiasApp
from distribuidores_ui import DistribuidoresView
from clasificador_ui import ClasificadorView
from concesionariosUI import ConcesionariosView
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "GSM")))
from gsm_ui import LectorGSMApp

SIDEBAR_W = 220
SIDEBAR_W_COLLAPSED = 56

class NavController:
    def __init__(self, container: tk.Frame):
        self.container = container
        self.frames = {}

    def register(self, key: str, view_cls, **kwargs):
        if key in self.frames:
            return self.frames[key]
        frame = view_cls(self.container, controller=self, **kwargs)
        frame.grid(row=0, column=0, sticky="nsew")
        self.frames[key] = frame
        return frame

    def show(self, key: str):
        frame = self.frames[key]
        frame.tkraise()
        if hasattr(frame, "title"):
            frame.master.master.master.lbl_title.config(text=frame.title)  
        if hasattr(frame, "on_show"):
            frame.on_show()

class MainMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Garantías")
        self.geometry("1200x800")
        try:
            self.state('zoomed')
        except Exception:
            try:
                self.attributes('-zoomed', True)
            except Exception:
                pass
        self._sidebar_expanded = True
        self._build_ui()


    def _build_ui(self):
        # Topbar
        top = ttk.Frame(self, padding=(8,8)); top.pack(side="top", fill="x")
        ttk.Button(top, text="☰", width=3, command=self.toggle_sidebar).pack(side="left")
        self.lbl_title = ttk.Label(top, text="Dashboard", font=("Segoe UI", 14, "bold"))
        self.lbl_title.pack(side="left", padx=8)

        # Body
        body = ttk.Frame(self); body.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = ttk.Frame(body, style="Sidebar.TFrame")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.configure(width=SIDEBAR_W)
        self.sidebar.pack_propagate(False)

        ttk.Label(self.sidebar, text="Menú", style="SidebarTitle.TLabel").pack(anchor="w", padx=12, pady=(12,6))

        def nav_btn(texto, key):
            b = ttk.Button(self.sidebar, text=texto, command=lambda: self._navigate(key))
            b.full_text = texto
            b.short_text = texto.split()[0] if " " in texto else texto
            b.pack(fill="x", padx=10, pady=4)
            return b

        nav_btn("🏠 Dashboard", "dashboard")
        nav_btn("🗂 Clasificador", "clasificador") 
        nav_btn("🧾 Escáner", "scanner")
        nav_btn(" GSM", "gsm")
        nav_btn("🔍 Distribuidores", "distribuidores")
        nav_btn("🏢 Concesionarios", "concesionarios")
        nav_btn("📊 Prueba3", "reportes")

        ttk.Separator(self.sidebar, orient="horizontal").pack(fill="x", padx=10, pady=8)

        # Contenedor principal
        self.container = ttk.Frame(body)
        self.container.pack(side="left", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # Estilos
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except: pass
        style.configure("Sidebar.TFrame", background="#FFFFFF")
        style.configure("SidebarTitle.TLabel", background="#FFFFFF", font=("Segoe UI", 11, "bold"))

        # Router
        self.router = NavController(self.container)

        # Registrar vistas
        self.router.register("dashboard", DashboardView)
        self.router.register("clasificador", ClasificadorView)
        self.router.register("scanner", ScannerView)   
        self.router.register("gsm", GSMView)
        self.router.register("distribuidores", DistribuidoresView)
        self.router.register("reportes", ReportesView)
        self.router.register("concesionarios", ConcesionariosView)

        # Mostrar por defecto
        self.router.show("scanner")

    def toggle_sidebar(self):
        self._sidebar_expanded = not self._sidebar_expanded
        w = SIDEBAR_W if self._sidebar_expanded else SIDEBAR_W_COLLAPSED
        self.sidebar.configure(width=w)
        for child in self.sidebar.winfo_children():
            if isinstance(child, ttk.Button):
                try:
                    child.config(text=child.full_text if self._sidebar_expanded else child.short_text)
                except: pass
        self.sidebar.update_idletasks()

    def _navigate(self, key: str):
        self.router.show(key)

# ---------------- Vistas simples ----------------
class DashboardView(ttk.Frame):
    title = "Dashboard"
    def __init__(self, parent, controller=None):
        super().__init__(parent, padding=16)
        ttk.Label(self, text="Bienvenido al Dashboard").pack()

class ScannerView(ttk.Frame):
    title = "Escáner"
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        # Aquí se monta tu app OCR dentro del frame
        self.app = LectorGarantiasApp(root=None, host=self)  

class VinMotorView(ttk.Frame):
    title = "VIN/Motor"
    def __init__(self, parent, controller=None):
        super().__init__(parent, padding=16)
        ttk.Label(self, text="Módulo VIN/Motor").pack()

class ReportesView(ttk.Frame):
    title = "Reportes"
    def __init__(self, parent, controller=None):
        super().__init__(parent, padding=16)
        ttk.Label(self, text="Módulo de reportes").pack()

class GSMView(ttk.Frame):
    title = "GSM"
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.app = LectorGSMApp(root=None, host=self)

if __name__ == "__main__":
    MainMenu().mainloop()
