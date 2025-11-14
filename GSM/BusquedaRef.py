import os, re, difflib, unicodedata
import pandas as pd
from typing import Dict, List, Optional
from pathlib import Path

# Carpeta raíz del proyecto (PruebaLectura)
BASE_DIR = Path(__file__).resolve().parents[1]

# Tablas/Referencias.xlsx está en la raíz, no dentro de GSM
EXCEL_PATH = BASE_DIR / "Tablas" / "Referencias.xlsx"

df_excel = pd.read_excel(
    EXCEL_PATH,
    dtype=str,
    engine="openpyxl"
).fillna("")

df_excel["Referencia"] = (
    df_excel["Referencia"]
    .astype(str)
    .str.upper()
    .str.replace(" ", "", regex=False)
)

DESC_POR_REF: Dict[str, str] = dict(zip(df_excel["Referencia"], df_excel["Desc. item"]))

REFS_POR_PREFIJO: Dict[str, List[str]] = {}
for ref in DESC_POR_REF.keys():
    pref = ref.split("-", 1)[0]
    if pref:
        REFS_POR_PREFIJO.setdefault(pref, []).append(ref)

def unir_lineas_cortadas(texto: str) -> str:
    lineas = str(texto).splitlines()
    out = []
    i = 0
    while i < len(lineas):
        l = lineas[i].strip()
        if l.endswith("-") and i + 1 < len(lineas):
            nxt = lineas[i+1].strip()
            if re.match(r"^[A-Z0-9]", nxt, flags=re.I):
                l = l + nxt
                i += 1
        out.append(l)
        i += 1
    return "\n".join(out)

def norm_ocr_para_refs(s: str) -> str:
    if not s:
        return ""
    s = str(s).upper()
    s = unicodedata.normalize("NFKD", s)
    for ch in "‐-‒–—−﹣－_":
        s = s.replace(ch, "-")
    s = s.replace("O", "0").replace("I", "1").replace("B", "8")
    s = re.sub(r"[^A-Z0-9\-]", "", s)
    return s

def _variantes_O0(ref: str) -> List[str]:
    if not ref:
        return []
    return list({ref, ref.replace("O", "0"), ref.replace("0", "O")})

REF_PATTERN = re.compile(r"\b[A-Z0-9]{3,6}-[A-Z0-9]{2,4}-[A-Z0-9]{2,4}\b")

def _mejor_por_prefijo(candidato: str) -> Optional[str]:
    pref = candidato.split("-", 1)[0]
    cand_list = REFS_POR_PREFIJO.get(pref, [])
    if not cand_list:
        return None
    m = difflib.get_close_matches(candidato, cand_list, n=1, cutoff=0.80)
    return m[0] if m else None

def buscar_referencias_en_texto(texto_ocr: str) -> List[Dict[str, str]]:
    if not texto_ocr:
        return []

    texto_ocr = unir_lineas_cortadas(texto_ocr)

    resultados: List[Dict[str, str]] = []
    seen = set()

    texto_norm = norm_ocr_para_refs(texto_ocr)
    texto_sin  = texto_norm.replace("-", "")

    for ref, desc in DESC_POR_REF.items():
        ok = any(v in texto_norm for v in _variantes_O0(ref))
        if not ok and ref.replace("-", "") in texto_sin:
            ok = True
        if ok and ref not in seen:
            resultados.append({"Referencia": ref, "Descripcion": desc}); seen.add(ref)

    if not resultados:
        for raw in str(texto_ocr).splitlines():
            line = norm_ocr_para_refs(raw)
            if not line:
                continue
            line_sin = line.replace("-", "")
            for ref, desc in DESC_POR_REF.items():
                ok = any(v in line for v in _variantes_O0(ref))
                if not ok and ref.replace("-", "") in line_sin:
                    ok = True
                if ok and ref not in seen:
                    resultados.append({"Referencia": ref, "Descripcion": desc}); seen.add(ref)

    candidatos = set(REF_PATTERN.findall(texto_norm))
    for cand in candidatos:
        if cand in seen:
            continue
        ref_cat = _mejor_por_prefijo(cand)
        if ref_cat and ref_cat not in seen:
            resultados.append({"Referencia": ref_cat, "Descripcion": DESC_POR_REF.get(ref_cat, "")}); seen.add(ref_cat)

    if not resultados and "YUASA" in texto_ocr.upper().replace(" ", ""):
        for ref, desc in DESC_POR_REF.items():
            if ref.startswith("YUASA"):
                if ref[:10] in texto_ocr.upper().replace(" ", ""):
                    if ref not in seen:
                        resultados.append({"Referencia": ref, "Descripcion": desc})
                        seen.add(ref)

    return resultados
