# cartera-garantias-dq

**Análisis de confiabilidad de una cartera de garantías inmobiliarias**

> **Proyecto de portafolio.** El problema es real; el caso, la entidad y los datos son simulados.
> Ninguna cifra describe el desempeño de una organización existente.

Un banco tiene miles de créditos respaldados por propiedades. Este proyecto toma dos cortes
mensuales de esa cartera, les aplica ocho reglas de calidad definidas con criterio de valuación,
cruza el resultado con el saldo de cada crédito y responde: **¿qué proporción de la exposición
está respaldada por avalúos confiables, y cuáles conviene atender primero?**

---

## El resultado

Con la **misma capacidad de 150 avalúos al mes**, ordenar la revisión por exposición en riesgo
en vez de por antigüedad cubre **4,18 veces más saldo expuesto**.

| Criterio | Casos | No confiables atendidos |
|---|---:|---:|
| Por exposición en riesgo *(propuesto)* | 150 | **140 de 140** (100 %) |
| Por antigüedad *(criterio actual)* | 150 | 16 de 140 (11,4 %) |

No es una proyección ni un ahorro estimado: son los dos ordenamientos aplicados sobre los mismos
datos. **El proyecto no reduce el esfuerzo de revisión, cambia el orden** — las horas disponibles
son las mismas; lo que cambia es dónde se gastan.

En el corte de abril, el saldo con respaldo confiable es de **85,9 % en colones** y **88,3 % en
dólares**. La tasa de incumplimiento bajó de 30 % a 12 % entre los dos cortes, pero **1 de cada 3
avalúos defectuosos sigue defectuoso**: la mejora viene tanto de correcciones como de rotación de
cartera, y el modelo las separa.

El análisis completo está en **[`reports/memo_ejecutivo.md`](reports/memo_ejecutivo.md)**, que se
genera con un script y no a mano.

*(Recordatorio: cifras de un escenario simulado.)*

---

## Cómo está construido

```
reference/     6 tablas de referencia con criterio de valuación
    ↓
src/generar.py         genera dos cortes mensuales + créditos + ground truth
    ↓
src/validar.py         aplica las 8 reglas activas del catálogo
    ↓
sql/ (5 archivos)      staging → 7 dimensiones → 2 hechos → 9 marts → control
    ↓
src/generar_memo.py    memo ejecutivo        dashboards/    Power BI, 3 páginas
```

**Stack:** Python con pandas para validar, DuckDB para el SQL, Power BI para el tablero.
DuckDB se instala con `pip`, lee y escribe CSV directo y no requiere servidor ni ODBC.

### Tres decisiones que definen el proyecto

**Dos tablas de hechos, no una.** Un avalúo puede incumplir tres reglas. En una sola tabla
aparecería tres veces y su valor de garantía se sumaría tres veces. Medido sobre estos datos: 310
avalúos se convertirían en 350 filas, inflando la cartera en ₡55.178 millones que no existen.
`fact_garantia` y `fact_incidencia` comparten dimensiones y nunca se unen entre sí.

**Las reglas viven en un CSV, no en el código.** Activar R-09 o R-10 es cambiar una celda de
[`reference/reglas_datos.csv`](reference/reglas_datos.csv). Cada regla declara su acción
—BLOQUEA o REVISA—, su responsable y su justificación.

**No se consolidan monedas.** La exposición se reporta siempre segmentada en CRC y USD. El tipo de
cambio de `reference/parametros.csv` es un supuesto declarado y se usa **solo** para ordenar la
lista de trabajo, nunca para reportar cartera.

### Si las cifras no cuadran, no se publica

El almacén se reconcilia contra sus propias fuentes en **once comprobaciones** antes de exportar
nada. Si alguna falla, el script no escribe ningún CSV y los de la corrida anterior quedan
intactos. Esa tabla de control va **en el tablero, a la vista**, no en un log.

El pipeline es **reproducible byte a byte**: borrar el almacén y reconstruirlo desde cero produce
archivos idénticos. Las listas ordenadas llevan desempate explícito para que no dependan del
momento en que se ejecutó el script.

---

## Estado

| Fase | Estado |
|---|---|
| 1 · Fundamentos | Completa |
| 2 · Datos | Completa |
| 3 · Validación | Completa |
| 4 · Modelo | Completa |
| 5 · Entrega | En curso — memo y modelo listos, tablero pendiente |

## Documentación

