import os, io, base64, json, re, time
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
from fechas import fecha_factura

# ====== CONFIG SENCILLA ======
MODEL = "gpt-4o-mini"
IMG_MAX_SIDE = 2000
TIMING = True  # ← pon False si no quieres ver tiempos

print(f"[IA] ia_factura loaded from: {__file__}")
print(f"[IA] TIMING = {TIMING}")

# Carga API key (si la tienes en .env o en el entorno)
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None
print("API Key IA Factura:", "✔️" if client else "❌")

# ====== Utils ======
def _resize(img: Image.Image, max_side: int = IMG_MAX_SIDE) -> Image.Image:
    w, h = img.size
    s = min(max_side / max(w, h), 1.0)
    return img if s >= 1.0 else img.resize((int(w*s), int(h*s)), Image.LANCZOS)

def _to_data_url_with_size(img: Image.Image):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:image/png;base64,{b64}", len(raw)

def _solo_digitos_monto(s: str) -> str:
    if not s: return ""
    s = s.strip()
    if "," in s and "." in s:
        cut = max(s.rfind(","), s.rfind("."))
        s = s[:cut]
    return re.sub(r"[^\d]", "", s)

def _limpia_num_factura(s: str) -> str:
    if not s: return ""
    s = s.strip().upper()
    s = re.sub(r"[\u2012-\u2015]", "-", s)  # normaliza guiones largos
    s = s.replace(" ", "").replace("-", "")
    s = s.strip(".:#")
    if len(s) < 3 or len(s) > 25: return ""
    if re.fullmatch(r"\d{7,12}-\d", s): return ""  # NIT típico
    if re.search(r"\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}", s): return ""  # parece fecha
    if not re.search(r"\d{3,}", s): return ""
    if not re.match(r"^[A-Z]", s): return ""
    return s

# ====== Core ======
def extraer_campos_factura(img: Image.Image) -> dict:
    """
    Devuelve:
      {
        'numero_factura': '',
        'total_factura':  '',
        'mano_obra':      '',
        'ref_principal':  '',
        'fecha_emision':  'YYYY-MM-DD'
      }
    """
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

        # prompt
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
            "P1) MANO DE OBRA: valor en COP como solo dígitos. Considera rótulos: 'mano de obra', 'FRT', 'servicio(s)', 'M.O.' etc. Si hay varias líneas, suma.\n"
            "P2) ITEMS: SOLO repuestos (ref, descripcion, precio_en_COP). Excluye mano de obra/FRT.\n"
            "P3) REF PRINCIPAL = ref del ítem con mayor precio.\n"
            "P4) NUMERO Y TOTAL: numero_factura sin guiones/espacios; total_factura solo dígitos.\n"
            "P5) FECHA EMISION: fecha de emisión/generación en formato YYYY-MM-DD; si no está, \"\".\n"
            "P6) FORMATO: si un campo no existe, deja \"\". Devuelve SOLO el JSON.\n"
        )

        # llamada API
        t = time.perf_counter()
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.0,
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

        # parseo
        t = time.perf_counter()
        txt = (resp.choices[0].message.content or "").strip()
        m = re.search(r"\{.*\}", txt, flags=re.S)
        data = json.loads(m.group(0)) if m else json.loads(txt)
        t_parse = time.perf_counter() - t

        # limpieza
        t = time.perf_counter()
        out["numero_factura"] = _limpia_num_factura(data.get("numero_factura", "") or "")
        out["total_factura"]  = _solo_digitos_monto(data.get("total_factura", "") or "")
        out["mano_obra"]      = _solo_digitos_monto(data.get("mano_obra", "") or "")
        out["ref_principal"]  = (data.get("ref_principal", "") or "").strip()
        out["fecha_emision"]  = fecha_factura(data.get("fecha_emision", "") or "")
        t_clean = time.perf_counter() - t

        # corrección ref_principal por items
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
