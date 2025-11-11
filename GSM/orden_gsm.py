import re
#from modelos_moto import mapear_linea_a_modelo_catalogo, detectar_modelo_en_texto

_SEP = r"[ \t\r\n\f\v\u00A0\-\.:]"
def _norm(s: str) -> str:
    return re.sub(_SEP + "+", "", (s or "").strip()).upper()

# ---------- NÚMERO DE ORDEN (40000nnnnnn) ----------
_ANCLA_ORDEN = re.compile(r"(ORDEN\s+DE\s+SERVICIO|ORDEN\s+DE\s+TALLER|N[oº°\.\s]*ORDEN)", re.I)
_PAT_ORDEN_40000 = re.compile(r"\b40000\d{5,8}\b")

def _digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def extraer_numero_orden(texto: str, _img=None) -> str:
    if not texto:
        return ""

    # 1) Buscar cerca del ancla (“ORDEN DE SERVICIO …” / “ORDEN DE TALLER …”)
    lines = [l.strip() for l in texto.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if _ANCLA_ORDEN.search(l):
            # mira la línea del ancla y un pequeño vecindario
            blob = " ".join(lines[i:i+3])
            # primero prueba directo (por si viene limpio)
            m = _PAT_ORDEN_40000.search(blob)
            if m:
                return m.group(0)
            # si viene con puntos, espacios o símbolos entre medio, limpiamos a solo dígitos y re-buscamos
            m2 = re.search(r"(40000\d{5,8})", _digits_only(blob))
            if m2:
                return m2.group(1)

    # 2) Fallback global (en todo el texto)
    m = _PAT_ORDEN_40000.search(texto)
    if m:
        return m.group(0)
    m2 = re.search(r"(40000\d{5,8})", _digits_only(texto))
    return m2.group(1) if m2 else ""

# --------------------- N° CHASIS / VIN ----------------------------
_VIN_CHAR = r"[A-HJ-NPR-Z0-9]"                 # VIN válido (sin I,O,Q)
_PAT_VIN_STRICT = re.compile(rf"\b({_VIN_CHAR}{{17}})\b")
_ANCLA_CHASIS = re.compile(r"(No\.\s*Chasis|Chasis|VIN)", re.I)

def extraer_chasis_orden(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]
    # Cerca del ancla
    for i, l in enumerate(lines):
        if _ANCLA_CHASIS.search(l):
            blob = " ".join(lines[i:i+4])
            m = _PAT_VIN_STRICT.search(blob)
            if m: return m.group(1).upper()
    # Fallback global
    m = _PAT_VIN_STRICT.search(texto)
    return m.group(1).upper() if m else ""

# ---------- MOTOR----------
# Letras/números con posible guion en medio (5–6 letras/dígitos, guion, 5–8 dígitos)
_PAT_MOTOR = re.compile(r"\b([A-Z0-9]{3,6}\-\d{5,8})\b", re.I)
_ANCLA_MOTOR = re.compile(r"(No\.\s*Motor|Motor)", re.I)

def extraer_motor_orden(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if _ANCLA_MOTOR.search(l):
            blob = " ".join(lines[i:i+4])
            m = _PAT_MOTOR.search(blob)
            if m: return _norm(m.group(1))
    m = _PAT_MOTOR.search(texto)
    return _norm(m.group(1)) if m else ""

# ---------- PLACA ----------
_PAT_PLACA = re.compile(r"\b([A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z])\b")

_ANCLA_PLACA = re.compile(r"(Placa)", re.I)
def extraer_placa_orden(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if _ANCLA_PLACA.search(l):
            blob = " ".join(lines[i:i+3])
            m = _PAT_PLACA.search(blob)
            if m: return _norm(m.group(1))
    m = _PAT_PLACA.search(texto)
    return _norm(m.group(1)) if m else ""

# ---------- KILOMETRAJE ----------
# “KM: 47” o “Kilometraje ... 4”
_PAT_KM = re.compile(r"\b(KM|Kilometraje)\b\s*[:\-]?\s*([0-9]{1,6})\b", re.I)

def extraer_km_orden(texto: str, _img=None) -> str:
    if not texto:
        return ""
    # primero por patrón “KM: nnn”
    m = _PAT_KM.search(texto)
    if m:
        return m.group(2)
    # fallback simple: número al lado de “KM”
    m = re.search(r"\bKM\b\D{0,5}(\d{1,6})\b", texto, re.I)
    return m.group(1) if m else ""

# --- Fecha de daño (desde "FECHA DE APERTURA") ---
_ANCLA_FE_AP = re.compile(r"FECHA\s*DE\s*APERTURA", re.I)
_PAT_FECHA_ORD = re.compile(r"\b(\d{2}[\/\-.]\d{2}[\/\-.]\d{4}|\d{4}[\/\-.]\d{2}[\/\-.]\d{2})\b")

def extraer_fecha_dano_orden(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]

    # 1) cerca del ancla
    for i, l in enumerate(lines):
        if _ANCLA_FE_AP.search(l):
            blob = " ".join(lines[i:i+3])  # línea + una o dos siguientes (por el OCR)
            m = _PAT_FECHA_ORD.search(blob)
            if m:
                return _norm_fecha_orden(m.group(1))  # Devuelve DD/MM/YYYY

    # 2) fallback global por si quedó más lejos
    m = re.search(_ANCLA_FE_AP.pattern + r".{0,120}?" + _PAT_FECHA_ORD.pattern, texto, flags=re.I|re.S)
    if m:
        return _norm_fecha_orden(m.group(1))

    return ""

# ---------- MODELOS ----------
_ANCLA_LINEA = re.compile(r"\b(L[ií]nea)\b", re.I)
_PAT_LINEA_VAL = re.compile(r"([A-Z0-9][A-Z0-9 ]*(?:\.\d+)?)")

def _clean_linea_chunk(s: str) -> str:
    s = (s or "").strip()
    # corta en separadores típicos que siguen al modelo
    s = re.split(r"[–\-,:;…]| {2,}", s)[0].strip()   # en-dash, guion, coma, dos puntos, etc.
    # quita puntos suspensivos sueltos
    s = s.rstrip(".").strip()
    return s

def extraer_modelo_orden(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]

    # 1) Buscar la palabra “Línea” y tomar 1–2 renglones pegar
    for i, l in enumerate(lines):
        if _ANCLA_LINEA.search(l):
            blob = " ".join(lines[i:i+2])
            # toma lo que sigue a 'Línea:' si existe
            after = re.split(r"L[ií]nea\s*[:\-]\s*", blob, flags=re.I, maxsplit=1)
            cand = after[1] if len(after) > 1 else blob
            cand = _clean_linea_chunk(cand)
            m = _PAT_LINEA_VAL.search(cand)
            if m:
                linea_detectada = m.group(1).strip()
                mapped = mapear_linea_a_modelo_catalogo(linea_detectada)
                return mapped or linea_detectada  # si no mapea, al menos devuelve limpio

    # 2) Fallback global por si se perdió el “Línea”
    m = re.search(r"L[ií]nea\s*[:\-]\s*([^\n\r]+)", texto, flags=re.I)
    if m:
        cand = _clean_linea_chunk(m.group(1))
        m2 = _PAT_LINEA_VAL.search(cand)
        if m2:
            linea_detectada = m2.group(1).strip()
            mapped = mapear_linea_a_modelo_catalogo(linea_detectada)
            return mapped or linea_detectada

    return ""

def extraer_modelo_orden(texto: str, _img=None) -> str:
        return detectar_modelo_en_texto(texto or "")

#------------FECHA DE VENTA (D/MM/YYYY) ------------
_ANCLA_FE_INI_GAR = re.compile(r"Fecha\s*Inicio\s*de\s*Garant[ií]a", re.I)
_PAT_FECHA_ORD = re.compile(r"\b(\d{2}[\/\-.]\d{2}[\/\-.]\d{4}|\d{4}[\/\-.]\d{2}[\/\-.]\d{2})\b")

def _norm_fecha_orden(fe: str) -> str:
    fe = (fe or "").strip().replace("-", "/").replace(".", "/")
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", fe)  # DD/MM/YYYY
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    m = re.match(r"(\d{4})/(\d{2})/(\d{2})", fe)  # YYYY/MM/DD
    if m:
        return f"{int(m.group(3)):02d}/{int(m.group(2)):02d}/{m.group(1)}"
    return fe

def extraer_fecha_venta_orden(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]

    # 1) Buscar cerca del ancla en 1–2 renglones siguientes (sobrevive a OCR con saltos)
    for i, l in enumerate(lines):
        if _ANCLA_FE_INI_GAR.search(l):
            blob = " ".join(lines[i:i+3])
            m = _PAT_FECHA_ORD.search(blob)
            if m:
                return _norm_fecha_orden(m.group(1))

    # 2) Fallback global por si el OCR separó demasiado
    m = re.search(_ANCLA_FE_INI_GAR.pattern + r".{0,120}?" + _PAT_FECHA_ORD.pattern, texto, flags=re.I|re.S)
    if m:
        return _norm_fecha_orden(m.group(1))

    return ""
