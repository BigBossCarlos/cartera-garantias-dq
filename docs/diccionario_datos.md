# Diccionario de datos — `cartera-garantias-dq`

Versión 1.0 · Reemplaza al contrato YAML del diseño anterior. Es la única fuente de definición de campos, tipos y parámetros de negocio.

---

## 1. Grano y claves

**Grano:** una fila de `avaluos_YYYY_MM.csv` representa el avalúo de **un** inmueble inscrito bajo un único número de finca, elaborado por un perito, con una fecha de valor determinada, tal como estaba registrado en la fecha de corte.

**Consecuencias:**
- Una misma finca puede tener varios avalúos con fechas de valor distintas.
- `numero_finca` **no** es único.
- `id_avaluo` debe ser único dentro de un corte (R-01).
- El mismo avalúo aparece en ambos cortes si sigue en cartera.

**Clave de seguimiento entre cortes:** `id_avaluo`. Un avalúo corregido conserva su identificador; lo que cambia es el contenido. El caso de dos avalúos distintos que comparten identificador por error es precisamente lo que detecta R-01, y se trata como un grupo, no como un avalúo.

**Fuera de alcance:** avalúos que cubren varias fincas (finca matriz y filiales), bienes muebles, Isla del Coco.

---

## 2. Tabla `avaluos_YYYY_MM.csv` — 20 campos

Un archivo por corte: `avaluos_2026_03.csv` y `avaluos_2026_04.csv`.

| # | Campo | Tipo | Oblig. | Definición | Reglas |
|---|---|---|---|---|---|
| 1 | `id_avaluo` | texto | Sí | Identificador de negocio, formato `AV-AAAA-NNNNNN` | R-01, R-02 |
| 2 | `numero_finca` | texto | Sí | Número registral. Convención sintética `P-NNNNNN[-FFF]`; no se valida contra el Registro Nacional | R-02 |
| 3 | `finalidad` | texto | Sí | Propósito del avalúo. Dominio: Garantía hipotecaria · Leasing · Actualización de garantía · Seguro · Contable · Compraventa | R-02 |
| 4 | `fecha_inspeccion` | fecha | Sí | Visita física al inmueble | R-02, R-05 |
| 5 | `fecha_valor` | fecha | Sí | Fecha a la que está referido el valor. Es la fecha con significado técnico (IVS la distingue de la del informe) | R-02, R-05, R-08 |
| 6 | `fecha_informe` | fecha | Sí | Emisión del informe firmado | R-02, R-05 |
| 7 | `provincia` | texto | Sí | Según `geografia.csv` | R-02, R-06 |
| 8 | `canton` | texto | Sí | Según `geografia.csv` | R-02, R-06 |
| 9 | `distrito` | texto | Sí | Según `geografia.csv`. La validación es de la terna completa | R-02, R-06 |
| 10 | `latitud` | decimal(9,6) | Sí | WGS84. Rango nacional aproximado 8.0 – 11.3 | R-02, R-06 |
| 11 | `longitud` | decimal(9,6) | Sí | WGS84. Rango nacional aproximado −86.0 – −82.5 | R-02, R-06 |
| 12 | `tipologia_inmueble` | texto | Sí | Según `tipologias.csv`. Gobierna R-04 | R-02, R-04, R-07 |
| 13 | `moneda` | texto | Sí | `CRC` o `USD`. Aplica a todos los importes de la fila | R-02, R-03, R-07 |
| 14 | `area_terreno_m2` | decimal(12,2) | Sí | Área registral del terreno. Mín 30, máx 500.000 | R-02, R-03 |
| 15 | `valor_unitario_terreno_m2` | decimal(14,2) | Sí | Valor por m² de terreno, en la moneda de la fila | R-02, R-03, R-07 |
| 16 | `area_construccion_m2` | decimal(12,2) | Sí | Área construida. Cero si la tipología no contempla edificaciones | R-02, R-03, R-04 |
| 17 | `valor_unitario_construccion_m2` | decimal(14,2) | **Condicional** | Obligatorio si `area_construccion_m2` > 0; debe ser cero si es 0 | R-02, R-03, R-04 |
| 18 | `valor_obras_complementarias` | decimal(14,2) | Sí | Tapias, aceras, portones, ranchos, piscinas. Cero si no aplica | R-02, R-03 |
| 19 | `valor_total_inmueble` | decimal(16,2) | Sí | Declarado por la fuente y **ya redondeado**. R-03 verifica que coincida con la suma | R-02, R-03 |
| 20 | `perito_id` | texto | Sí | Seudonimizado, formato `PER-NNN`. Según `peritos.csv` | R-02 |

**Campo agregado por el proceso:** `corte` (texto, `2026-03` / `2026-04`), derivado del nombre del archivo.

