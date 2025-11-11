# distribuidores.py
from __future__ import annotations
import os
from typing import Optional, Dict, List, Tuple
import pandas as pd

# --- Definición de columnas ---
BASE_COLUMNS = [
    "NIT", "RAZON SOCIAL", "AGENCIA", "RED", "CIUDAD", "DEPARTAMENTO", "CORREOS"
]

# Tus columnas nuevas (EDITABLES en la UI)
EXTRA_COLUMNS = [
    "FACTURA_LEGIBLE",
    "ORDEN_FANALCA",
    "ORDEN_LEGIBLE",
    "TEXTO_MANUAL",
    "FOTO", 
    "OBSERVACIONES",
    "QR",
]

OPTIONAL_EXTRAS = {"FOTO"} 

# Todas las columnas que se persistirán en el Excel
COLUMNS = BASE_COLUMNS + EXTRA_COLUMNS

# Columnas que la UI debe mostrar (solo lectura las base, editables las extra)
VISIBLE_COLUMNS = ["NIT", "RAZON SOCIAL", "AGENCIA"] + EXTRA_COLUMNS


class DistribuidoresRepo:
    """
    CRUD sobre Excel de distribuidores (pandas + openpyxl).
    - Mantiene NIT como string
    - Crea columnas nuevas si no existen
    - Expone 'VISIBLE_COLUMNS' para que la UI muestre solo lo necesario
    """

    def __init__(self, path: str = "Distribuidores.xlsx", sheet_name: str = "Hoja1"):
        self.path = path
        self.sheet = sheet_name
        self.df = pd.DataFrame(columns=COLUMNS)
        self.load_or_init()

    # ---------- carga / guardado ----------
    def load_or_init(self):
        if os.path.exists(self.path):
            self.df = pd.read_excel(
                self.path, sheet_name=self.sheet, dtype={"NIT": str}, engine="openpyxl"
            )
            self._ensure_columns()
            self.df["NIT"] = self.df["NIT"].astype(str).str.strip()
        else:
            # crear archivo vacío con el esquema completo (incluye tus nuevas)
            self.save()

    def save(self, to_path: Optional[str] = None):
        out = to_path or self.path
        df = self.df.reindex(columns=COLUMNS)
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=self.sheet, index=False)

    # ---------- importar / exportar ----------
    def import_from_excel(
        self,
        src_path: str,
        sheet_name: Optional[str] = None,
        *,
        mode: str = "upsert",                # "replace" | "upsert"
        keep_repo_path: bool = True,         # True = NO cambiar self.path
        columns_map: Optional[Dict[str, str]] = None,
    ):
        """
        Importa desde otro Excel grande.
        - Lee SOLO columnas base (por nombre o usando 'columns_map').
        - No exige que existan las columnas nuevas en la fuente.
        - 'mode' = 'replace' reemplaza todo; 'upsert' actualiza/añade por NIT.
        - 'keep_repo_path' True: no cambia el archivo base del repo.
        """
        sheet = sheet_name or self.sheet

        # 1) columnas a leer en fuente y renombre -> destino (BASE_COLUMNS)
        if columns_map:
            usecols_src = list(columns_map.keys())
            rename_map = columns_map
        else:
            usecols_src = BASE_COLUMNS
            rename_map = {c: c for c in BASE_COLUMNS}

        src = pd.read_excel(
            src_path,
            sheet_name=sheet,
            dtype={"NIT": str},
            engine="openpyxl",
            usecols=usecols_src,
        ).rename(columns=rename_map)

        # 2) asegurar base y normalizar
        for c in BASE_COLUMNS:
            if c not in src.columns:
                src[c] = ""
        src = src[BASE_COLUMNS].copy()
        src["NIT"] = src["NIT"].astype(str).str.strip()

        # 3) añadir columnas nuevas (vacías si no existen en el import)
        for c in EXTRA_COLUMNS:
            if c not in src.columns:
                src[c] = ""

        # 4) aplicar modo
        if mode == "replace":
            self.df = src[COLUMNS].copy()
        elif mode == "upsert":
            if self.df.empty:
                self.df = pd.DataFrame(columns=COLUMNS)
            self._ensure_columns()

            cur = self.df.set_index("NIT")
            incoming = src.set_index("NIT")

            common = incoming.index.intersection(cur.index)
            cur.loc[common, COLUMNS] = incoming.loc[common, COLUMNS]

            new = incoming.index.difference(cur.index)
            cur = pd.concat([cur, incoming.loc[new, COLUMNS]], axis=0)

            self.df = cur.reset_index()
        else:
            raise ValueError("mode debe ser 'replace' o 'upsert'")

        self._ensure_columns()
        self.df["NIT"] = self.df["NIT"].astype(str).str.strip()

        if not keep_repo_path:
            self.path = src_path
            self.sheet = sheet

    def export_to_excel(self, dst_path: str, sheet_name: Optional[str] = None, *, only_visible: bool = False):
        """Exporta el dataset actual. Si only_visible=True exporta solo lo visible en la UI."""
        sheet = sheet_name or self.sheet
        cols = VISIBLE_COLUMNS if only_visible else COLUMNS
        with pd.ExcelWriter(dst_path, engine="openpyxl") as writer:
            self.df.reindex(columns=cols).to_excel(writer, sheet_name=sheet, index=False)

    # ---------- CRUD ----------
    def list_all(self) -> pd.DataFrame:
        return self.df.copy()

    def list_visible(self) -> pd.DataFrame:
        """Lo que usará la UI para mostrar en la tabla."""
        self._ensure_columns()
        return self.df[VISIBLE_COLUMNS].copy()

    def exists_nit(self, nit: str) -> bool:
        nit = str(nit).strip()
        return any(self.df["NIT"].astype(str).str.strip() == nit)

    def get_by_nit(self, nit: str) -> Optional[Dict]:
        nit = str(nit).strip()
        rows = self.df[self.df["NIT"].astype(str).str.strip() == nit]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def upsert(self, data: Dict[str, str]):
        self._ensure_columns()
        if "NIT" not in data or not str(data["NIT"]).strip():
            raise ValueError("NIT es obligatorio para upsert.")
        nit = str(data["NIT"]).strip()

        # Normalizar SI/NO en columnas booleanas
        bool_cols = {"FACTURA_LEGIBLE", "ORDEN_FANALCA", "ORDEN_LEGIBLE", "TEXTO_MANUAL", "QR"}
        norm = {}
        for c in COLUMNS:
            v = data.get(c, "")
            if pd.isna(v):
                v = ""
            v = str(v).strip()
            if c in bool_cols:
                v = v.upper()
                v = v if v in ("", "SI", "NO") else ""
            norm[c] = v
        norm["NIT"] = nit  # asegurar

        mask = self.df["NIT"].astype(str).str.strip() == nit
        if mask.any():
            # --- UPDATE ---
            idx = self.df.index[mask][0]
            for k, v in norm.items():
                self.df.at[idx, k] = v
            # mover fila actualizada al tope
            top = self.df.loc[[idx]]
            rest = self.df.drop(index=idx)
            self.df = pd.concat([top, rest], ignore_index=True)
        else:
            # --- INSERT ---
            self.df.loc[len(self.df)] = [norm.get(c, "") for c in COLUMNS]
            new_idx = self.df.index[-1]
            # mover la nueva fila al tope
            top = self.df.loc[[new_idx]]
            rest = self.df.drop(index=new_idx)
            self.df = pd.concat([top, rest], ignore_index=True)

    def delete(self, nit: str) -> bool:
        nit = str(nit).strip()
        before = len(self.df)
        self.df = self.df[self.df["NIT"].astype(str).str.strip() != nit].reset_index(drop=True)
        return len(self.df) < before

    # ---------- métricas de completitud ----------
    def completion_stats(self):
        if self.df.empty:
            return (0, 0, 0.0)

        # Normaliza a string y recorta
        df_extras = self.df[EXTRA_COLUMNS].astype(str).apply(lambda s: s.str.strip())
        # columnas requeridas = EXTRA - opcionales
        required = [c for c in EXTRA_COLUMNS if c not in OPTIONAL_EXTRAS]

        if required:
            row_ok = df_extras[required].ne("").all(axis=1)
        else:
            # si no hay requeridas, todo cuenta como completo
            row_ok = pd.Series([True] * len(self.df), index=self.df.index)

        done = int(row_ok.sum())
        total = int(len(self.df))
        pct = (done / total * 100.0) if total else 0.0
        return (done, total, pct)


    # ---------- util ----------
    def _ensure_columns(self):
        for c in COLUMNS:
            if c not in self.df.columns:
                self.df[c] = ""
            # cast a str y limpiar 'nan'
            self.df[c] = self.df[c].astype(str).replace({"nan": ""}).str.strip()
        self.df = self.df.reindex(columns=COLUMNS)


