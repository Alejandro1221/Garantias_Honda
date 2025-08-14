import re
import pandas as pd

# Cargar una sola vez el Excel Motor.xlsx
df_motor = pd.read_excel(
    "Motor.xlsx",
    dtype=str,
    engine="openpyxl"
).fillna("")

# Limpia espacios y normaliza encabezados
df_motor.columns = df_motor.columns.str.strip()

# Ahora solo nos quedamos con las columnas que necesitamos
df_motor = df_motor[["Ext-Motor", "Modelo", "Casa_Matriz", "Cobro_Matriz", "Responsable"]]

# Normalizar iniciales
df_motor["Ext-Motor"] = (
    df_motor["Ext-Motor"]
    .astype(str)
    .str.upper()
    .str.strip()
    .str.replace(" ", "", regex=False)
)

MODELO_POR_INICIAL = dict(zip(df_motor["Ext-Motor"], df_motor["Modelo"]))
FILA_POR_INICIAL = {row["Ext-Motor"]: row for _, row in df_motor.iterrows()}

_DASH = r"[‑\-–—]"
_DASH_OPT = rf"\s*{_DASH}\s*"

# Patrones válidos de motor (solo estos formatos)
_PATTERNS = [
    rf"\b[A-Z0-9]{{2,6}}{_DASH_OPT}[A-Z0-9]{{5,10}}\b",                 # KD07E-3143016
    rf"\b[A-Z0-9]{{2,6}}{_DASH_OPT}[A-Z0-9]{{1,6}}{_DASH_OPT}[A-Z0-9]{{4,10}}\b",  # JF65E-D-1004998
    r"\b[A-Z0-9]{12,13}\b",                                            # MD42E0N000492, KD07E2484918
]

def _clean_alnum(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s or "")

def _is_motor(raw: str) -> bool:
    s = _clean_alnum(raw)
    # Debe tener 12 o 13 alfanuméricos reales y mezclar letras y dígitos
    return (12 <= len(s) <= 13) and any(c.isalpha() for c in s) and any(c.isdigit() for c in s)

def extraer_motor_cerca_vin(texto: str, vin: str) -> str:
    t = (texto or "").upper()
    if not t:
        return "No detectado"

    # 1) Buscar cerca del VIN 
    if vin:
        lineas = t.splitlines()
        idx = next((i for i, ln in enumerate(lineas) if vin.upper() in ln), None)
        if idx is not None:
            ini, fin = max(0, idx - 3), min(len(lineas), idx + 6)
            bloque = "\n".join(lineas[ini:fin])
            for pat in _PATTERNS:
                for m in re.finditer(pat, bloque):
                    cand = m.group(0).strip()
                    if _is_motor(cand):
                        return cand

    # 2) Fallback global por si el VIN no ayuda
    for pat in _PATTERNS:
        for m in re.finditer(pat, t):
            cand = m.group(0).strip()
            if _is_motor(cand):
                return cand

    return "No detectado"

def _iniciales(motor_detectado: str) -> str:
    """Primer token alfanumérico (tolera guiones raros y espacios)."""
    if not motor_detectado:
        return ""
    return re.split(r"[^A-Z0-9]+", motor_detectado.upper().strip(), maxsplit=1)[0]

def obtener_modelo(motor_detectado: str) -> str | None:
    ini = _iniciales(motor_detectado)
    val = MODELO_POR_INICIAL.get(ini)
    return str(val).strip() if val else None

def buscar_info_motor(motor_detectado: str) -> dict | None:
    ini = _iniciales(motor_detectado)
    row = FILA_POR_INICIAL.get(ini)
    return dict(row) if row is not None else None

def obtener_casa_matriz(motor_detectado: str) -> str | None:
    info = buscar_info_motor(motor_detectado)
    if not info:
        return None
    val = str(info.get("Casa_Matriz", "")).strip()
    return val or None

def obtener_cobro_casamatriz(motor_detectado: str) -> str | None:
    info = buscar_info_motor(motor_detectado)
    if not info:
        return None
    return "Sí" if str(info.get("Cobro_Matriz", "")).strip() == "Si" else "No"


def obtener_responsable(motor_detectado: str) -> str | None:
    info = buscar_info_motor(motor_detectado)
    if not info:
        return None
    return str(info.get("Responsable", "")).strip() or None

