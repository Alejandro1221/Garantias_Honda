def _ocr_desde_pdf(ruta_pdf: str, pagina_index: int, dpi: int = 700, lang: str = "eng+spa") -> str:
    with fitz.open(ruta_pdf) as doc:
        if not (0 <= pagina_index < len(doc)):
            return ""
        pagina = doc[pagina_index]
        pix = pagina.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    tess_cfg = r'--oem 1 --psm 6 -c tessedit_char_whitelist=ABCDEFGHJKLMNPRSTUVWXYZ0123456789'
    return pytesseract.image_to_string(img, lang=lang, config=tess_cfg)