"""
construir_almacen.py — Ejecuta el SQL en DuckDB y exporta los marts.

Corre los cinco archivos de sql/ en orden sobre una base DuckDB, verifica la
reconciliación y exporta cada mart a CSV para que Power BI los consuma sin
necesidad de conector.

Uso
---
    python src/construir_almacen.py

Salidas
-------
warehouse/garantias.duckdb   la base completa: staging, dimensiones, hechos, marts
data/marts/*.csv             un archivo por mart, para Power BI
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
SQL = RAIZ / "sql"
BASE = RAIZ / "warehouse" / "garantias.duckdb"
MARTS = RAIZ / "data" / "marts"

ARCHIVOS = ["01_staging.sql", "02_dimensiones.sql", "03_hechos.sql",
            "04_marts.sql", "05_control.sql"]


def ejecutar(con, archivo: Path) -> int:
    """Ejecuta un archivo .sql sentencia por sentencia y devuelve cuántas corrió.

    Se usa el parser de DuckDB en vez de partir el texto por ';'. Un punto y coma
    dentro de un comentario o de una cadena partiría mal el archivo.
    """
    texto = archivo.read_text(encoding="utf-8").replace("@RAIZ@", RAIZ.as_posix())
    sentencias = duckdb.extract_statements(texto)
    for i, sentencia in enumerate(sentencias, 1):
        try:
            con.execute(sentencia.query)
        except Exception as e:
            encabezado = " ".join(sentencia.query.split())[:90]
            sys.exit(f"\nError en {archivo.name}, sentencia {i}:\n  {encabezado}\n  {e}")
    return len(sentencias)


def main():
    faltan = [f for f in ("data/output/avaluos_validados.csv", "data/output/incidencias.csv",
                          "data/raw/creditos.csv", "reference/parametros.csv")
              if not (RAIZ / f).exists()]
    if faltan:
        sys.exit(f"Faltan archivos de entrada: {faltan}\nCorré primero: "
                 f"python src/generar.py && python src/validar.py")

    BASE.parent.mkdir(parents=True, exist_ok=True)
    MARTS.mkdir(parents=True, exist_ok=True)
    if BASE.exists():
        BASE.unlink()

    con = duckdb.connect(str(BASE))
    inicio = time.time()
    for nombre in ARCHIVOS:
        t0 = time.time()
        n = ejecutar(con, SQL / nombre)
        print(f"  {nombre:22s} {n:2d} sentencias   {time.time() - t0:5.2f}s")
    print(f"  {'total':22s} {'':15s}{time.time() - inicio:5.2f}s")

    tablas = [t[0] for t in con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' ORDER BY table_name").fetchall()]
    print(f"\nTablas creadas: {len(tablas)}")
    for prefijo, titulo in [("dim_", "dimensiones"), ("fact_", "hechos"), ("mart_", "marts")]:
        nombres = [t.replace(prefijo, "") for t in tablas if t.startswith(prefijo)]
        print(f"  {titulo:12s} {', '.join(nombres)}")

    print("\nControl del almacén")
    control = con.execute("SELECT * FROM v_control_almacen").df()
    print(control.to_string(index=False))

    for mart in [t for t in tablas if t.startswith("mart_")]:
        con.execute(f"COPY {mart} TO '{(MARTS / (mart + '.csv')).as_posix()}' (HEADER, DELIMITER ',')")
    con.execute(f"COPY (SELECT * FROM v_control_almacen) TO "
                f"'{(MARTS / 'control_almacen.csv').as_posix()}' (HEADER, DELIMITER ',')")
    print(f"\nMarts exportados a {MARTS.relative_to(RAIZ)}")

    fallidas = control[control["resultado"] != "OK"]
    if not fallidas.empty:
        con.close()
        sys.exit(f"\n{len(fallidas)} comprobaciones no cuadran. El modelo no se publica.")

    print(f"Base en {BASE.relative_to(RAIZ)}")
    con.close()


if __name__ == "__main__":
    main()
