import pandas as pd

# Cargar una sola vez el Excel (mejor para rendimiento)
df_excel = pd.read_excel("referencias.xlsx", usecols=["Referencia", "Desc. item"])
df_excel["Referencia"] = df_excel["Referencia"].astype(str).str.upper().str.replace(" ", "")

def buscar_referencias_en_texto(texto_ocr):
    texto_limpio = texto_ocr.upper().replace(" ", "")
    resultados = []

    for _, fila in df_excel.iterrows():
        ref = fila["Referencia"]
        if ref in texto_limpio:
            resultados.append({
                "Referencia": ref,
                "Descripcion": fila["Desc. item"]
            })

    # Si no encuentra nada, pero hay algo que empieza con YUASA, intentamos solo esas
    if not resultados and "YUASA-" in texto_limpio:
        for ref in df_excel["Referencia"]:
            if ref.startswith("YUASA-") and ref[:10] in texto_limpio:
                desc = df_excel[df_excel["Referencia"] == ref]["Desc. item"].values[0]
                resultados.append({
                    "Referencia": ref,
                    "Descripcion": desc
                })
    return resultados if resultados else None
