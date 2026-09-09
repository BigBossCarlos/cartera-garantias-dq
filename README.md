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
| 2 · Datos | En curso |
| 3 · Validación | Pendiente |
| 4 · Modelo | Pendiente |
| 5 · Entrega | Pendiente |

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
