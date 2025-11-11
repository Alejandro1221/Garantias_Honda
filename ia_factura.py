import os, io, base64, json, re, time
from dotenv import load_dotenv
from openai import OpenAI
from fechas import fecha_factura
from PIL import Image

MODEL = "gpt-4o-mini"   
IMG_MAX_SIDE = 1400
TIMING = True

print(f"[IA] ia_factura loaded from: {__file__}")
print(f"[IA] TIMING = {TIMING}")

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None
print("API Key IA Factura:", "✔️" if client else "❌")

# --- Utilidades ---
def _resize(img: Image.Image, max_side: int = IMG_MAX_SIDE) -> Image.Image:
    w, h = img.size
    s = min(max_side / max(w, h), 1.0)
    return img if s >= 1.0 else img.resize((int(w*s), int(h*s)), Image.LANCZOS)

def _to_data_url_with_size(img: Image.Image):
    # Escala de grises + JPEG con compresión adecuada
    img2 = img.convert("L")
    buf = io.BytesIO()
    img2.save(buf, format="JPEG", quality=75, optimize=True, progressive=True)
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}", len(raw)

def _solo_digitos_monto(s: str) -> str:
    """
    Normaliza un monto (COP) a solo dígitos.
    Maneja: $ 1.234.567,89 -> '1234567' (ignora decimales)
            1,234,567.00   -> '1234567'
            1234567        -> '1234567'
    """
    if not s:
        return ""
    s = s.strip()

    # Si hay punto y coma, asume que el separador más a la derecha es decimal y córtalo
    if "," in s and "." in s:
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        cut = max(last_comma, last_dot)
        s = s[:cut]

    # Quita todo lo que no sea dígito
    s = re.sub(r"[^\d]", "", s)
    return s

def _limpia_num_factura(s: str) -> str:
    if not s:
        return ""
    s = s.strip().upper()
    s = re.sub(r"[\u2012-\u2015]", "-", s)  # normaliza guiones largos
    s = s.replace(" ", "").replace("-", "")
    s = s.strip(".:#")
    if len(s) < 3 or len(s) > 25:
        return ""
    if re.fullmatch(r"\d{7,12}-\d", s):        # NIT típico
        return ""
    if re.search(r"\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}", s):  # formato de fecha
        return ""
    if not re.search(r"\d{3,}", s):
        return ""
    if not re.match(r"^[A-Z]", s):
        return ""
    return s

