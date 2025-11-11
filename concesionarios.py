import pandas as pd
import os,glob
from datetime import datetime


TABLAS_DIR = os.path.join(os.getcwd(), "Tablas")
CARGAR_TABLA = os.path.join(TABLAS_DIR, "tabla_concesionarios.xlsx")


_tabla_concesionarios = None

def cargar_excel(path: str):
    global _tabla_concesionarios
    _tabla_concesionarios = pd.read_excel(path)
    return _tabla_concesionarios

def get_tabla():
    return _tabla_concesionarios

def transformar_tabla():
    global _tabla_concesionarios
    if _tabla_concesionarios is None:
        return None
    df = _tabla_concesionarios.copy()
    df = df[df["RED"].astype(str).str.upper().isin(["GSM","DISTRIBUIDOR"])]
    nit_digits = df["NIT"].astype(str).str.replace(r"\D","", regex=True)
    df = df[nit_digits.str.len() >= 2]
    df = df[["NIT","Rozón Social","AGENCIA","RED","REGIONAL"]].reset_index(drop=True)
    _tabla_concesionarios = df
    return _tabla_concesionarios


def guardar_en_tablas(nombre_base="tabla_concesionarios"):
    global _tabla_concesionarios
    if _tabla_concesionarios is None:
        return None
    os.makedirs(TABLAS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(TABLAS_DIR, f"{nombre_base}_{ts}.xlsx")
    _tabla_concesionarios.to_excel(path, index=False)
    return path

def cargar_guardada():
    global _tabla_concesionarios
    if os.path.exists(CARGAR_TABLA):
        _tabla_concesionarios = pd.read_excel(CARGAR_TABLA)
        return _tabla_concesionarios
    os.makedirs(TABLAS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(TABLAS_DIR, "tabla_concesionarios_*.xlsx")), reverse=True)
    if files:
        _tabla_concesionarios = pd.read_excel(files[0])
        return _tabla_concesionarios
    return None

def guardar_en_tablas():
    global _tabla_concesionarios
    if _tabla_concesionarios is None:
        return None
    os.makedirs(TABLAS_DIR, exist_ok=True)
    _tabla_concesionarios.to_excel(CARGAR_TABLA, index=False)
    return CARGAR_TABLA

def path_guardado():
    return CARGAR_TABLA