---

## 3. Tabla `creditos.csv`

Una fila por crédito y corte. Solo el 80 % de los avalúos respalda un crédito: el resto tiene finalidades sin exposición.

| Campo | Tipo | Definición |
|---|---|---|
| `corte` | texto | `2026-03` / `2026-04` |
| `id_credito` | texto | Formato `CR-NNNNNN` |
| `id_avaluo` | texto | Avalúo que respalda la operación. Clave de cruce |
| `moneda` | texto | **Igual a la moneda del avalúo**, por regla de diseño |
| `saldo` | decimal(16,2) | Saldo pendiente a la fecha de corte |
| `fecha_desembolso` | fecha | Inicio de la operación |
| `estado` | texto | `VIGENTE` / `CANCELADO` |

**Regla de diseño:** la moneda del crédito coincide siempre con la del avalúo. Sin esa restricción, LTV = saldo ÷ valor mezclaría monedas y no tendría sentido.

---

## 4. Salidas de `validar.py`

### `avaluos_validados.csv` — una fila por avalúo y corte

Todos los campos de la tabla de avalúos, más:

| Campo | Definición |
|---|---|
| `corte` | Corte de origen |
| `n_bloquea` | Cantidad de reglas BLOQUEA incumplidas |
| `n_revisa` | Cantidad de reglas REVISA incumplidas |
| `nivel_confiabilidad` | `CONFIABLE` (0 incumplimientos) · `REVISAR` (solo REVISA) · `NO_CONFIABLE` (≥1 BLOQUEA) |
| `R-01` … `R-08` | Resultado por regla: `CUMPLE` · `INCUMPLE` · `NO_APLICA` |

### `incidencias.csv` — una fila por incumplimiento

| Campo | Definición |
|---|---|
| `corte` | Corte de origen |
| `id_avaluo` | Avalúo afectado |
| `rule_id` | Regla incumplida |
| `campo` | Campo evaluado |
| `valor_observado` | Lo que traía el dato |
| `condicion_esperada` | Lo que debía cumplir |

### `control_cifras.csv` — una fila por corte

| Campo | Definición |
|---|---|
| `corte` | |
| `recibidos` | Filas leídas del archivo |
| `procesados` | Filas evaluadas |
| `confiable` · `revisar` · `no_confiable` | Conteo por nivel |
| `cuadra` | `SI` si recibidos = procesados = suma de niveles |

---

## 5. Tablas de referencia

| Archivo | Clave | Columnas | Usa |
|---|---|---|---|
| `geografia.csv` | provincia, canton, distrito | `zona`, `lat_centroide`, `lon_centroide`, `radio_km`, `verificado` | R-06, R-07 (vía zona), dim_geografia |
| `tipologias.csv` | tipologia | `requiere_construccion` (SI/NO/OPCIONAL), `cobertura_min`, `cobertura_max`, `moneda_habitual`, `activa` | R-04, R-09, dim_tipologia |
| `rangos_vu.csv` | zona, tipologia, moneda | `vu_min`, `vu_max`, `fuente` | R-07 |
| `peritos.csv` | perito_id | `activo` | dim_perito |
| `reglas_datos.csv` | rule_id | `nombre`, `dimension`, `accion`, `campo_principal`, `responsable`, `justificacion`, `activa`, `motivo_inactiva` | validar.py, dim_regla |

**Zonas:** `GAM_CENTRO` · `GAM_PERIFERIA` · `CIUDAD_INTERMEDIA` · `RURAL` · `COSTA`. Cada distrito pertenece a una. Los rangos de valor se definen por zona porque así razonan los valuadores y porque 35 distritos × 9 tipologías sería una tabla imposible de mantener.

**Combinaciones ausentes en `rangos_vu.csv`** no son error: R-07 devuelve `NO_APLICA` para esa fila.

---

## 6. Parámetros de negocio

Ninguno vive en el código. Todos son discutibles con el negocio y por eso están aquí.

| Parámetro | Valor | Usa | Origen |
|---|---|---|---|
| Paso de redondeo del valor total | ₡1.000 · US$1 | R-03 | Práctica habitual en informes |
| Tolerancia de R-03 | ₡500 · US$0,50 | R-03 | Derivada: medio paso de redondeo, comparador `<=` |
| Método de redondeo | half-up, solo sobre el total | R-03 | Los componentes no se redondean |
| Máx. días inspección → valor | 30 | R-05 | Supuesto operativo |
| Máx. días valor → informe | 15 | R-05 | Supuesto operativo |
| Fechas futuras | No permitidas | R-05 | Respecto de la fecha de corte |
| Vigencia del avalúo | 24 meses | R-08 | **Política interna asumida. Ajustar a la práctica del cliente bancario** |
| Radio geográfico | Por distrito, en `geografia.csv` | R-06 | 2–4 km urbano, 8–20 km rural |
| Sistema de coordenadas | WGS84 (EPSG:4326) | R-06 | |
| Capacidad de revisión | 150 avalúos/mes | Lista de trabajo | **Supuesto** |
| Orden de la lista de trabajo | 1º `NO_CONFIABLE` por saldo desc · 2º `REVISAR` por saldo desc | Lista de trabajo | Decisión de diseño: lexicográfico, sin pesos |