def extraer_campos_factura(img: Image.Image) -> dict:
    out = {"numero_factura": "", "total_factura": "", "mano_obra": "", "ref_principal": "", "fecha_emision": ""}

    if not client or img is None:
        return out

    def _to_int_digits(s: str) -> int:
        s = re.sub(r"[^\d]", "", s or "")
        return int(s) if s else 0

    try:
        t0 = time.perf_counter()

        # resize
        t = time.perf_counter()
        img_api = _resize(img, IMG_MAX_SIDE)
        t_resize = time.perf_counter() - t


        # data url
        t = time.perf_counter()
        data_url, payload_bytes = _to_data_url_with_size(img_api)
        t_encode = time.perf_counter() - t

        prompt = (
            "Objetivo PRIORITARIO: Detecta primero el valor de MANO DE OBRA y solo después completa el resto.\n"
            "Devuelve SOLO JSON con este esquema EXACTO:\n"
            "{\n"
            "  \"numero_factura\": \"\",\n"
            "  \"total_factura\":  \"\",\n"
            "  \"mano_obra\":      \"\",\n"
            "  \"ref_principal\":  \"\",\n"
            "  \"items\": [ {\"ref\":\"\",\"descripcion\":\"\",\"precio_en_COP\":\"\"} ],\n"
            "  \"fecha_emision\":  \"\",\n"
            "}\n"
            "\n"
            "REGLAS (en orden de prioridad):\n"
            "P1) MANO DE OBRA (campo 'mano_obra'):\n"
            "   - Extrae el VALOR EN COP como SOLO dígitos (sin $, puntos, comas ni decimales).\n"
            "   - Busca en rótulos como: 'mano de obra', 'mano de obra de garantías', 'FRT', 'VALOR FRT', 'mantenimiento', 'Reparacion', 'servicios', 'servicio técnico',\n"
            "   - Si el valor trae decimales (ej. 1200.25 o 1.200,25), DEVUELVE SOLO LA PARTE ENTERA en COP (1200)\n"
            "   - NUNCA escoger el valor de la columna VALOR UNITARIO, sino el valor TOTAL asociado a la mano de obra.\n"
            "   - NUNCA dejes 'mano_obra' vacío si existe algún valor visible relacionado a estos rótulos.\n"
            "\n"
            "P2) ITEMS (solo repuestos):\n"
            "   - 'items' es SOLO repuestos (ref + descripción + precio). EXCLUYE mano de obra/FRT\n"
            "   - ref: código tal cual (ej: 01210-xxx-xxx, 15312-xxx-600), sin espacios extra.\n"
            "   - descripcion: texto corto.\n"
            "   - precio_en_COP: SOLO dígitos.\n"
            "\n"
            "P3) REF PRINCIPAL:\n"
            "   - 'ref_principal' = la 'ref' del ítem con mayor 'precio_en_COP'. Si no hay repuestos, \"\".\n"
            "\n"
            "P4) NÚMERO Y TOTAL:\n"
            "   - numero_factura: ejemplos FV-00123, FAC12345; devuélvelo SIN guiones ni espacios. Nunca inicia con dígito.\n"
            "   - total_factura: monto TOTAL en COP (SOLO dígitos).\n"
            "\n"
            "P5) FECHA EMISION:\n"
            "   - Campo 'fecha_emision' = FECHA DE EMISION//GENERACION de la factura .\n"
            "   - Devuélvela en formato YYYY-MM-DD. Si no está, deja \"\".\n"
            "P6) FORMATO:\n"
            "   - Si un campo no existe, déjalo \"\" (vacío). Devuelve SOLO el JSON, sin comentarios.\n"
            "\n"
          
        )
        t = time.perf_counter()
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.0,
            # Si tu SDK lo soporta, activa JSON estricto:
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Eres un extractor de campos de facturas en español."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]},
            ],
        )
        t_api = time.perf_counter() - t

        t = time.perf_counter()
        txt = (resp.choices[0].message.content or "").strip()
        m = re.search(r"\{.*\}", txt, flags=re.S)
        data = json.loads(m.group(0)) if m else json.loads(txt)
        t_parse = time.perf_counter() - t

        # Limpieza base
        t = time.perf_counter()
        out["numero_factura"] = _limpia_num_factura(data.get("numero_factura", "") or "")
        out["total_factura"]  = _solo_digitos_monto(data.get("total_factura", "") or "")
        out["mano_obra"]      = _solo_digitos_monto(data.get("mano_obra", "") or "")
        out["ref_principal"]  = (data.get("ref_principal", "") or "").strip()
        out["fecha_emision"] = fecha_factura(data.get("fecha_emision", "") or "")
        t_clean = time.perf_counter() - t

        # Corrección por items (por si el modelo dudó):
        items = data.get("items") or []
        mejor_ref, mejor_val = "", 0
        for it in items:
            ref  = (it.get("ref") or "").strip()
            desc = (it.get("descripcion") or "").lower()
            val  = _to_int_digits(it.get("precio_en_COP"))
            if not ref or any(k in desc for k in ["mano de obra", "labor", "frt"]):
                continue
            if val > mejor_val:
                mejor_val, mejor_ref = val, ref
        if not out["ref_principal"]:
            out["ref_principal"] = mejor_ref

         # tiempos
        if TIMING:
            t_total = time.perf_counter() - t0
            w, h = img_api.size
            print(
                f"[IA-TIME] resize={t_resize*1000:.0f} ms | encode={t_encode*1000:.0f} ms | "
                f"api={t_api*1000:.0f} ms | parse={t_parse*1000:.0f} ms | clean={t_clean*1000:.0f} ms | "
                f"total={t_total*1000:.0f} ms | img={w}x{h} | payload≈{payload_bytes/1024:.1f} KB | "
                f"req_id={getattr(resp, 'id', '-')}"
            )

        return out

    except Exception as e:
        print("Error IA Factura (campos):", e)
        return out