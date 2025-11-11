import os, io, base64, json, re, time, hashlib
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageFilter, ImageEnhance

# === CONFIG ===
MODEL = "gpt-4o-mini"
IMG_MAX_SIDE = 1520
TIMING = True

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None
print("[GSM-IA] API Key:", "✔️" if client else "❌")

# --- cache simple en memoria ---
_MEMO = {}

# === UTILIDADES ===
def _resize(img: Image.Image, max_side: int = IMG_MAX_SIDE) -> Image.Image:
    """Redimensiona sin perder proporción."""
    w, h = img.size
    s = min(max_side / max(w, h), 1.0)
    return img if s >= 1.0 else img.resize((int(w * s), int(h * s)), Image.LANCZOS)

def _crop_header_top_right(img: Image.Image) -> Image.Image:
    """Recorta la esquina superior derecha donde suele estar el número de factura."""
    w, h = img.size
    left = int(w * 0.55)
    upper = 0
    right = w
    lower = int(h * 0.35)
    crop = img.crop((left, upper, right, lower))
    # Escalar un poco el recorte para que el texto quede más grande
    cw, ch = crop.size
    crop = crop.resize((int(cw * 1.5), int(ch * 1.5)), Image.LANCZOS)
    return crop

def _to_data_url_with_size(img: Image.Image, fmt="PNG"):
    """Convierte la imagen a base64. PNG conserva mejor el texto."""
    img2 = img.convert("L")
    buf = io.BytesIO()
    if fmt.upper() == "PNG":
        img2.save(buf, format="PNG", optimize=True)
        mime = "image/png"
    else:
        img2.save(buf, format="JPEG", quality=80, optimize=True, progressive=True)
        mime = "image/jpeg"
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime};base64,{b64}", len(raw)

def _enhance_for_vision(img: Image.Image) -> Image.Image:
    """Mejora contraste y nitidez para lectura de texto."""
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
    return img


def _limpia_num_gsm(s: str) -> str:
    """Limpia caracteres extra (No., N°, espacios, etc)."""
    if not s:
        return ""
    s = s.strip().upper()
    s = re.sub(r"^\s*N[°ºO\.]*\s*", "", s, flags=re.I)
    s = re.sub(r"[^A-Z0-9\-]", "", s)
    return s

def _extraer_json_seguro(txt: str) -> dict:
    """Intenta cargar JSON; si viene con texto adicional, rescata el primer {...}."""
    txt = (txt or "").strip()
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}

def _fallback_regex(texto_hint: str) -> str:
    if not texto_hint:
        return ""
    patrones = [
        r"\b(\d{2}\s*[A-Z]\s*M\s*\d{4,5})\b",  # ← captura en grupo 1
        r"FACTURA(?: ELECTRONICA| ELECTRÓNICA)?[:\s\-]*.*?(?:N[°ºO\.]?\s*)?(\d{2}\s*[A-Z]\s*M\s*\d{4,5})",
    ]
    for pat in patrones:
        m = re.search(pat, texto_hint, flags=re.I)
        if m:
            g = m.group(1) if m.lastindex else m.group(0)
            return _limpia_num_gsm(g)
    return ""

# === AUTO-CORRECCIÓN DE ERRORES VISUALES ===
def _auto_fix_factura(num: str) -> str:
    """
    Corrige errores visuales comunes como:
    - 498M9483  → 48GM9483
    - 486M9485  → 48GM9485
    - 48G69483  → 48GM9483
    """
    if not num:
        return ""
    num = num.strip().upper().replace(" ", "")

    # Confusiones visuales (O↔0, B↔8, S↔5, Z↔2, I/L↔1)
    traducciones = str.maketrans({
        "O": "0", "B": "8", "S": "5", "Z": "2", "I": "1", "L": "1"
    })
    num = num.translate(traducciones)

    # Caso: 498M9483 (3er caracter es número → insertar 'G')
    if re.match(r"^\d{2}\dM\d{4,5}$", num):
        num = num[:2] + "G" + num[2:]

    # Caso: 48G69483 (4to caracter es número → corregir 'M')
    elif re.match(r"^\d{2}[A-Z]\d\d{4,5}$", num):
        num = num[:3] + "M" + num[4:]

    # Eliminar guiones o espacios sobrantes
    num = re.sub(r"[\s\-]+", "", num)
    return num

