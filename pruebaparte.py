# mini_gui_refs.py
import os, io, re, difflib, unicodedata, hashlib, tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Dict, Tuple, Optional

import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import pandas as pd

# ========= CONFIG =========
# Si Tesseract no está en el PATH, especifica tu ruta aquí:
TESSERACT_PATH = r"C:\Users\practicante1servicio\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
try:
    if os.path.isfile(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
except Exception:
    pass

DPI_ROI   = 650
DPI_FULL  = 650
LANG_OCR  = "eng+spa"
MIN_REFS  = 2
ROI_MODE  = "BOTTOM60"  

# ====== CATALOGO ======
def cargar_catalogo(path_excel: str = "referencias.xlsx") -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    df = pd.read_excel(path_excel, usecols=["Referencia", "Desc. item"],
                       dtype=str, engine="openpyxl").fillna("")
    df["Referencia"] = df["Referencia"].astype(str).str.upper().str.replace(" ", "", regex=False)
    desc_por_ref = dict(zip(df["Referencia"], df["Desc. item"]))
    refs_por_prefijo: Dict[str, List[str]] = {}
    for ref in desc_por_ref:
        pref = ref.split("-")[0]
        if pref:
            refs_por_prefijo.setdefault(pref, []).append(ref)
    return desc_por_ref, refs_por_prefijo

# ====== NORMALIZACIÓN & BÚSQUEDA ======
def _norm_ocr_para_refs(s: str) -> str:
    if not s: return ""
    s = s.upper()
    s = unicodedata.normalize("NFKD", s)
    for ch in "‐-‒–—−﹣－_":
        s = s.replace(ch, "-")  # guiones raros → '-'
    s = s.replace("O", "0").replace("I", "1").replace("B", "8")  # confusiones típicas
    s = re.sub(r"[^A-Z0-9\-]", "", s)  # solo A-Z, 0-9 y '-'
    return s

def _variantes_O0(ref: str) -> List[str]:
    if not ref: return []
    return list({ref, ref.replace("O", "0"), ref.replace("0", "O")})

REF_PATTERN = re.compile(r"\b[A-Z0-9]{3,6}-[A-Z0-9]{2,4}-[A-Z0-9]{2,4}\b")

def _mejor_por_prefijo(candidato: str, REFS_POR_PREFIJO: Dict[str, List[str]]) -> Optional[str]:
    if not candidato: return None
    pref = candidato.split("-")[0]
    cand_list = REFS_POR_PREFIJO.get(pref, [])
    if not cand_list: return None
    m = difflib.get_close_matches(candidato, cand_list, n=1, cutoff=0.80)
    return m[0] if m else None

def _unir_lineas_cortadas(texto: str) -> str:
    """
    Une líneas cortadas típicas del OCR:
    - si una línea termina en '-' y la siguiente inicia con alfanumérico, se concatena.
    """
    lineas = texto.splitlines()
    out = []
    i = 0
    while i < len(lineas):
        linea = lineas[i].strip()
        if linea.endswith("-") and i + 1 < len(lineas):
            sig = lineas[i+1].strip()
            if re.match(r"^[A-Z0-9]", sig, flags=re.I):
                linea = linea + sig  # fusiona
                i += 1
        out.append(linea)
        i += 1
    return "\n".join(out)

def buscar_referencias_en_texto(texto_ocr: str,
                                DESC_POR_REF: Dict[str, str],
                                REFS_POR_PREFIJO: Dict[str, List[str]]) -> List[Dict[str, str]]:
    if not texto_ocr: return []
    resultados, seen = [], set()

    # PRE: unir renglones partidos
    texto_ocr = _unir_lineas_cortadas(texto_ocr)

    texto_norm = _norm_ocr_para_refs(texto_ocr)
    texto_sin  = texto_norm.replace("-", "")

    # 1) exacto + variantes O↔0 + sin guiones
    for ref, desc in DESC_POR_REF.items():
        if not ref: continue
        ok = any(v in texto_norm for v in _variantes_O0(ref))
        if not ok and ref.replace("-", "") in texto_sin:
            ok = True
        if ok and ref not in seen:
            resultados.append({"Referencia": ref, "Descripcion": desc}); seen.add(ref)

    # 2) si nada, línea por línea
    if not resultados:
        for raw in str(texto_ocr).splitlines():
            line = _norm_ocr_para_refs(raw)
            if not line: continue
            line_sin = line.replace("-", "")
            for ref, desc in DESC_POR_REF.items():
                ok = any(v in line for v in _variantes_O0(ref))
                if not ok and ref.replace("-", "") in line_sin:
                    ok = True
                if ok and ref not in seen:
                    resultados.append({"Referencia": ref, "Descripcion": desc}); seen.add(ref)

    # 3) regex + fuzzy por prefijo
    candidatos = set(REF_PATTERN.findall(texto_norm))
    for cand in candidatos:
        if cand in seen: continue
        ref_cat = _mejor_por_prefijo(cand, REFS_POR_PREFIJO)
        if ref_cat and ref_cat not in seen:
            resultados.append({"Referencia": ref_cat, "Descripcion": DESC_POR_REF.get(ref_cat, "")}); seen.add(ref_cat)

    return resultados

# ====== OCR CACHE & RENDER ======
_OCR_CACHE: Dict[Tuple, str] = {}

def _ocr_pdf_roi(ruta_pdf: str, pagina_index: int, dpi: int = DPI_ROI, lang: str = LANG_OCR, roi: str = ROI_MODE) -> str:
    key = (ruta_pdf, pagina_index, dpi, lang, f"ROI:{roi}")
    if key in _OCR_CACHE: return _OCR_CACHE[key]
    with fitz.open(ruta_pdf) as doc:
        if not (0 <= pagina_index < len(doc)): _OCR_CACHE[key] = ""; return ""
        page = doc[pagina_index]
        rect = page.rect
        clip = fitz.Rect(rect.x0, rect.y0 + rect.height * 0.4, rect.x1, rect.y1) if roi=="BOTTOM60" else rect
        mat  = fitz.Matrix(dpi/72.0, dpi/72.0)
        pix  = page.get_pixmap(matrix=mat, clip=clip)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    texto = pytesseract.image_to_string(img, lang=lang, config="--oem 3 --psm 6")
    _OCR_CACHE[key] = texto
    return texto

def _ocr_pdf_full(ruta_pdf: str, pagina_index: int, dpi: int = DPI_FULL, lang: str = LANG_OCR) -> str:
    key = (ruta_pdf, pagina_index, dpi, lang, "FULL")
    if key in _OCR_CACHE: return _OCR_CACHE[key]
    with fitz.open(ruta_pdf) as doc:
        if not (0 <= pagina_index < len(doc)): _OCR_CACHE[key] = ""; return ""
        page = doc[pagina_index]
        mat  = fitz.Matrix(dpi/72.0, dpi/72.0)
        pix  = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    texto = pytesseract.image_to_string(img, lang=lang, config="--oem 3 --psm 6")
    _OCR_CACHE[key] = texto
    return texto

# ====== OpenAI Vision (opcional) ======
def _vision_refs_opcional(pil_img: Image.Image) -> List[Dict[str, str]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or pil_img is None: return []
    try:
        import base64, json
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        buf = io.BytesIO(); pil_img.save(buf, format="PNG")
        data_url = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
        schema = {
            "name": "refs_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"Referencia":{"type":"string"}, "Descripcion":{"type":"string"}},
                            "required": ["Referencia"]
                        }
                    }
                }, "required": ["items"], "additionalProperties": False
            }
        }
        prompt = ("Extrae TODAS las referencias de repuestos visibles (p.ej. 01210-K1L-D00, 15312-K70-600). "
                  "Devuelve JSON con 'items', cada item con 'Referencia' y 'Descripcion' si aparece en la misma línea.")
        resp = client.chat.completions.create(
            model="gpt-4o-mini", temperature=0,
            response_format={"type":"json_schema","json_schema":schema},
            messages=[{"role":"user","content":[
                {"type":"text","text":prompt},
                {"type":"image_url","image_url":{"url":data_url}}
            ]}]
        )
        msg = resp.choices[0].message
        obj = getattr(msg, "parsed", None) or __import__("json").loads(msg.content)
        out = []
        for it in obj.get("items", []) or []:
            ref = (it.get("Referencia") or "").upper().strip()
            ref = re.sub(r"[‐‒–—−﹣－_]", "-", ref)
            desc = (it.get("Descripcion") or "").strip()
            if ref: out.append({"Referencia": ref, "Descripcion": desc})
        return out
    except Exception as e:
        print("[Visión] Error:", e)
        return []

