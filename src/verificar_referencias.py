"""
Verifica la consistencia interna de las tablas de referencia.

Se corre después de editar cualquier archivo de reference/.
Falla con mensaje claro si algo no cuadra, antes de que el problema llegue
al validador o al modelo.

Uso:
    python src/verificar_referencias.py
"""

from pathlib import Path
import sys

import pandas as pd

REF = Path(__file__).resolve().parents[1] / "reference"

ZONAS = {"GAM_CENTRO", "GAM_PERIFERIA", "CIUDAD_INTERMEDIA", "RURAL", "COSTA"}
MONEDAS = {"CRC", "USD"}
ACCIONES = {"BLOQUEA", "REVISA"}

# Rango nacional aproximado (WGS84). Excluye Isla del Coco.
LAT_MIN, LAT_MAX = 8.0, 11.3
LON_MIN, LON_MAX = -86.0, -82.5


def leer(nombre: str) -> pd.DataFrame:
    ruta = REF / nombre
    if not ruta.exists():
        raise FileNotFoundError(f"Falta {ruta}")
    return pd.read_csv(ruta, encoding="utf-8")


def verificar() -> list[str]:
    errores: list[str] = []

    geo = leer("geografia.csv")
    tip = leer("tipologias.csv")
    vu = leer("rangos_vu.csv")
    per = leer("peritos.csv")
    reg = leer("reglas_datos.csv")

    # --- geografia ---------------------------------------------------------
    clave = ["provincia", "canton", "distrito"]
    if geo.duplicated(clave).any():
        errores.append("geografia: terna provincia-canton-distrito duplicada")
    if not set(geo["zona"]).issubset(ZONAS):
        errores.append(f"geografia: zonas fuera de catálogo -> {set(geo['zona']) - ZONAS}")
    fuera = geo[~geo["lat_centroide"].between(LAT_MIN, LAT_MAX) | ~geo["lon_centroide"].between(LON_MIN, LON_MAX)]
    if not fuera.empty:
        errores.append(f"geografia: {len(fuera)} centroides fuera del rango nacional -> {fuera['distrito'].tolist()}")
    if (geo["radio_km"] <= 0).any():
        errores.append("geografia: radio_km debe ser positivo")
    sin_verificar = (geo["verificado"] == "NO").sum()

    # --- tipologias --------------------------------------------------------
    if tip["tipologia"].duplicated().any():
        errores.append("tipologias: tipología duplicada")
    if not set(tip["requiere_construccion"]).issubset({"SI", "NO", "OPCIONAL"}):
        errores.append("tipologias: requiere_construccion fuera de {SI, NO, OPCIONAL}")
    if (tip["cobertura_min"] > tip["cobertura_max"]).any():
        errores.append("tipologias: cobertura_min mayor que cobertura_max")

    # --- rangos_vu ---------------------------------------------------------
    if vu.duplicated(["zona", "tipologia", "moneda"]).any():
        errores.append("rangos_vu: combinación zona-tipologia-moneda duplicada")
    if not set(vu["zona"]).issubset(ZONAS):
        errores.append("rangos_vu: zona fuera de catálogo")
    if not set(vu["moneda"]).issubset(MONEDAS):
        errores.append("rangos_vu: moneda fuera de {CRC, USD}")
    tip_desconocidas = set(vu["tipologia"]) - set(tip["tipologia"])
    if tip_desconocidas:
        errores.append(f"rangos_vu: tipologías inexistentes en tipologias.csv -> {tip_desconocidas}")
    completos = vu.dropna(subset=["vu_min", "vu_max"])
    if (completos["vu_min"] >= completos["vu_max"]).any():
        errores.append("rangos_vu: vu_min debe ser menor que vu_max")
    sin_rango = vu["vu_min"].isna().sum()

    # --- peritos -----------------------------------------------------------
    if per["perito_id"].duplicated().any():
        errores.append("peritos: perito_id duplicado")
    if not per["perito_id"].str.match(r"^PER-\d{3}$").all():
        errores.append("peritos: formato de perito_id inválido (esperado PER-NNN)")

    # --- reglas ------------------------------------------------------------
    if reg["rule_id"].duplicated().any():
        errores.append("reglas: rule_id duplicado")
    if not set(reg["accion"]).issubset(ACCIONES):
        errores.append(f"reglas: acción fuera de {ACCIONES}")
    inactivas_sin_motivo = reg[(reg["activa"] == "NO") & reg["motivo_inactiva"].isna()]
    if not inactivas_sin_motivo.empty:
        errores.append(f"reglas: inactivas sin motivo -> {inactivas_sin_motivo['rule_id'].tolist()}")
    activas = (reg["activa"] == "SI").sum()

    # --- resumen -----------------------------------------------------------
    print(f"geografia    : {len(geo)} distritos, {geo['zona'].nunique()} zonas, {sin_verificar} sin verificar")
    print(f"tipologias   : {len(tip)} tipologías")
    print(f"rangos_vu    : {len(vu)} combinaciones, {sin_rango} sin valores todavía")
    print(f"peritos      : {len(per)} peritos, {(per['activo'] == 'SI').sum()} activos")
    print(f"reglas       : {len(reg)} reglas, {activas} activas")

    if sin_verificar:
        print(f"\nAVISO: {sin_verificar} distritos con verificado=NO. Revisar centroides antes de publicar.")
    if sin_rango:
        print(f"AVISO: {sin_rango} combinaciones de rangos_vu sin valores. R-07 devolverá NO_APLICA para ellas.")

    return errores


if __name__ == "__main__":
    errs = verificar()
    if errs:
        print("\nERRORES:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    print("\nTablas de referencia consistentes.")
