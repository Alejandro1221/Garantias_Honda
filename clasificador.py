import os, io, re, unicodedata
from typing import List, Tuple
import fitz
from PIL import Image
import pytesseract
from pdf_io import leer_pdf_con_ocr, leer_primera_pagina, leer_pdf_aumentado

from GSM.orden_gsm import (
    extraer_numero_orden,
    extraer_chasis_orden,
    extraer_motor_orden,
    extraer_placa_orden
)

class ClasificadorService:
    def __init__(self, base_out="Garantias", tesseract_cmd=None):
        self.BASE_OUT = os.path.abspath(base_out)
        self.DIR_FACTURAS = os.path.join(self.BASE_OUT, "Facturas")
        self.DIR_ORDENES = os.path.join(self.BASE_OUT, "Ordenes")
        self.DIR_SINPAR   = os.path.join(self.BASE_OUT, "SinPar")
        self.DIR_REVISION = os.path.join(self.BASE_OUT, "Revision")
        os.makedirs(self.DIR_FACTURAS, exist_ok=True)
        os.makedirs(self.DIR_ORDENES, exist_ok=True)
        os.makedirs(self.DIR_SINPAR,   exist_ok=True)
        os.makedirs(self.DIR_REVISION, exist_ok=True)
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def _clasificar_texto(self, texto: str) -> str:
        return self._clasificar(texto or "")

    # ---------- utilidades ----------
    @staticmethod
    def human_size(nbytes: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        s = 0
        size = float(nbytes)
        while size >= 1024 and s < len(units) - 1:
            size /= 1024.0
            s += 1
        return f"{size:.1f} {units[s]}"

    @staticmethod
    def _norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = re.sub(r"\s+", " ", s.lower()).strip()
        return s

    @staticmethod
    def _safe_token(s: str) -> str:
        s = (s or "").strip().replace(" ", "_")
        s = re.sub(r"[^A-Za-z0-9._-]", "", s)
        return s or "SINNUM"

    def _texto_pagina(self, page, dpi=300, lang="eng") -> str:
        texto = (page.get_text("text") or "").strip()
        if texto:
            return texto
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        return pytesseract.image_to_string(img, lang=lang, config="--oem 3 --psm 6") or ""

    def _texto_top(self, page, top_ratio=0.38, dpi=300, lang="eng") -> str:

        # 1) Texto embebido en la parte superior
        try:
            blocks = page.get_text("blocks") or []
            h = page.rect.height
            tops = [b[4] for b in blocks if len(b) >= 5 and b[3] <= h * top_ratio and b[4]]
            txt = " ".join(tops).strip()
            if txt:
                return txt
        except Exception:
            pass

        # 2) OCR de la franja superior
        try:
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            w, h = img.size
            crop = img.crop((0, 0, w, int(h * top_ratio)))
            return pytesseract.image_to_string(crop, lang=lang, config="--oem 3 --psm 6") or ""
        except Exception:
            return ""

    def clasificar_pagina(self, page) -> str:
        # 1) Encabezado primero
        head = self._texto_top(page, top_ratio=0.40, dpi=300, lang="eng")
        tipo = self._clasificar(head)
        if tipo != "Revision":
            return tipo

        # 2) Página completa si el encabezado no alcanza:
        # usa texto embebido; si no hay, OCR de toda la página
        full = (page.get_text("text") or "").strip()
        if not full:
            full = self._texto_pagina(page, dpi=300, lang="eng")
        return self._clasificar(full)

    # ---------- extractores ----------
    def extraer_vin(self, t: str) -> str:
        t2 = t.upper()
        m = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", t2)
        return m.group(1) if m else ""

    def extraer_placa(self, t: str) -> str:
        t2 = t.upper().replace(" ", "")
        m = re.search(r"\b([A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z]|[A-Z]{3}\d[A-Z]\d)\b", t2)
        return m.group(1) if m else ""

    # ---------- clasificación ----------
    def _clasificar(self, texto: str) -> str:
        t = self._norm(texto)
        t = t.replace("0", "o").replace("1", "i").replace("5", "s")

        # FACTURA
        if re.search(r"\bfactura\W{0,40}electronica\W{0,40}de\W{0,40}venta\b", t):
            return "Factura"
        if re.search(r"\bfactura\W{0,40}de\W{0,40}venta\b", t):
            return "Factura"

        # ORDEN (más estricto: cercanía real, sin el 'if "orden" in t and "servicio" in t')
        if re.search(r"\borden\W{0,40}de\W{0,40}servicio\b", t):
            return "Orden"
        if re.search(r"\borden\b.{0,60}\bservicio\b", t, flags=re.DOTALL):
            return "Orden"

        return "Revision"

    # ---------- IO ----------
    def save_single_page_pdf(self, src_path: str, page_idx: int, dst_path: str):
        with fitz.open(src_path) as doc:
            if page_idx < 0 or page_idx >= len(doc):
                raise ValueError(f"page_idx fuera de rango: {page_idx} (len={len(doc)})")
            out = fitz.open()
            out.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            out.save(dst_path, deflate=True)
            out.close()

    # ---------- API que usa la UI ----------
    def leer_texto_pdf(self, ruta: str, modo: str = "separados", lang: str = "eng+spa") -> str:
        if modo.startswith("separados"):
            t0 = leer_primera_pagina(ruta, lang=lang)
            return (t0 or "").strip()
        textos, _ = leer_pdf_con_ocr(ruta, lang=lang)
        return "\n\n".join(textos).strip()

    def analizar_contar(self, rutas: List[str], modo: str = "separados") -> Tuple[int, int, int, int, List[str]]:
        c_fact = c_orden = c_rev = c_err = 0
        logs = []
        for i, ruta in enumerate(rutas, 1):
            nombre = os.path.basename(ruta)
            try:
                if modo.startswith("separados"):
                    # Solo 1ra página, sin OCR si hay texto embebido
                    t0 = leer_primera_pagina(ruta, lang="eng+spa")
                    if not t0:
                        c_rev += 1
                        logs.append(f"[{i:03d}] {nombre} -> Revision (sin texto)")
                        continue
                    tipo = self._clasificar_texto(t0)
                    if   tipo == "Factura": c_fact += 1
                    elif tipo == "Orden":   c_orden += 1
                    else:                   c_rev += 1
                    logs.append(f"[{i:03d}] {nombre} -> {tipo}")
                else:
                    # Todas las páginas
                    textos, _ = leer_pdf_con_ocr(ruta, lang="eng+spa")
                    if not textos:
                        c_rev += 1
                        logs.append(f"[{i:03d}] {nombre} -> Revision (sin texto)")
                        continue
                    for pidx, t in enumerate(textos, 1):
                        tipo = self._clasificar_texto(t)
                        if   tipo == "Factura": c_fact += 1
                        elif tipo == "Orden":   c_orden += 1
                        else:                   c_rev += 1
                        logs.append(f"[{i:03d}-{pidx:02d}] {nombre} (p.{pidx}) -> {tipo}")
            except Exception as e:
                c_err += 1
                logs.append(f"[{i:03d}] {nombre} -> ERROR: {e}")
        return c_fact, c_orden, c_rev, c_err, logs

    def analizar_contar_stream(self, rutas: List[str], modo: str = "separados"):
        # calcular total de items
        total_items = 0
        if modo.startswith("separados"):
            total_items = len(rutas)
        else:
            # estimación por páginas sin OCR
            for ruta in rutas:
                try:
                    with fitz.open(ruta) as d:
                        total_items += max(1, len(d))
                except Exception:
                    total_items += 1
        total_items = max(1, total_items)

        c_fact = c_orden = c_rev = c_err = 0
        done = 0

        if not rutas:
            yield {"msg": "[Info] No hay PDFs.", "progress": 1.0}
            yield ("__SUMMARY__", 0, 0, 0, 0)
            return

        for i, ruta in enumerate(rutas, 1):
            nombre = os.path.basename(ruta)
            try:
                if modo.startswith("separados"):
                    # Solo 1ra página
                    t0 = leer_primera_pagina(ruta, lang="eng+spa")
                    if not t0:
                        c_rev += 1
                        done += 1
                        yield {"msg": f"[{i:03d}] {nombre} -> Revision (sin texto)", "progress": done / total_items}
                        continue
                    tipo = self._clasificar_texto(t0)
                    if   tipo == "Factura": c_fact += 1
                    elif tipo == "Orden":   c_orden += 1
                    else:                   c_rev += 1
                    done += 1
                    yield {"msg": f"[{i:03d}] {nombre} -> {tipo}", "progress": done / total_items}
                else:
                    # Todas las páginas
                    textos, _ = leer_pdf_con_ocr(ruta, lang="eng+spa")
                    if not textos:
                        c_rev += 1
                        done += 1
                        yield {"msg": f"[{i:03d}] {nombre} -> Revision (sin texto)", "progress": done / total_items}
                        continue
                    for pidx, t in enumerate(textos, 1):
                        tipo = self._clasificar_texto(t)
                        if   tipo == "Factura": c_fact += 1
                        elif tipo == "Orden":   c_orden += 1
                        else:                   c_rev += 1
                        done += 1
                        yield {
                            "msg": f"[{i:03d}-{pidx:02d}] {nombre} (p.{pidx}) -> {tipo}",
                            "progress": done / total_items,
                        }

            except Exception as e:
                c_err += 1
                done += 1
                yield {"msg": f"[{i:03d}] {nombre} -> ERROR: {e}", "progress": done / total_items}

        yield {"msg": "Resumen listo.", "progress": 1.0}
        yield ("__SUMMARY__", c_fact, c_orden, c_rev, c_err)

    def _digits(self, s: str) -> str:
        return re.sub(r"\D", "", s or "")

    def _norm_orden(self, s: str) -> str:
        d = self._digits(s)
        d = re.sub(r"^0+", "", d)
        return d
    
    def _orden_core(self, s: str) -> str:
        """Devuelve el núcleo 40000 + 6 dígitos (11 dígitos) si existe."""
        d = self._digits(s)  # solo dígitos
        m = re.search(r'40000\d{6}', d)
        return m.group(0) if m else ""

    
    def _match_orden_relajado(self, a: str, b: str) -> bool:
        # 1) Intento principal: comparar el núcleo 40000 + 6 dígitos
        A = self._orden_core(a)
        B = self._orden_core(b)
        if A and B:
            return A == B

        # 2) Fallback: si alguno no tiene núcleo, usa tu normalización anterior
        A2, B2 = self._norm_orden(a), self._norm_orden(b)
        if not A2 or not B2:
            return False

        # tolerancias suaves (por si hay colas/recortes)
        if A2 == B2 or A2.endswith(B2) or B2.endswith(A2):
            return True

        # prefijo fuerte: si comparten prefijo largo (>=9) y las colas son cortas
        lcp = 0
        for ca, cb in zip(A2, B2):
            if ca == cb:
                lcp += 1
            else:
                break
        if lcp >= 9 and max(len(A2)-lcp, len(B2)-lcp) <= 2:
            return True

        return False
    
    def separar_y_renombrar(self, rutas: List[str], modo: str = "separados") -> List[str]:
        logs = [f"[Separar] Guardando en: {self.BASE_OUT}"]
        for ev in self.separar_y_renombrar_stream(rutas, modo):
            if isinstance(ev, dict):
                msg = ev.get("msg")
                if msg:
                    logs.append(msg)
            elif isinstance(ev, tuple) and ev and ev[0] == "__SUMMARY__":
                _, c_fact, c_orden, c_rev, c_err = ev
                logs.append("")
                logs.append("===== RESUMEN =====")
                label_pag = "" if modo.startswith("separados") else " (páginas)"
                logs.append(f"Facturas guardadas{label_pag}:        {c_fact}")
                logs.append(f"Órdenes guardadas{label_pag}:         {c_orden}")
                logs.append(f"Revisión{label_pag}: {c_rev}")
                logs.append(f"Errores:                              {c_err}")
        return logs

    
    def separar_y_renombrar_stream(self, rutas: List[str], modo: str = "separados"):
        if not rutas:
            yield {"msg": "[Separar] No hay PDFs.", "progress": 1.0}
            yield ("__SUMMARY__", 0, 0, 0, 0)
            return

        # --- Estimar trabajo total (páginas + guardados) ---
        total_pages = 0
        pages_per_file = []
        for ruta in rutas:
            try:
                with fitz.open(ruta) as doc:
                    n = len(doc) if not modo.startswith("separados") else 1
            except Exception:
                n = 1
            pages_per_file.append(n)
            total_pages += n

        est_saves = max(1, total_pages)
        total_work = total_pages + est_saves
        done = 0

        # --- Leer/OCR + clasificar ---
        docs = []
        revisiones = []
        for i, (ruta, n_pages) in enumerate(zip(rutas, pages_per_file), 1):
            nombre = os.path.basename(ruta)
            try:
                textos_ocr, _ = leer_pdf_con_ocr(ruta, lang="eng+spa")
                with fitz.open(ruta) as doc:
                    pages = range(len(doc)) if not modo.startswith("separados") else range(1)
                    for pidx in pages:
                        full = textos_ocr[pidx] if pidx < len(textos_ocr) else ""
                        tipo = self._clasificar_texto(full)
                        if tipo == "Factura":
                            docs.append({
                                "tipo": tipo,
                                "orden_taller": extraer_numero_orden(full),
                                "vin": self.extraer_vin(full),
                                "motor": "",
                                "placa": self.extraer_placa(full),
                                "src": ruta,
                                "pidx": pidx,
                                "nombre": nombre
                            })
                        elif tipo == "Orden":
                            docs.append({
                                "tipo": tipo,
                                "orden_taller": extraer_numero_orden(full),
                                "chasis": extraer_chasis_orden(full),
                                "motor": extraer_motor_orden(full),
                                "placa": extraer_placa_orden(full),
                                "src": ruta,
                                "pidx": pidx,
                                "nombre": nombre
                            })
                        else:
                            revisiones.append({
                                "tipo": "Revision",
                                "src": ruta,
                                "pidx": pidx,
                                "nombre": nombre
                            })
                        done += 1
                        yield {"msg": f"[{i:03d}-{pidx+1:02d}] {nombre} clasificada: {tipo}",
                            "progress": min(0.999, done/total_work)}
            except Exception as e:
                done += n_pages
                yield {"msg": f"[{i:03d}] ERROR leyendo {nombre}: {e}",
                    "progress": min(0.999, done/total_work)}
            else:
                yield {"msg": "", "progress": min(0.999, done/total_work)}

        # ====== SEGUNDO INTENTO (DPI 200) SOLO PARA REVISION ======
        if revisiones:
            nuevas_docs = []
            for r in list(revisiones):
                try:
                    textos_retry = leer_pdf_aumentado(r["src"], lang="eng+spa", dpi_retry=200)
                    full = textos_retry[r["pidx"]] if r["pidx"] < len(textos_retry) else ""
                    tipo2 = self._clasificar_texto(full)

                    if tipo2 in ("Factura", "Orden"):
                        if tipo2 == "Factura":
                            nuevas_docs.append({
                                "tipo": "Factura",
                                "orden_taller": extraer_numero_orden(full),
                                "vin": self.extraer_vin(full),
                                "motor": "",
                                "placa": self.extraer_placa(full),
                                "src": r["src"],
                                "pidx": r["pidx"],
                                "nombre": r["nombre"]
                            })
                        else:
                            nuevas_docs.append({
                                "tipo": "Orden",
                                "orden_taller": extraer_numero_orden(full),
                                "chasis": extraer_chasis_orden(full),
                                "motor": extraer_motor_orden(full),
                                "placa": extraer_placa_orden(full),
                                "src": r["src"],
                                "pidx": r["pidx"],
                                "nombre": r["nombre"]
                            })
                        revisiones.remove(r)
                        yield {"msg": f"[2do intento] {r['nombre']} reclasificada como {tipo2}",
                            "progress": min(0.999, done/total_work)}
                except Exception:
                    pass

            docs.extend(nuevas_docs)
        # ====== EMPAREJAR FACTURAS Y ÓRDENES ======
        facturas = [d for d in docs if d["tipo"] == "Factura"]
        ordenes  = [d for d in docs if d["tipo"] == "Orden"]
        pairs, orf_fact, orf_ord = [], [], []
        usados_fact, usados_ord = set(), set()

        def vin_ok(s: str) -> str:
            s = (s or "").strip().upper()
            return s if len(s) == 17 else ""

        def placa_ok(s: str) -> str:
            return (s or "").strip().upper()

        for o in ordenes:
            if id(o) in usados_ord:
                continue

            co_core = self._orden_core(o.get("orden_taller"))
            o_raw   = o.get("orden_taller") or ""
            o_vin   = vin_ok(o.get("chasis") or o.get("vin")) 
            o_placa = placa_ok(o.get("placa"))

            match = None

            # 1) Núcleo fuerte (exacto)
            if co_core:
                for f in facturas:
                    if id(f) in usados_fact: 
                        continue
                    cf_core = self._orden_core(f.get("orden_taller"))
                    if cf_core and cf_core == co_core:
                        match = f
                        break

            # 2) Match relajado del número de orden 
            if not match:
                for f in facturas:
                    if id(f) in usados_fact:
                        continue
                    if self._match_orden_relajado(f.get("orden_taller") or "", o_raw):
                        match = f
                        break

            # 3) VIN exacto (17 chars)
            if not match and o_vin:
                for f in facturas:
                    if id(f) in usados_fact:
                        continue
                    f_vin = vin_ok(f.get("vin"))
                    if f_vin and f_vin == o_vin:
                        match = f
                        break

            # 4) Placa exacta
            if not match and o_placa:
                for f in facturas:
                    if id(f) in usados_fact:
                        continue
                    f_placa = placa_ok(f.get("placa"))
                    if f_placa and f_placa == o_placa:
                        match = f
                        break

            if match:
                pairs.append((match, o))
                usados_fact.add(id(match))
                usados_ord.add(id(o))
            else:
                orf_ord.append(o)

        for f in facturas:
            if id(f) not in usados_fact:
                orf_fact.append(f)

        # Ajustar total con guardados reales
        real_saves = len(pairs)*2 + len(orf_fact) + len(orf_ord) + len(revisiones)
        total_work = max(done + real_saves, done + 1)

        os.makedirs(self.DIR_FACTURAS, exist_ok=True)
        os.makedirs(self.DIR_ORDENES,  exist_ok=True)

        # --- Guardar resultados ---
        c_fact = c_orden = c_err = 0
        c_rev  = 0 
        c_sinpar = 0   
        k = 1

        # ====== SEGUNDO INTENTO (DPI 200) SOLO PARA SINPAR ======
        if orf_fact or orf_ord:
            def _refresca_campos(doc_item, es_factura=True):
                try:
                    textos_retry = leer_pdf_aumentado(doc_item["src"], lang="eng+spa", dpi_retry=200)
                    full = textos_retry[doc_item["pidx"]] if doc_item["pidx"] < len(textos_retry) else ""
                    if es_factura:
                        doc_item["orden_taller"] = extraer_numero_orden(full) or doc_item.get("orden_taller", "")
                        doc_item["vin"]          = self.extraer_vin(full)     or doc_item.get("vin", "")
                        doc_item["placa"]        = self.extraer_placa(full)   or doc_item.get("placa", "")
                    else:
                        doc_item["orden_taller"] = extraer_numero_orden(full)     or doc_item.get("orden_taller", "")
                        doc_item["chasis"]       = extraer_chasis_orden(full)     or doc_item.get("chasis", "")
                        doc_item["motor"]        = extraer_motor_orden(full)      or doc_item.get("motor", "")
                        doc_item["placa"]        = extraer_placa_orden(full)      or doc_item.get("placa", "")
                except Exception:
                    pass

            # refresca campos con mejor DPI
            for f in orf_fact:
                _refresca_campos(f, es_factura=True)
            for o in orf_ord:
                _refresca_campos(o, es_factura=False)

            # reintenta emparejar SOLO entre los huérfanos
            nuevos_pairs = []
            usados_fact_retry, usados_ord_retry = set(), set()
            for o in orf_ord:
                if id(o) in usados_ord_retry:
                    continue

                co_core = self._orden_core(o.get("orden_taller"))
                o_raw   = o.get("orden_taller") or ""
                o_vin   = (o.get("chasis") or o.get("vin") or "").strip().upper()
                o_vin   = o_vin if len(o_vin) == 17 else ""
                o_placa = (o.get("placa") or "").strip().upper()

                match = None
                # 1) núcleo exacto
                if co_core:
                    for f in orf_fact:
                        if id(f) in usados_fact_retry: continue
                        cf_core = self._orden_core(f.get("orden_taller"))
                        if cf_core and cf_core == co_core:
                            match = f; break
                # 2) orden relajado
                if not match:
                    for f in orf_fact:
                        if id(f) in usados_fact_retry: continue
                        if self._match_orden_relajado(f.get("orden_taller") or "", o_raw):
                            match = f; break
                # 3) vin
                if not match and o_vin:
                    for f in orf_fact:
                        if id(f) in usados_fact_retry: continue
                        f_vin = (f.get("vin") or "").strip().upper()
                        f_vin = f_vin if len(f_vin) == 17 else ""
                        if f_vin and f_vin == o_vin:
                            match = f; break
                # 4) placa
                if not match and o_placa:
                    for f in orf_fact:
                        if id(f) in usados_fact_retry: continue
                        f_placa = (f.get("placa") or "").strip().upper()
                        if f_placa and f_placa == o_placa:
                            match = f; break

                if match:
                    nuevos_pairs.append((match, o))
                    usados_fact_retry.add(id(match))
                    usados_ord_retry.add(id(o))

            if nuevos_pairs:
                pairs.extend(nuevos_pairs)
                orf_fact = [f for f in orf_fact if id(f) not in usados_fact_retry]
                orf_ord  = [o for o in orf_ord  if id(o) not in usados_ord_retry]
                yield {"msg": f"[2do intento] Emparejadas {len(nuevos_pairs)} parejas adicionales.",
                    "progress": min(0.999, done/total_work)}

        # (RE)calcula trabajo real tras el retry (porque cambiaron las cuentas):
        real_saves = len(pairs)*2 + len(orf_fact) + len(orf_ord) + len(revisiones)
        total_work = max(done + real_saves, done + 1)
        for fact, ordn in pairs:
            raw_num = (ordn.get("orden_taller") or fact.get("orden_taller") or "")
            core_num = self._orden_core(raw_num) or self._norm_orden(raw_num) or "SINORDEN"
            num_safe = self._safe_token(core_num)

            fact_out = os.path.join(self.DIR_FACTURAS, f"{k}_Factura_{num_safe}.pdf")
            ord_out  = os.path.join(self.DIR_ORDENES,  f"{k}_Orden_{num_safe}.pdf")

            # Guardar ambos y emitir UNA sola línea
            fact_ok = ord_ok = False
            err_msgs = []

            try:
                self.save_single_page_pdf(fact["src"], fact["pidx"], fact_out)
                c_fact += 1
                fact_ok = True
            except Exception as e:
                c_err += 1
                err_msgs.append(f"ERROR factura: {e}")

            try:
                self.save_single_page_pdf(ordn["src"], ordn["pidx"], ord_out)
                c_orden += 1
                ord_ok = True
            except Exception as e:
                c_err += 1
                err_msgs.append(f"ERROR orden: {e}")

            done += (1 if fact_ok or not err_msgs else 0) + (1 if ord_ok or (len(err_msgs) > (1 if not fact_ok else 0)) else 0)

            if fact_ok and ord_ok:
                msg = f"[{k}] {os.path.basename(fact_out)} ↔ {os.path.basename(ord_out)}"
            else:
                # Un solo mensaje también en caso de error, con detalles
                base = f"[{k}] {os.path.basename(fact_out)} ↔ {os.path.basename(ord_out)}"
                msg = f"{base} | " + " | ".join(err_msgs)

            yield {"msg": msg, "progress": min(0.999, done/total_work)}
            k += 1


        for f in orf_fact:
            try:
                ref = self._orden_core(f.get("orden_taller")) or self._norm_orden(f.get("orden_taller")) or f.get("vin") or f.get("placa") or "SINREF"
                out = os.path.join(self.DIR_SINPAR, f"{k}_Factura_{self._safe_token(ref)}_SINPAR.pdf")
                self.save_single_page_pdf(f["src"], f["pidx"], out)
                c_sinpar += 1
                done += 1
                yield {"msg": f"[{k}] guardada {os.path.basename(out)}",
                    "progress": min(0.999, done/total_work)}
                k += 1
            except Exception as e:
                c_err += 1
                yield {"msg": f"[{k}] ERROR guardando factura huérfana: {e}",
                    "progress": min(0.999, done/total_work)}

        for o in orf_ord:
            try:
                ref = self._orden_core(o.get("orden_taller")) or self._norm_orden(o.get("orden_taller")) or o.get("chasis") or o.get("placa") or "SINREF"
                out = os.path.join(self.DIR_SINPAR, f"{k}_Orden_{self._safe_token(ref)}_SINPAR.pdf")
                self.save_single_page_pdf(o["src"], o["pidx"], out)
                c_sinpar += 1
                done += 1
                yield {"msg": f"[{k}] guardada {os.path.basename(out)}",
                    "progress": min(0.999, done/total_work)}
                k += 1
            except Exception as e:
                c_err += 1
                yield {"msg": f"[{k}] ERROR guardando orden huérfana: {e}",
                    "progress": min(0.999, done/total_work)}
        
        # --- Guardar REVISION ---
        for r in revisiones:
            try:
                base = os.path.splitext(r["nombre"])[0]
                ref  = self._safe_token(base) 
                out  = os.path.join(self.DIR_REVISION, f"{k}_Revision_{ref}.pdf")
                self.save_single_page_pdf(r["src"], r["pidx"], out)
                c_rev += 1
                done  += 1
                yield {"msg": f"[{k}] guardada {os.path.basename(out)}",
                    "progress": min(0.999, done/total_work)}
                k += 1
            except Exception as e:
                c_err += 1
                yield {"msg": f"[{k}] ERROR guardando revisión: {e}",
                    "progress": min(0.999, done/total_work)}

        yield {"msg": f"SinPar guardados: {c_sinpar}", "progress": min(0.999, done/total_work)}  
        yield {"msg": "Resumen listo.", "progress": 1.0}
        yield ("__SUMMARY__", c_fact, c_orden, c_rev, c_err)
