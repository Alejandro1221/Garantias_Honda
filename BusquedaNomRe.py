import pandas as pd
import sys

FILE = "REF-PRINC.xlsx"  

try:
    df = pd.read_excel(FILE, dtype=str, engine="openpyxl").fillna("")
except Exception as e:
    print(f"ERROR leyendo {FILE}: {e}")
    sys.exit(1)

# --- Normaliza y deja solo la columna REF ---
print("Columnas encontradas:", list(df.columns))
cols_map = {c.strip().lower(): c for c in df.columns}
ref_col = cols_map.get("ref") or cols_map.get("referencia")
if not ref_col:
    print("ERROR: no encuentro columna 'REF' (o 'Referencia').")
    sys.exit(1)

df = df[[ref_col]].astype(str).fillna("")
df.columns = ["REF"]
df["REF"] = df["REF"].str.strip().str.upper()

print(f"OK: {len(df)} filas cargadas.")

# --- Búsqueda en consola SOLO por ceros a la izquierda ---
while True:
    s = input("\nEscribe la referencia (ENTER para salir): ").strip().upper()
    if not s:
        break

    # si viene algo como '06121-XXX', toma solo lo antes del primer guion
    pref = s.split("-", 1)[0]

    # normalización SOLO: quitar ceros a la izquierda
    key = pref.lstrip("0")

    # compara contra REF del Excel también sin ceros a la izquierda
    matches = df[df["REF"].str.lstrip("0") == key]