# ====== DETECCIÓN POR PÁGINA ======
def detectar_refs_en_pagina(pdf_path: str, page_index: int,
                            DESC_POR_REF: Dict[str, str], REFS_POR_PREFIJO: Dict[str, List[str]],
                            usar_vision: bool = False) -> List[Dict[str, str]]:
    resultados: List[Dict[str, str]] = []

    def _merge(nuevos: List[Dict[str, str]]):
        ya = {r["Referencia"] for r in resultados if r.get("Referencia")}
        for r in (nuevos or []):
            ref = r.get("Referencia")
            if ref and ref not in ya:
                resultados.append(r); ya.add(ref)

    # 1) ROI rápido
    texto_roi = _ocr_pdf_roi(pdf_path, page_index, dpi=DPI_ROI, lang=LANG_OCR, roi=ROI_MODE)
    _merge(buscar_referencias_en_texto(texto_roi, DESC_POR_REF, REFS_POR_PREFIJO))

    # 2) FULL si faltan
    if len(resultados) < MIN_REFS:
        texto_full = _ocr_pdf_full(pdf_path, page_index, dpi=DPI_FULL, lang=LANG_OCR)
        _merge(buscar_referencias_en_texto(texto_full, DESC_POR_REF, REFS_POR_PREFIJO))

    # 3) Visión (opcional)
    if usar_vision and len(resultados) < MIN_REFS:
        with fitz.open(pdf_path) as doc:
            page = doc[page_index]
            mat  = fitz.Matrix(DPI_FULL/72.0, DPI_FULL/72.0)
            pix  = page.get_pixmap(matrix=mat)
        pil_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        _merge(_vision_refs_opcional(pil_img))

    return resultados

