import re

def fecha_factura(s: str) -> str:
    """
    Devuelve 'YYYY-MM-DD' si reconoce formatos típicos de FACTURA:
      - YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
      - DD/MM/YYYY / DD-MM-YYYY / DD.MM.YYYY
      - YYYYMMDD (sin separadores)
    Si no reconoce, devuelve ''.
    """
    if not s:
        return ""
    s = s.strip()

    # 1) YYYY-MM-DD (o / .)
    m = re.search(r"\b(\d{4})[\/\.-](\d{1,2})[\/\.-](\d{1,2})\b", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    # 2) DD/MM/YYYY (o - .)
    m = re.search(r"\b(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{4})\b", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    # 3) YYYYMMDD (8 dígitos seguidos)
    m = re.search(r"\b(\d{4})(\d{2})(\d{2})\b", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    return ""
