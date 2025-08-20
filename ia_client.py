import os
from openai import OpenAI
from dotenv import load_dotenv

# --- Cargar variables de entorno desde .env ---
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# --- Inicializar cliente ---
if api_key:
    _client = OpenAI(api_key=api_key)
    print("API Key cargada: ✔️")
else:
    _client = None
    print("API Key cargada: ❌")

# --- Helpers opcionales ---
def _anonimizar(texto: str) -> str:
    """Enmascara VIN/NIT antes de enviar a la nube (opcional)."""
    import re
    texto = re.sub(r"\b[A-HJ-NPR-Z0-9]{17}\b", "VIN_REDACTED", texto)  # VIN
    texto = re.sub(r"\b\d{7,12}(-\d)?\b", "NIT_REDACTED", texto)      # NIT
    return texto

USE_IA = False

# --- Función principal ---
def extraer_descripcion_falla(texto_ocr: str) -> str:
    """
    Devuelve SOLO la descripción de la falla como una línea de texto.
    Si no encuentra, devuelve "".
    """
    if not texto_ocr or not _client:
        return ""
    
    if not USE_IA or _client is None:
        return "SIMULACIÓN: descripción de falla (IA OFF)"

    prompt = f"""
Eres un extractor de campos de órdenes de servicio mecánicas.
Del texto OCR a continuación, devuelve EXCLUSIVAMENTE la "descripción de la falla".
- No incluyas prefijos como "Descripción:" ni explicaciones.
- Si no hay una descripción clara, devuelve vacío.

TEXTO_OCR:
---
{_anonimizar(texto_ocr)}
---
    """.strip()

    try:
        resp = _client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            temperature=0.1,
            max_output_tokens=120,
        )
        return (resp.output_text or "").strip()
    except Exception as e:
        print("⚠️ Error al llamar a OpenAI:", e)
        return ""