# ====== GUI ======
class MiniGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Detector de Referencias (OCR + Visión opcional)")
        self.root.geometry("950x600")
        self.pdf_path = ""
        self.usar_vision = tk.BooleanVar(value=False)
        self.desc_por_ref, self.refs_por_prefijo = {}, {}
        self.rows_csv: List[Dict[str,str]] = []

        top = tk.Frame(root); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="Cargar PDF", command=self.cargar_pdf, width=14, bg="#cfe8ff").pack(side="left")
        tk.Checkbutton(top, text="Usar OpenAI si faltan", variable=self.usar_vision).pack(side="left", padx=12)
        tk.Button(top, text="Procesar", command=self.procesar, width=12, bg="#d5ffd5").pack(side="left")
        tk.Button(top, text="Exportar CSV", command=self.exportar_csv, width=12, bg="#ffe2b5").pack(side="left", padx=8)

        self.lbl_pdf = tk.Label(root, text="PDF: (ninguno)", anchor="w"); self.lbl_pdf.pack(fill="x", padx=10)

        mid = tk.Frame(root); mid.pack(fill="both", expand=True, padx=10, pady=8)
        left = tk.Frame(mid); left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="Log / Estado:", anchor="w").pack(fill="x")
        self.txt_log = tk.Text(left, height=10)
        self.txt_log.pack(fill="both", expand=True)

        right = tk.Frame(mid); right.pack(side="left", fill="both", expand=True, padx=(10,0))
        tk.Label(right, text="Referencias detectadas por página:", anchor="w").pack(fill="x")
        self.txt_out = tk.Text(right, height=10)
        self.txt_out.pack(fill="both", expand=True)

        # Carga catálogo
        try:
            self.desc_por_ref, self.refs_por_prefijo = cargar_catalogo("referencias.xlsx")
            self.log("Catálogo cargado: OK")
        except Exception as e:
            self.log(f"ERROR cargando referencias.xlsx: {e}")
            messagebox.showerror("Error", "No se pudo cargar referencias.xlsx")

        # Check Tesseract
        self._check_tesseract()

    def _check_tesseract(self):
        try:
            v = pytesseract.get_tesseract_version()
            self.log(f"Tesseract OK: {v}")
        except Exception:
            self.log("Tesseract NO encontrado. Configura TESSERACT_PATH al inicio del script.")
            messagebox.showwarning("Tesseract", "Tesseract no encontrado.\nConfigura TESSERACT_PATH al inicio del script.")

    def log(self, msg: str):
        self.txt_log.insert("end", msg + "\n"); self.txt_log.see("end"); self.root.update_idletasks()

    def _out(self, s: str):
        self.txt_out.insert("end", s + "\n"); self.txt_out.see("end"); self.root.update_idletasks()

    def cargar_pdf(self):
        path = filedialog.askopenfilename(title="Selecciona un PDF", filetypes=[("PDF","*.pdf")])
        if path:
            self.pdf_path = path
            self.lbl_pdf.config(text=f"PDF: {self.pdf_path}")
            self.txt_out.delete("1.0", "end")
            self.rows_csv.clear()
            self.log("PDF listo.")

    def procesar(self):
        if not self.pdf_path:
            messagebox.showinfo("Info", "Primero elige un PDF.")
            return
        self.txt_out.delete("1.0", "end")
        self.rows_csv.clear()
        try:
            with fitz.open(self.pdf_path) as doc:
                total = len(doc)
            self.log(f"Procesando {total} página(s)...")
            for i in range(total):
                refs = detectar_refs_en_pagina(self.pdf_path, i, self.desc_por_ref, self.refs_por_prefijo, usar_vision=self.usar_vision.get())
                # hashes cache
                h_roi_key  = (self.pdf_path, i, DPI_ROI,  LANG_OCR, f"ROI:{ROI_MODE}")
                h_full_key = (self.pdf_path, i, DPI_FULL, LANG_OCR, "FULL")
                h_roi  = hashlib.md5(_OCR_CACHE.get(h_roi_key,  "").encode("utf-8","ignore")).hexdigest()[:8] if h_roi_key  in _OCR_CACHE else "--"
                h_full = hashlib.md5(_OCR_CACHE.get(h_full_key, "").encode("utf-8","ignore")).hexdigest()[:8] if h_full_key in _OCR_CACHE else "--"

                self._out(f"[Página {i+1}] Refs: {len(refs)} | hashROI:{h_roi} hashFULL:{h_full}")
                for r in refs:
                    self._out(f"   - {r['Referencia']} => {r.get('Descripcion','')}")
                    self.rows_csv.append({"pdf": os.path.basename(self.pdf_path), "pagina": str(i+1),
                                          "referencia": r["Referencia"], "descripcion": r.get("Descripcion","")})
                self._out("-"*60)
            self.log("Terminado.")
        except Exception as e:
            self.log(f"ERROR: {e}")
            messagebox.showerror("Error", str(e))

    def exportar_csv(self):
        if not self.rows_csv:
            messagebox.showinfo("Info", "No hay datos para exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")],
                                            initialfile="refs_detectadas.csv", title="Guardar CSV")
        if not path: return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["pdf","pagina","referencia","descripcion"])
                w.writeheader(); w.writerows(self.rows_csv)
            self.log(f"CSV guardado: {path}")
            messagebox.showinfo("Exportado", f"CSV guardado en:\n{path}")
        except Exception as e:
            self.log(f"ERROR exportando CSV: {e}")
            messagebox.showerror("Error", str(e))

def main():
    root = tk.Tk()
    app = MiniGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