# === PRINCIPAL ===
def extraer_numero_factura_gsm(img: Image.Image, texto_hint: str = "") -> dict:
    """
    Devuelve: {"numero_factura": "<num o ''>"}
    - img: PIL.Image de la página
    - texto_hint: texto OCR de la misma página (opcional)
    """
    out = {"numero_factura": ""}

    if img is None:
        return out

    # Cache para evitar repeticiones
    try:
        #img_api = _resize(img, IMG_MAX_SIDE)
        #data_url, payload_bytes = _to_data_url_with_size(img_api)
        # Redimensionar y recortar el encabezado (zona del número)
        img_api = _resize(img, IMG_MAX_SIDE)
        hdr = _crop_header_top_right(img_api)
        hdr = _enhance_for_vision(hdr)  # mejora contraste y nitidez

        # Exportar recorte en PNG (más claro)
        hdr_url, _ = _to_data_url_with_size(hdr, fmt="PNG")

        # También conserva la página completa (para contexto)
        data_url, payload_bytes = _to_data_url_with_size(img_api, fmt="JPEG")
        h = hashlib.md5(data_url.encode("utf-8")).hexdigest()
        if h in _MEMO:
            return {"numero_factura": _MEMO[h]}
    except Exception as e:
        print("[GSM-IA] prep img:", e)
        out["numero_factura"] = _fallback_regex(texto_hint)
        return out

    if not client:
        out["numero_factura"] = _fallback_regex(texto_hint)
        return out

    t0 = time.perf_counter()
    prompt = (
        "Eres un extractor de campos de facturas.\n"
        "Devuelve SOLO el número de la factura.\n\n"
        "Formato esperado: dos dígitos + una letra + 'M' + cinco dígitos "
        "(ejemplo: 48GM9483).\n"
        "Ignora prefijos como 'No', 'N°', etc. y elimina espacios.\n"
        "Responde SOLO en JSON: {\"numero_factura\": \"\"}"
    )

    messages = [
        {"role": "system", "content": "Responde exclusivamente con JSON válido."},
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": hdr_url}},   # primero el recorte
            {"type": "image_url", "image_url": {"url": data_url}},  # luego la página completa
        ]},
    ]

    # --- reintentos sólo si hay rate limit (429) ---
    backoff = [0.0, 0.6, 1.2, 2.4]  # segundos; empieza sin esperar
    resp = None
    last_err = None

    for wait in backoff:
        if wait:
            time.sleep(wait)
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=messages,
            )
            break  # éxito
        except Exception as e:
            last_err = e
            s = str(e).lower()
            # si es rate limit (429), reintenta; si es otra cosa, corta
            if ("rate limit" in s) or ("429" in s):
                continue
            print("[GSM-IA] Error:", e)
            out["numero_factura"] = _fallback_regex(texto_hint)
            return out

    if resp is None:
        # agotó reintentos por 429
        print("[GSM-IA] Rate limit persistente; usando fallback OCR/regex.")
        out["numero_factura"] = _fallback_regex(texto_hint)
        return out

    raw = (resp.choices[0].message.content or "").strip()
    data = _extraer_json_seguro(raw)
    num = _limpia_num_gsm(data.get("numero_factura", "") or "")

    # (si usas tu auto-fix, aplícalo aquí)
    # num = _auto_fix_factura(num)

    if not num and texto_hint:
        num = _fallback_regex(texto_hint)

    out["numero_factura"] = num
    _MEMO[h] = num

    if TIMING:
        dt = (time.perf_counter() - t0) * 1000
        print(f"[GSM-IA] num='{num}'  | payload≈{payload_bytes/1024:.1f} KB | {dt:.0f} ms")

    return out


