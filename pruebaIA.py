
import os
import io
import json
import base64
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk
import fitz  # PyMuPDF
from dotenv import load_dotenv
from openai import OpenAI

# ---------- Config ----------
MODEL = "gpt-4o-mini"   
IMG_MAX_SIDE = 1600      
PROMPT_DEFECTO = (
    "Extrae todo el texto legible. "
    "Si es una factura u orden, devuelve también un JSON con campos útiles "
    "(numero_factura, fecha, total_cop, nit, concesionario, referencias). "
    "Primero muestra el texto crudo y luego el JSON."
)

# ---------- Setup OpenAI ----------
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("⚠️ No se encontró OPENAI_API_KEY. Crea un archivo .env con: OPENAI_API_KEY=tu_clave")
client = OpenAI(api_key=api_key) if api_key else None

# ---------- Utilidades ----------
def pil_from_pdf_page(pdf_path: str, page_index: int, dpi: int = 220) -> Image.Image:
    with fitz.open(pdf_path) as doc:
        if not (0 <= page_index < len(doc)):
            raise IndexError("Página fuera de rango.")
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

def load_any_image(path: str, page_index: int = 0) -> Image.Image:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return pil_from_pdf_page(path, page_index, dpi=220)
    return Image.open(path).convert("RGB")

def resize_for_api(img: Image.Image, max_side: int = IMG_MAX_SIDE) -> Image.Image:
    w, h = img.size
    s = min(max_side / max(w, h), 1.0)
    return img if s >= 1.0 else img.resize((int(w*s), int(h*s)), Image.LANCZOS)

def pil_to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

def call_openai_vision(img: Image.Image, prompt: str) -> str:
    if not client:
        return "[ERROR] No hay API key configurada."
    try:
        img_api = resize_for_api(img, IMG_MAX_SIDE)
        data_url = pil_to_data_url(img_api)

        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": "Eres un asistente que lee documentos en español."},
                {"role": "user",
                 "content": [
                     {"type": "text", "text": prompt},
                     {"type": "image_url", "image_url": {"url": data_url}},
                 ]},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERROR OpenAI] {e}"

# ---------- Interfaz ----------
class VisionTester(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Prueba IA (OpenAI Vision)")
        self.geometry("1200x800")

        self.file_path = None
        self.page_index = 0
        self.page_count = 1
        self.current_img = None
        self.preview_tk = None

        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self); top.pack(fill="x", pady=6)
        tk.Button(top, text="Abrir PDF/Imagen", command=self.open_file, bg="#d0ebff").pack(side="left", padx=4)
        self.lbl_file = tk.Label(top, text="(ningún archivo)"); self.lbl_file.pack(side="left", padx=8)

        nav = tk.Frame(self); nav.pack(fill="x")
        tk.Button(nav, text="◀ Página", command=self.prev_page).pack(side="left", padx=2)
        tk.Button(nav, text="Página ▶", command=self.next_page).pack(side="left", padx=2)
        self.lbl_page = tk.Label(nav, text="Página 1/1"); self.lbl_page.pack(side="left", padx=8)

        prm = tk.Frame(self); prm.pack(fill="x", pady=(6, 0))
        tk.Label(prm, text="Prompt:").pack(side="left", padx=(6, 4))
        self.prompt = tk.Entry(prm)
        self.prompt.insert(0, PROMPT_DEFECTO)
        self.prompt.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(prm, text="Leer con OpenAI", command=self.run_openai, bg="#c3f9c6").pack(side="left", padx=6)

        body = tk.PanedWindow(self, orient="horizontal"); body.pack(fill="both", expand=True, pady=6)
        left = tk.Frame(body, bg="#f5f5f5"); body.add(left, stretch="always")
        right = tk.Frame(body); body.add(right, stretch="always")

        self.canvas = tk.Canvas(left, bg="#f5f5f5")
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)

        self.txt = tk.Text(right, wrap="word")
        self.txt.pack(fill="both", expand=True, padx=12, pady=12)

        self.status = tk.Label(self, text="Listo", anchor="w")
        self.status.pack(fill="x")

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Seleccionar PDF o imagen",
            filetypes=[
                ("PDF/Imágenes", "*.pdf;*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.webp"),
                ("PDF", "*.pdf"),
                ("Imágenes", "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.webp"),
            ],
        )
        if not path:
            return
        self.file_path = path
        self.page_index = 0
        self.page_count = self._get_page_count(path)
        self.lbl_file.config(text=os.path.basename(path))
        self._update_page_label()
        self._render_preview()

    def _get_page_count(self, path: str) -> int:
        if path.lower().endswith(".pdf"):
            with fitz.open(path) as doc:
                return len(doc)
        return 1

    def _render_preview(self):
        if not self.file_path:
            return
        try:
            img = load_any_image(self.file_path, self.page_index)
            self.current_img = img
            # preview reducido
            w, h = img.size
            s = min(900 / max(w, h), 1.0)
            prev = img if s >= 1.0 else img.resize((int(w*s), int(h*s)), Image.LANCZOS)
            self.preview_tk = ImageTk.PhotoImage(prev)
            self.canvas.delete("all")
            self.canvas.create_image(10, 10, anchor="nw", image=self.preview_tk)
            self.canvas.config(scrollregion=(0, 0, prev.width, prev.height))
            self.status.config(text=f"Imagen cargada: {w}x{h}px")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def run_openai(self):
        if not self.current_img:
            return messagebox.showinfo("Atención", "Primero abre un PDF o imagen.")
        self.status.config(text="Llamando a OpenAI…"); self.update_idletasks()
        prompt = self.prompt.get().strip() or "Extrae todo el texto legible."
        result = call_openai_vision(self.current_img, prompt)
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", result)
        self.status.config(text="Completado.")

    def prev_page(self):
        if not self.file_path or self.page_count <= 1:
            return
        if self.page_index > 0:
            self.page_index -= 1
            self._update_page_label()
            self._render_preview()

    def next_page(self):
        if not self.file_path or self.page_count <= 1:
            return
        if self.page_index < self.page_count - 1:
            self.page_index += 1
            self._update_page_label()
            self._render_preview()

    def _update_page_label(self):
        self.lbl_page.config(text=f"Página {self.page_index + 1}/{self.page_count}")

if __name__ == "__main__":
    if not api_key:
        print(" Falta OPENAI_API_KEY en .env")
    app = VisionTester()
    app.mainloop()
