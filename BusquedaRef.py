import pandas as pd

# Cargar una sola vez el Excel (mejor para rendimiento)
df_excel = pd.read_excel(
    "referencias.xlsx",
    usecols=["Referencia", "Desc. item"],
    dtype=str,
    engine="openpyxl"
).fillna("")

df_excel["Referencia"] = (
    df_excel["Referencia"]
    .astype(str)
    .str.upper()
    .str.replace(" ", "", regex=False)
)

DESC_POR_REF = dict(zip(df_excel["Referencia"], df_excel["Desc. item"]))

def buscar_referencias_en_texto(texto_ocr):
    if not texto_ocr:
        return None

    texto_limpio = str(texto_ocr).upper().replace(" ", "")
    resultados = []

    for ref, desc in DESC_POR_REF.items():
        if ref and ref in texto_limpio:
            resultados.append({"Referencia": ref, "Descripcion": desc})

    if not resultados and "YUASA-" in texto_limpio:
        for ref, desc in DESC_POR_REF.items():
            if ref.startswith("YUASA-") and ref[:10] in texto_limpio:
                resultados.append({"Referencia": ref, "Descripcion": desc})

    return resultados or None
