"""
construir_almacen.py — Ejecuta el SQL en DuckDB y exporta los marts.

Corre los cinco archivos de sql/ en orden sobre una base DuckDB, verifica la
reconciliación y exporta a CSV tanto los marts como el modelo dimensional, para
que Power BI los consuma sin necesidad de conector.

Por qué se exportan las dos cosas
---------------------------------
Power BI no tiene conector nativo de DuckDB. Los marts alimentan los visuales ya
agregados; el modelo dimensional (dimensiones + los dos hechos) alimenta las
medidas DAX que necesitan filtrar por cualquier atributo. Las dos tablas de
hechos comparten dimensiones y nunca se unen entre sí: ver docs/MANUAL.md,
sección 11.

Uso
---
    python src/construir_almacen.py

Salidas
-------
warehouse/garantias.duckdb   la base completa: staging, dimensiones, hechos, marts
data/marts/*.csv             un archivo por mart, para los visuales agregados
data/modelo/*.csv            dimensiones y hechos, para el modelo de Power BI
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
MODELO = RAIZ / "data" / "modelo"

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


def exportar(con, tabla: str, destino: Path) -> None:
    """Exporta una tabla a CSV con las filas siempre en el mismo orden.

    Sin ORDER BY, DuckDB no garantiza el orden de salida de una agregación: dos
    corridas sobre los mismos datos producen los mismos valores en filas
    barajadas. Los CSV se versionan, así que eso llenaría cada diff de ruido y
    haría imposible ver un cambio real. ORDER BY ALL ordena por todas las
    columnas de izquierda a derecha y vuelve la exportación reproducible.
    """
    con.execute(f"COPY (SELECT * FROM {tabla} ORDER BY ALL) TO "
                f"'{destino.as_posix()}' (HEADER, DELIMITER ',')")


def main():
    faltan = [f for f in ("data/output/avaluos_validados.csv", "data/output/incidencias.csv",
                          "data/raw/creditos.csv", "reference/parametros.csv")
              if not (RAIZ / f).exists()]
    if faltan:
        sys.exit(f"Faltan archivos de entrada: {faltan}\nCorré primero: "
                 f"python src/generar.py && python src/validar.py")

    BASE.parent.mkdir(parents=True, exist_ok=True)
    MARTS.mkdir(parents=True, exist_ok=True)
    MODELO.mkdir(parents=True, exist_ok=True)
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

    # La reconciliación se evalúa ANTES de exportar. Si se exportara primero, un
    # fallo dejaría CSV recién escritos en disco junto a un mensaje de error: la
    # próxima persona que abra Power BI encontraría archivos con fecha de hoy y
    # cifras que no cuadran. "No se publica" tiene que significar que no hay
    # archivo nuevo, no que hubo una queja después de escribirlo.
    fallidas = control[control["resultado"] != "OK"]
    if not fallidas.empty:
        con.close()
        sys.exit(f"\n{len(fallidas)} comprobaciones no cuadran. No se exporta nada.\n"
                 f"Los CSV de la corrida anterior quedan intactos.")

    for mart in [t for t in tablas if t.startswith("mart_")]:
        exportar(con, mart, MARTS / f"{mart}.csv")
    exportar(con, "v_control_almacen", MARTS / "control_almacen.csv")
    print(f"\nMarts exportados a {MARTS.relative_to(RAIZ)}")

    dimensionales = [t for t in tablas if t.startswith(("dim_", "fact_"))]
    for tabla in dimensionales:
        exportar(con, tabla, MODELO / f"{tabla}.csv")
    print(f"Modelo dimensional exportado a {MODELO.relative_to(RAIZ)} "
          f"({len(dimensionales)} tablas)")

    print(f"Base en {BASE.relative_to(RAIZ)}")
    con.close()


if __name__ == "__main__":
    main()