**Tratamiento de nulos:** `""`, espacios, `N/A`, `NA`, `null`, `-` se consideran ausencia. Se aplica `trim` antes de evaluar.

---

## 7. Parámetros del generador

| Parámetro | Valor |
|---|---|
| Avalúos por corte | 4.000 |
| Con crédito vigente | 80 % |
| Con ≥1 incumplimiento en marzo | 1.200 (30 %) |
| — de los cuales `NO_CONFIABLE` | 320 (8 %) |
| — de los cuales `REVISAR` | 880 (22 %) |
| Corregidos entre cortes | 720 (60 % de los defectuosos) |
| Persistentes | 360 (30 %) |
| Salen de cartera (defectuosos) | 120 (10 %) |
| Salidas totales de cartera | 200 |
| Entradas a cartera | 200 |
| Nuevos incumplimientos en abril | 120 |
| Con ≥1 incumplimiento en abril | 480 (12 %) |
| Semilla | 2026 |

**Propensión a error por perito:** el generador asigna a cada perito una probabilidad distinta de introducir defectos, para que el indicador de tasa por perito tenga señal. Esa propensión vive en el generador, no en `peritos.csv`: es parámetro de simulación, no dato de referencia.

---

## 8. Ground truth

El generador sabe qué defectos sembró. Lo exporta para que la Fase 3 pueda demostrar que el validador los encuentra todos, y la Fase 4 que la comparación entre cortes clasifica bien.

### `data/ground_truth/incumplimientos_sembrados.csv`

| Campo | Definición |
|---|---|
| `corte` | `2026-03` / `2026-04` |
| `id_avaluo` | Tal como aparece en el archivo del corte |
| `numero_finca` | Desambigua los pares R-01, que comparten `id_avaluo` |
| `rule_id` | Regla que el avalúo incumple en ese corte |

Un avalúo aparece una vez por regla que incumple. Incluye los incumplimientos **derivados**: un R-04 que no recalcula el total también genera R-03; un persistente cuya fecha de valor cruza el umbral de vigencia entre cortes también genera R-08.

### `data/ground_truth/evolucion_esperada.csv`

Una fila por avalúo, con `id_avaluo_marzo`, `id_avaluo_abril` y `categoria`:

| Categoría | Significado |
|---|---|
| `CORREGIDO` | Incumplía en marzo, cumple en abril |
| `PERSISTENTE` | Incumplía en marzo, sigue incumpliendo en abril |
| `NUEVO` | Cumplía o no existía en marzo, incumple en abril |
| `SALIO` | Incumplía en marzo, no está en abril |
| `SALIO_CUMPLIENDO` | Cumplía en marzo, no está en abril |
| `ENTRA_CUMPLIENDO` | No existía en marzo, cumple en abril |
| `CUMPLE` | Cumple en ambos cortes |

### Lo que el analista verá distinto: el efecto R-01

El ground truth sigue a cada avalúo por su identidad real. El SQL de la Fase 4 solo puede seguirlo por `id_avaluo`. Ambos coinciden **excepto** en los pares R-01:

- Cuando un par se corrige, el segundo avalúo recupera su identificador original, que nunca apareció en marzo. Por identificador parece una entrada nueva.
- Cuando un par persiste, dos avalúos cuentan como un solo identificador.
- Cuando en abril aparece un par nuevo, el identificador propio del segundo avalúo desaparece: parece una salida.

Con 20 pares en marzo y 2 nuevos en abril, la diferencia es de una o dos decenas de registros en cada categoría. No es un error de ninguno de los dos: es la consecuencia inevitable de que la clave de negocio esté bajo sospecha. La Fase 4 debe reportarlo, no ajustarlo.

### Parámetros invariantes

Independientemente de los rangos que contenga `rangos_vu.csv`, el generador garantiza: 4.000 avalúos por corte; 1.200 con incumplimiento en marzo (320 `NO_CONFIABLE`, 880 `REVISAR`); 720 corregidos, 360 persistentes, 120 que salen; 120 nuevos; 480 con incumplimiento en abril. La distribución por regla sí varía: si una combinación no tiene rango, R-07 no puede sembrarse ahí y el cupo pasa a R-08.
