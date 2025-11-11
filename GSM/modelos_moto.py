from pathlib import Path
from typing import Dict
import pandas as pd
import re, unicodedata, difflib

# Este archivo vive en GSM/, el Excel vive en ../Tablas/Modelo_Motos.xlsx
EXCEL_PATH = Path(__file__).resolve().parent.parent / "Tablas" / "Modelo_Motos.xlsx"

if not EXCEL_PATH.exists():
    raise FileNotFoundError(f"No encontré el Excel en: {EXCEL_PATH}")

df = pd.read_excel(EXCEL_PATH, dtype=str, engine="openpyxl").fillna("")
MODELOS = [str(x).strip() for x in df.iloc[:, 0].tolist() if str(x).strip()]

def _normalize(s: str) -> str:

    if not s:
        return ""
    s = str(s).upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))

    s = s.replace("O", "0")  # O->0
    s = s.replace("I", "1")  # I->1

    s = re.sub(r"[^A-Z0-9\.]", "", s)
    return s

# Carga catálogo y construye índice normalizado -> original
_df = pd.read_excel(EXCEL_PATH, dtype=str, engine="openpyxl").fillna("")
if "MODELOS" not in _df.columns:
    raise RuntimeError("El archivo Modelo_Motos.xlsx debe tener una columna 'MODELOS'.")

_MODELOS_RAW = [m.strip() for m in _df["MODELOS"].astype(str).tolist() if m.strip()]
_INDEX: Dict[str, str] = { _normalize(m): m for m in _MODELOS_RAW }

_KEYS = list(_INDEX.keys())

def mapear_linea_a_modelo_catalogo(linea_detectada: str) -> str:
    """
    Recibe la 'Línea' detectada en la Orden (p.ej. 'CB125F 2.0')
    y devuelve el nombre EXACTO del catálogo (p.ej. 'CB125F2.0'),
    o '' si no encuentra match razonable.
    """
    key = _normalize(linea_detectada)
    if not key:
        return ""

    # 1) Match exacto por clave normalizada
    if key in _INDEX:
        return _INDEX[key]

    # 2) Fuzzy contra claves normalizadas
    cand = difflib.get_close_matches(key, _KEYS, n=1, cutoff=0.84)
    if cand:
        return _INDEX[cand[0]]

    return ""

def _norm_text(s: str) -> str:
    if not s: return ""
    s = str(s).upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("O","0").replace("I","1")
    return re.sub(r"[^A-Z0-9\.]", "", s)

# ya tienes: _INDEX (normalizado -> original) y _KEYS = list(_INDEX.keys())

def detectar_modelo_en_texto(texto: str) -> str:
    """
    Busca cualquier modelo del catálogo dentro de TODO el texto OCR.
    Devuelve exactamente como está en el Excel, o '' si no encuentra.
    """
    t = _norm_text(texto)
    if not t:
        return ""

    # 1) match directo: prioriza claves más largas para evitar falsos positivos
    for key in sorted(_KEYS, key=len, reverse=True):
        if key and key in t:
            return _INDEX[key]

    # 2) (opcional) fuzzy con todo el texto “compactado”
    cand = difflib.get_close_matches(t, _KEYS, n=1, cutoff=0.92)
    if cand:
        return _INDEX[cand[0]]

    return ""