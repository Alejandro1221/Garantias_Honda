import re
from BusquedaRef import buscar_referencias_en_texto, unir_lineas_cortadas

NIT_GSM = "901038167"

# ---------- NIT CONCESIONARIO  ----------
def extraer_nit_factura(_texto: str = "", _img=None) -> str:
    return NIT_GSM

# ---------- FECHA DE EXPEDICIÓN (factura) ----------
_ANCLA_FE_EXP = re.compile(r"Fecha\s*(y\s*Hora\s*de\s*)?Expedici[oó]n", re.I)
_ANCLA_FE_GEN = re.compile(r"Fecha\s*(y\s*Hora\s*de\s*)?Generaci[oó]n", re.I)

_PAT_FECHA = re.compile(r"\b(\d{4}[\/\-.]\d{2}[\/\-.]\d{2}|\d{2}[\/\-.]\d{2}[\/\-.]\d{4})\b")


def _norm_fecha(fe: str) -> str:
    """Devuelve D/MM/YYYY (día sin cero; mes con 2 dígitos)."""
    fe = fe.replace("-", "/").replace(".", "/").strip()
    m = re.match(r"(\d{4})/(\d{2})/(\d{2})", fe)  # YYYY/MM/DD
    if m:
        yyyy, mm, dd = m.groups()
        return f"{int(dd)}/{int(mm):02d}/{yyyy}"
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", fe)  # DD/MM/YYYY
    if m:
        dd, mm, yyyy = m.groups()
        return f"{int(dd)}/{int(mm):02d}/{yyyy}"
    return fe

def extraer_fecha_expedicion_fact(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]

    # 1) Buscar cerca de "Fecha de Expedición"
    for i, l in enumerate(lines):
        if _ANCLA_FE_EXP.search(l):
            blob = " ".join(lines[i:i+3])
            m = _PAT_FECHA.search(blob)
            if m:
                return _norm_fecha(m.group(1))

    # 2) Respaldo: buscar cerca de "Fecha de Generación"
    for i, l in enumerate(lines):
        if _ANCLA_FE_GEN.search(l):
            blob = " ".join(lines[i:i+3])
            m = _PAT_FECHA.search(blob)
            if m:
                return _norm_fecha(m.group(1))

    # 3) Fallbacks globales por si el OCR separó mucho
    m = re.search(_ANCLA_FE_EXP.pattern + r".{0,120}?" + _PAT_FECHA.pattern, texto, flags=re.I|re.S)
    if m:
        return _norm_fecha(m.group(1))

    m = re.search(_ANCLA_FE_GEN.pattern + r".{0,120}?" + _PAT_FECHA.pattern, texto, flags=re.I|re.S)
    if m:
        return _norm_fecha(m.group(1))

    return ""

_ANCLA_TOTAL_OP = re.compile(r"VALOR\s+TOTAL\s+DE\s+LA\s+OPERACI[oó]N", re.I)

# número con miles (.,) y decimales opcionales
_PAT_IMPORTE = re.compile(
    r"([0-9]{1,3}(?:[.,][0-9]{3})+[.,]\d{2}|[0-9]+[.,]\d{2}|[0-9]{1,3}(?:[.,][0-9]{3})+)"
)

def _to_int_without_decimals(s: str) -> str:
    s = (s or "").strip()
    # ¿tiene separador decimal explícito al final con 2 dígitos?
    m = re.search(r"([.,])(\d{2})\s*$", s)
    has_decimal = bool(m)
    digits = re.sub(r"\D", "", s)
    if has_decimal and len(digits) > 2:
        digits = digits[:-2]  # quita decimales
    return digits

def extraer_valor_total_operacion_fact(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]
    if not lines:
        return ""

    # 1) Buscar cerca del ancla (misma línea y hasta 3 líneas después)
    for i, l in enumerate(lines):
        if _ANCLA_TOTAL_OP.search(l):
            blob = " ".join(lines[i : min(i + 4, len(lines))])
            m = _PAT_IMPORTE.search(blob)
            if m:
                return _to_int_without_decimals(m.group(1))

    # 2) Fallback global por si el importe queda lejos del texto “ancla”
    m = re.search(_ANCLA_TOTAL_OP.pattern + r".{0,80}?" + _PAT_IMPORTE.pattern, texto, flags=re.I|re.S)
    if m:
        # el último grupo del patrón completo NO es el importe, por eso volvemos a buscar importe en ese tramo
        tail = texto[m.start(): m.end()]
        m2 = _PAT_IMPORTE.search(tail)
        if m2:
            return _to_int_without_decimals(m2.group(1))
    return ""

# ---------- FACTURA INTERNA----------
_ANCLA_FACT_INT_FACT = re.compile(r"(No\.\s*Factura\s*Intern[oa]|Factura\s*Intern[oa])", re.I)
_ANCLA_TABLA_FACT_INT = re.compile(r"Marca.*L[ií]nea.*Modelo.*Factura\s*Intern", re.I)

_PAT_FACT_INT_10 = re.compile(r"\b(040\d{7})\b")

def extraer_factura_interna_fact(texto: str, _img=None) -> str:
    if not texto:
        return ""
    lines = [l.strip() for l in texto.splitlines() if l.strip()]
    if not lines:
        return ""

    for i, l in enumerate(lines):
        if _ANCLA_FACT_INT_FACT.search(l):
            blob = " ".join(lines[i:i+4])  
            m = _PAT_FACT_INT_10.search(blob)
            if m:
                return m.group(1)

    for i, l in enumerate(lines):
        if _ANCLA_TABLA_FACT_INT.search(l):
            blob = " ".join(lines[i:i+4])
            m = _PAT_FACT_INT_10.search(blob)
            if m:
                return m.group(1)
    return ""

# ---------- ITEMS DE LA FACTURA ----------
def imprimir_refs_consola(texto: str):
    t = unir_lineas_cortadas(texto or "")
    refs = buscar_referencias_en_texto(t) or []
    print(f"[REFS] detectadas: {len(refs)}")
    for r in refs:
        print(f"- {r.get('Referencia','')} | {r.get('Descripcion','')}")