- [`reports/memo_ejecutivo.md`](reports/memo_ejecutivo.md) — **el análisis y sus conclusiones**
- [`docs/MANUAL.md`](docs/MANUAL.md) — qué es, qué resuelve, cómo funciona, y las limitaciones declaradas
- [`docs/diccionario_datos.md`](docs/diccionario_datos.md) — campos, tipos, reglas y parámetros
- [`reference/reglas_datos.csv`](reference/reglas_datos.csv) — catálogo de reglas con responsable y justificación
- [`dashboards/GUIA_POWERBI.md`](dashboards/GUIA_POWERBI.md) — cómo se arma el tablero

---

## Ejecutar el proyecto

### Instalación

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
python src/verificar_referencias.py
```

### El pipeline completo

```bash
python src/verificar_referencias.py   # las 6 tablas de referencia son consistentes
python src/generar.py                 # dos cortes, créditos y ground truth
python src/validar.py                 # aplica las reglas activas del catálogo
python src/probar_validador.py        # contrasta lo detectado contra el ground truth
python src/construir_almacen.py       # el SQL sobre DuckDB + las 11 comprobaciones
python src/generar_memo.py            # el memo ejecutivo
```

Cada paso falla ruidosamente si sus cifras no cuadran. `generar.py` solo se corre para rehacer
el escenario: regenera todo y cambia las cifras.

### Qué produce cada etapa

**`generar.py`** escribe los dos cortes y los créditos en `data/raw/`, y el ground truth en
`data/ground_truth/`. Es determinístico: misma semilla, mismos archivos. Los parámetros están en
el bloque `PARÁMETROS DE SIMULACIÓN` del script y en `docs/diccionario_datos.md`, sección 7.

**`validar.py`** produce `avaluos_validados.csv`, `incidencias.csv` y `control_cifras.csv` en
`data/output/`. Si las cifras no cuadran, termina con error y no publica.

**`probar_validador.py`** compara lo detectado contra los defectos que el generador sembró, en
ambas direcciones. Verifica que la implementación coincide con la intención; **no** prueba que el
sistema detectaría errores que nadie anticipó, porque el generador define el universo de defectos
posibles.

**`construir_almacen.py`** ejecuta los cinco archivos de `sql/` sobre DuckDB, verifica las once
comprobaciones y recién entonces exporta:

| Salida | Contenido | Para qué |
|---|---|---|
| `data/modelo/` | 7 dimensiones y 3 hechos | El modelo de Power BI |
| `data/marts/` | 9 marts y el control de cifras | Agregados y tablas auxiliares |

Power BI no tiene conector nativo de DuckDB: por eso se exportan los dos niveles a CSV en vez de
conectar contra la base.

```
sql/01_staging.sql      tipado y despivoteo de resultados por regla
sql/02_dimensiones.sql  siete dimensiones con clave subrogada
sql/03_hechos.sql       fact_garantia y fact_incidencia
sql/04_marts.sql        exposición, Pareto, evolución, lista de trabajo
sql/05_control.sql      reconciliación entre capas
```

**`generar_memo.py`** escribe `reports/memo_ejecutivo.md` a partir de los marts. No recalcula
nada: toda cifra sale de una tabla que ya pasó la reconciliación. Se regenera con los datos, así
que cambiar la semilla no deja cifras viejas escritas a mano.

### El tablero

Se arma siguiendo [`dashboards/GUIA_POWERBI.md`](dashboards/GUIA_POWERBI.md), con las medidas de
[`dashboards/medidas_dax.txt`](dashboards/medidas_dax.txt). Tres páginas: Exposición, Diagnóstico
y Lista de trabajo.

El paso 10 de esa guía contrasta cada cifra del tablero contra el modelo. Las dos salidas vienen
del mismo origen por caminos distintos: si no coinciden, hay un error en el armado.

---

## Qué no hace este proyecto

Las limitaciones están declaradas en `docs/MANUAL.md`, sección 15. Las principales:

1. **Los datos son sintéticos.** El generador define los defectos que el validador busca.
   Detectarlos todos verifica que el código es correcto, no que encontraría errores no anticipados.
2. **Las tasas de incumplimiento y corrección son parámetros de diseño**, no observaciones.
3. **La validación geográfica es aproximada:** distancia al centroide del distrito contra un radio
   declarado, no pertenencia a un polígono.
4. **Los rangos de valor unitario son ilustrativos.** No son una tabla de valores de mercado.
5. **Dos cortes no son una serie.** Permiten comparar, no proyectar tendencia.

Los archivos regenerables (`data/output/`, `warehouse/*.duckdb`) no se versionan: se reconstruyen
corriendo el pipeline.
