# cartera-garantias-dq

**Análisis de confiabilidad de una cartera de garantías inmobiliarias**

> Proyecto de portafolio. El problema es real; el caso, la entidad y los datos son simulados.
> Ninguna cifra describe el desempeño de una organización existente.

Un banco tiene miles de créditos respaldados por propiedades. Este proyecto toma dos cortes
mensuales de esa cartera, les aplica ocho reglas de calidad definidas con criterio de valuación,
cruza el resultado con el saldo de cada crédito y responde: **¿qué proporción de la exposición
está respaldada por avalúos confiables, y cuáles conviene atender primero?**

## Estado

| Fase | Estado |
|---|---|
| 1 · Fundamentos | Completa |
| 2 · Datos | Completa |
| 3 · Validación | Completa |
| 4 · Modelo | Completa |
| 5 · Entrega | En curso — memo y modelo listos, tablero pendiente |

## Documentación

- [`docs/MANUAL.md`](docs/MANUAL.md) — qué es, qué resuelve, cómo funciona
- [`docs/diccionario_datos.md`](docs/diccionario_datos.md) — campos, tipos, reglas y parámetros
- [`reference/reglas_datos.csv`](reference/reglas_datos.csv) — catálogo de reglas con responsable y justificación

## Instalación

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python src/verificar_referencias.py
```

## Generar los datos

```bash
python src/generar.py
```

Produce los dos cortes y los créditos en `data/raw/`, y el ground truth en `data/ground_truth/`.
Es determinístico: misma semilla, mismos archivos. Los parámetros del experimento están en el
bloque `PARÁMETROS DE SIMULACIÓN` del script y documentados en `docs/diccionario_datos.md`, sección 7.

## Validar

```bash
python src/validar.py            # aplica las reglas activas del catálogo
python src/probar_validador.py   # compara lo detectado contra el ground truth
```

`validar.py` produce `avaluos_validados.csv`, `incidencias.csv` y `control_cifras.csv`
en `data/output/`. Si las cifras no cuadran, termina con error y no publica.

Qué reglas se aplican lo decide `reference/reglas_datos.csv`, no el código: activar
R-09 o R-10 es cambiar una celda de ese CSV.

## Construir el modelo

```bash
python src/construir_almacen.py
```

Ejecuta los cinco archivos de `sql/` sobre DuckDB, verifica once comprobaciones de
reconciliación y exporta a CSV el modelo dimensional y los marts. Si alguna
comprobación no cuadra, el modelo no se publica.

| Salida | Contenido | Para qué |
|---|---|---|
| `data/modelo/` | 7 dimensiones y 3 hechos | El modelo de Power BI |
| `data/marts/` | 9 marts y el control de cifras | Agregados y tablas auxiliares |

Power BI no tiene conector nativo de DuckDB: por eso se exportan los dos niveles
a CSV en vez de conectar contra la base.

```
sql/01_staging.sql      tipado y despivoteo de resultados por regla
sql/02_dimensiones.sql  siete dimensiones con clave subrogada
sql/03_hechos.sql       fact_garantia y fact_incidencia
sql/04_marts.sql        exposición, Pareto, evolución, lista de trabajo
sql/05_control.sql      reconciliación entre capas
```

## Entregar

```bash
python src/generar_memo.py
```

Escribe `reports/memo_ejecutivo.md` a partir de los marts. No recalcula nada: toda
cifra del memo sale de una tabla que ya pasó la reconciliación, y si alguna
comprobación falla el memo no se publica. Se regenera con los datos, así que
cambiar la semilla del generador no deja cifras viejas escritas a mano.

El tablero se arma siguiendo [`dashboards/GUIA_POWERBI.md`](dashboards/GUIA_POWERBI.md),
con las medidas de [`dashboards/medidas_dax.txt`](dashboards/medidas_dax.txt).
Tres páginas: Exposición, Diagnóstico y Lista de trabajo.

La sección 11 de la guía contrasta cada cifra del tablero contra el memo. Las dos
salidas vienen del mismo modelo por caminos distintos: si no coinciden, hay un
error en el armado.
