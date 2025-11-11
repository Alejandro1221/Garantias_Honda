from typing import Callable, Dict, List, Tuple, Optional
from BusquedaRef import buscar_referencias_en_texto, unir_lineas_cortadas
from items_costos import item_mas_costoso, extraer_mano_obra


from factura_gsm import (
    extraer_nit_factura,     
    extraer_fecha_expedicion_fact,   
    extraer_valor_total_operacion_fact, 
    extraer_factura_interna_fact,
)
from orden_gsm import (
    extraer_numero_orden,
    extraer_chasis_orden,      
    extraer_motor_orden,
    extraer_placa_orden,
    extraer_km_orden,
    extraer_fecha_venta_orden,
    extraer_fecha_dano_orden,
    extraer_modelo_orden,
)

from ia_factura_gsm import extraer_numero_factura_gsm

def _refs_y_desc(texto: str) -> List[Tuple[str, str]]:
    t = unir_lineas_cortadas(texto or "")
    rs = buscar_referencias_en_texto(t) or []
    vistos = set()
    pares = []
    for r in rs:
        ref = (r.get("Referencia","") or "").strip()
        if ref and ref not in vistos:
            pares.append((ref, (r.get("Descripcion","") or "").strip()))
            vistos.add(ref)
    return pares

def _refs_desc_por_costo(texto: str) -> List[Tuple[str, str]]:
    ranked = item_mas_costoso(texto, top_k=999)
    pares = []
    vistos = set()
    iters = ranked if isinstance(ranked, list) else ([ranked] if isinstance(ranked, dict) else [])
    for it in iters:
        ref = (it.get("ref") or "").strip()
        desc = (it.get("desc") or "").strip()
        if ref and ref not in vistos:
            pares.append((ref, desc))
            vistos.add(ref)
    if not pares:
        return _refs_y_desc(texto)
    return pares

def extraer_refs_joined(texto: str, _img=None) -> str:
    pares = _refs_desc_por_costo(texto)
    return "/ ".join([ref for ref,_ in pares])

def extraer_descs_joined(texto: str, _img=None) -> str:
    return ""

def extraer_mano_obra_fact(texto: str, _img=None) -> str:
    val = extraer_mano_obra(texto or "")
    return str(val) if val else ""

def extraer_num_fact_con_ia(texto: str, img) -> str:
    """
    Usa la IA (vision) para sacar el número de factura a partir de la imagen.
    'texto' se pasa como pista (hint) por si la IA no devuelve nada.
    """
    try:
        data = extraer_numero_factura_gsm(img, texto_hint=texto or "")
        return (data or {}).get("numero_factura", "") or ""
    except Exception:
        return ""

Extractor = Callable[[str, object], str]

FIELD_SOURCES: Dict[int, Dict[str, Optional[Extractor]]] = {
    0:  {"name": "numero_factura",  "factura": extraer_num_fact_con_ia, "orden": None},
    3:  {"name": "numero_solicitud","factura": None,                   "orden": extraer_numero_orden},
    4:  {"name": "nit_concesionario","factura": extraer_nit_factura,    "orden": extraer_nit_factura},
    8:  {"name": "chasis",           "factura": None,                   "orden": extraer_chasis_orden},
    9:  {"name": "motor",            "factura": None,                   "orden": extraer_motor_orden},
    10: {"name": "placa",            "factura": None,                   "orden": extraer_placa_orden},
    11: {"name": "modelo",           "factura": None,                   "orden": extraer_modelo_orden}, 
    15: {"name": "fecha_dano",       "factura": None,                   "orden": extraer_fecha_dano_orden},
    14: {"name": "fecha_venta",      "factura": None,                   "orden": extraer_fecha_venta_orden},
    17: {"name": "kilometraje",      "factura": None,                   "orden": extraer_km_orden},
    21: {"name": "referencia",       "factura": extraer_refs_joined,    "orden": None,},
    22: {"name": "descripcion",      "factura": extraer_descs_joined,   "orden": None,},
    28: {"name": "factura_interna",  "factura": extraer_factura_interna_fact,     "orden": None},
    29: {"name": "valor_total",      "factura": extraer_valor_total_operacion_fact, "orden": None},
    30: {"name": "mano_obra", "factura": extraer_mano_obra_fact, "orden": None},
    32: {"name": "fecha_expedicion", "factura": extraer_fecha_expedicion_fact,"orden": None},

}

def _safe(extractor: Optional[Extractor], texto: str, img) -> str:
    if extractor is None:
        return ""
    try:
        return (extractor(texto or "", img) or "").strip()
    except Exception:
        return ""

def calcular_valores_campos(
    modo: str,
    texto_actual: str,
    imagen_actual,
    texto_factura: Optional[str] = None,
    img_factura=None,
    texto_orden: Optional[str] = None,
    img_orden=None,
    estrategia: str = "prefer_modo",  
) -> List[Tuple[int, str]]:

    # Defaults de textos por si el caller no los pasó
    texto_factura = (texto_factura or "") if texto_factura is not None else ""
    texto_orden   = (texto_orden   or "") if texto_orden   is not None else ""

    # Si solo tenemos el texto “actual” (pantalla), úsalo como el del modo correspondiente
    if modo == "factura" and not texto_factura:
        texto_factura = texto_actual or ""
        img_factura = imagen_actual
    if modo == "orden" and not texto_orden:
        texto_orden = texto_actual or ""
        img_orden = imagen_actual

    out: List[Tuple[int, str]] = []

    for idx, spec in FIELD_SOURCES.items():
        f_ext = spec.get("factura")
        o_ext = spec.get("orden")

        val_f = _safe(f_ext, texto_factura, img_factura) if f_ext else ""
        val_o = _safe(o_ext, texto_orden,   img_orden)   if o_ext else ""

        val = ""
        if estrategia == "union":
            val = val_f or val_o
        elif estrategia == "interseccion":
            if val_f and (val_f == val_o or not o_ext):  
                val = val_f
            elif val_o and not f_ext:                  
                val = val_o
            else:
                val = ""  
        else:  
            if modo == "factura":
                val = val_f or val_o
            else: 
                val = val_o or val_f

        if val:
            out.append((idx, val))

    return out


