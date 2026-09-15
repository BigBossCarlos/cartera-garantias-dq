# Armado del tablero en Power BI Desktop

Guía para construir `dashboards/cartera_garantias_dq.pbix` contra los datos que
produce el pipeline de este repositorio.

**Entregable:** un `.pbix` con tres páginas —**Exposición**, **Diagnóstico** y
**Lista de trabajo**— sobre el modelo dimensional de `data/modelo/`.

Las medidas están en [`medidas_dax.txt`](medidas_dax.txt). Esta guía dice qué
cargar, cómo relacionarlo y qué va en cada página; ese archivo dice qué pegar.

---

## 0. Antes de abrir Power BI

Correr el pipeline. Power BI lee CSV, no la base DuckDB.

```powershell
.\.venv\Scripts\python.exe src\verificar_referencias.py
.\.venv\Scripts\python.exe src\validar.py
.\.venv\Scripts\python.exe src\probar_validador.py
.\.venv\Scripts\python.exe src\construir_almacen.py
.\.venv\Scripts\python.exe src\generar_memo.py
```

`src\generar.py` **no** está en esa lista a propósito: regenera la simulación y
cambia todas las cifras. Solo se corre si `data/raw/` está vacío o si se decide
deliberadamente rehacer el escenario, y en ese caso hay que correr todo lo demás
otra vez.

**Punto de control:** `construir_almacen.py` tiene que terminar con las once
comprobaciones en `OK`. Si alguna falla, el script no exporta nada y los CSV de
la corrida anterior quedan intactos. No se sigue hasta que las once estén en OK.

Al terminar deben existir 20 CSV:

| Carpeta | Archivos | Contenido |
|---|---|---|
| `data/modelo/` | 10 | 7 dimensiones + 3 hechos |
| `data/marts/` | 10 | 9 marts + `control_almacen.csv` |

---

## 1. El ajuste que hay que hacer primero

> **Antes de cargar cualquier dato.** Si se omite, los números se cargan mal y el
> error es silencioso.

DuckDB escribe los CSV con **punto decimal** (`288588.48`). Power BI en
configuración regional de Costa Rica lee ese punto como separador de miles y
convierte `288588.48` en `28.858.848`. Las cifras quedan infladas y nada falla a
la vista.

1. **Archivo > Opciones y configuración > Opciones**.
2. Sección **ARCHIVO ACTUAL > Configuración regional**.
3. **Configuración regional para importar datos:** `Inglés (Estados Unidos)`.
4. En **ARCHIVO ACTUAL > Carga de datos**, desmarcar **Detectar nuevas
   relaciones después de cargar los datos**. Así se crean solo las 15 relaciones
   de esta guía.
5. Aceptar.

Esto cambia cómo se **interpretan** los archivos al importarlos, no cómo se
muestran las cifras. El informe sigue en español.

Guardar ya como `dashboards/cartera_garantias_dq.pbix`.

---

## 2. Cargar las quince tablas

**Inicio > Obtener datos > Texto/CSV**, una vez por archivo. En cada ventana de
vista previa, antes de cargar:

- **Origen de archivo:** `65001: Unicode (UTF-8)`. Sin esto "Ramón" se ve
  "RamÃ³n".
- **Delimitador:** Coma.
- Verificar que los decimales se vean `288588.48` y no `28858848`. Si están mal,
  el paso 1 no se aplicó.

Cada archivo es una consulta independiente. **No usar "Combinar archivos":** son
tablas de estructuras distintas.

### De `data/modelo/` — el modelo (10)

| Archivo | Consulta | Rol |
|---|---|---|
| `dim_corte.csv` | `dim_corte` | Los dos cortes mensuales |
| `dim_fecha.csv` | `dim_fecha` | Calendario |
| `dim_geografia.csv` | `dim_geografia` | Provincia, cantón, distrito, zona |
| `dim_tipologia.csv` | `dim_tipologia` | Tipo de inmueble |
| `dim_perito.csv` | `dim_perito` | Profesional que firmó |
| `dim_regla.csv` | `dim_regla` | Catálogo de reglas |
| `dim_confiabilidad.csv` | `dim_confiabilidad` | Confiable / Revisar / No confiable |
| `fact_garantia.csv` | `fact_garantia` | **Hecho 1:** un avalúo en un corte |
| `fact_incidencia.csv` | `fact_incidencia` | **Hecho 2:** un incumplimiento |
| `fact_cobertura_regla.csv` | `fact_cobertura_regla` | Cuántos avalúos evaluó cada regla |

### De `data/marts/` — tablas sueltas (4)

| Archivo | Consulta | Por qué va aparte |
|---|---|---|
| `mart_evolucion.csv` | `mart_evolucion` | Su grano cruza los dos cortes a la vez |
| `mart_lista_trabajo.csv` | `mart_lista_trabajo` | Trae el orden de prioridad ya calculado |
| `mart_comparacion_priorizacion.csv` | `mart_comparacion_priorizacion` | Tres filas: la conclusión del proyecto |
| `control_almacen.csv` | `control_almacen` | Las once comprobaciones |

### De `reference/` — el supuesto declarado (1)

| Archivo | Consulta | Para qué |
|---|---|---|
| `reference/parametros.csv` | `parametros` | Capacidad mensual y tipo de cambio |

Se importa para que la medida `Meses de rezago` lea la capacidad del modelo en
vez de tener un `150` escondido dentro de una fórmula. El supuesto queda visible.

### Los cinco marts que NO se cargan

`mart_exposicion`, `mart_pareto_reglas`, `mart_concentracion`, `mart_perito` y
`mart_cobertura_reglas` son agregaciones que el modelo reproduce con DAX sobre
los hechos. Cargarlas además sería tener la misma cifra en dos lugares, con dos
maneras de que se desincronicen. Sí sirven para **verificar** el tablero al
final (paso 10).

---

## 3. Tipos de datos en Power Query

Power BI acierta casi todo. Hay que revisar:

| Campos | Tipo |
|---|---|
| Todas las `sk_*`, conteos, `prioridad`, `orden` | Número entero |
| `id_avaluo`, `numero_finca`, `rule_id`, `perito_id`, `corte`, `moneda` | Texto |
| `saldo`, `valor_garantia`, `exposicion_no_confiable`, `ltv`, `saldo_equivalente_crc` | Número decimal |
| `fecha`, `fecha_valor`, `fecha_corte` | Fecha |
| `tiene_credito`, `credito_atribuible`, `entra_este_mes` | Verdadero/Falso |

Si un importe con punto decimal se interpreta mal: clic derecho en la columna →
**Cambiar tipo → Usar configuración regional → Número decimal → Inglés (Estados
Unidos)**.

Si un identificador se convirtió a número, eliminar ese paso y asignarle Texto.
**No eliminar identificadores duplicados ni filas con datos ausentes:** son el
problema de calidad que el proyecto mide.

### Una columna extra para el gráfico de dispersión

En `fact_garantia`: **Agregar columna > Columna de índice > Desde 1**.
Renombrarla `id_fila_visual` y convertirla a **Texto**.

Sirve solo para que la dispersión dibuje un punto por avalúo. Sin ella, Power BI
agrega toda la cartera en unos pocos puntos. No es clave de negocio y puede
cambiar al actualizar.

**Inicio > Cerrar y aplicar.**

---

## 4. Las quince relaciones

Vista **Modelo**. Se arrastra la clave de la dimensión sobre la del hecho, o se
usa **Administrar relaciones > Nueva**.

Todas con: dimensión en el lado **1**, hecho en el lado **muchos (\*)**,
dirección de filtro cruzado **Única**, y **activa**. Ninguna bidireccional.

| N.º | Lado 1 | Lado \* |
|---|---|---|
| 1 | `dim_corte[sk_corte]` | `fact_garantia[sk_corte]` |
| 2 | `dim_corte[sk_corte]` | `fact_incidencia[sk_corte]` |
| 3 | `dim_corte[sk_corte]` | `fact_cobertura_regla[sk_corte]` |
| 4 | `dim_fecha[sk_fecha]` | `fact_garantia[sk_fecha_valor]` |
| 5 | `dim_fecha[sk_fecha]` | `fact_incidencia[sk_fecha_valor]` |
| 6 | `dim_geografia[sk_geografia]` | `fact_garantia[sk_geografia]` |
| 7 | `dim_geografia[sk_geografia]` | `fact_incidencia[sk_geografia]` |
| 8 | `dim_tipologia[sk_tipologia]` | `fact_garantia[sk_tipologia]` |
| 9 | `dim_tipologia[sk_tipologia]` | `fact_incidencia[sk_tipologia]` |
| 10 | `dim_perito[sk_perito]` | `fact_garantia[sk_perito]` |
| 11 | `dim_perito[sk_perito]` | `fact_incidencia[sk_perito]` |
| 12 | `dim_confiabilidad[sk_confiabilidad]` | `fact_garantia[sk_confiabilidad]` |
| 13 | `dim_confiabilidad[sk_confiabilidad]` | `fact_incidencia[sk_confiabilidad]` |
| 14 | `dim_regla[sk_regla]` | `fact_incidencia[sk_regla]` |
| 15 | `dim_regla[sk_regla]` | `fact_cobertura_regla[sk_regla]` |

Quedan **sin relaciones**: `mart_evolucion`, `mart_lista_trabajo`,
`mart_comparacion_priorizacion`, `control_almacen` y `parametros`. Es
deliberado, no un descuido: sus granos no corresponden con los de los hechos.

Las quince están verificadas contra la base: cero huérfanos y cero nulos en el
lado de los hechos, y clave única en las siete dimensiones. Power BI no debería
crear ninguna fila en blanco.

### Por qué los dos hechos nunca se unen

Es la decisión de modelado central (`docs/MANUAL.md`, sección 11).

Un avalúo puede incumplir tres reglas. Si `fact_garantia` y `fact_incidencia`
estuvieran unidos, ese avalúo aparecería tres veces y **su valor de garantía se
sumaría tres veces**.

Medido sobre estos datos: los avalúos de abril en colones que tienen al menos
una incidencia son **310**, con ₡651.778 millones de garantía. Uniendo los dos
hechos se vuelven **350 filas** y ₡706.956 millones — **₡55.178 millones que no
existen**. El error es difícil de ver porque el total sigue pareciendo razonable.

Los dos hechos cuelgan de las mismas dimensiones y se comunican solo a través de
ellas. El filtro baja; nunca cruza.

**Si Power BI ofrece crear una relación entre los dos hechos por `id_avaluo`:
rechazarla.**

### Sobre "Marcar como tabla de fechas"

**Omitir ese paso.** `dim_fecha` incluye un miembro `-1 / No informado` con fecha
nula, para que un avalúo sin fecha siga contándose en la cartera en vez de
desaparecer por un `LEFT JOIN` fallido. Power BI exige una columna de fechas sin
nulos y rechazaría la tabla.

No hace falta: la comparación entre cortes usa `dim_corte[orden]`, no
inteligencia de tiempo. Con dos cortes no hay serie que justificar.

### Ajustes de modelo

- `dim_confiabilidad`: seleccionar `etiqueta` → **Herramientas de columna >
  Ordenar por columna > `sk_confiabilidad`**. Así sale Confiable → Revisar → No
  confiable y no en orden alfabético.
- `dim_corte`: ordenar `etiqueta` por `orden`.
- Ocultar en vista de informe todas las columnas `sk_*` de los hechos. Ocultar no
  borra la columna ni su relación.

---

## 5. Las medidas

1. **Inicio > Escribir datos**. Una columna `Auxiliar`, una fila con `1`. Nombre
   de tabla: `_Medidas`. Cargar.
2. Clic derecho sobre `_Medidas` → **Nueva medida**.
3. Abrir [`medidas_dax.txt`](medidas_dax.txt), copiar la **primera** fórmula
   completa (desde su nombre hasta el final), pegarla en la barra y Enter.
4. Repetir con cada una, **en el orden del archivo**. Los grupos posteriores usan
   medidas de los anteriores.
5. Al terminar, ocultar `Auxiliar`.

**No pegar todo el TXT de una vez.**

Las funciones DAX van en inglés y el archivo usa coma como separador de
argumentos. Si tu Power BI está configurado con punto y coma, ajustá la
configuración; no traduzcas las funciones.

Aplicar después los formatos de la última sección del archivo.

### Por qué no hay segmentador de moneda

Cada importe tiene su medida por moneda: `Saldo CRC`, `Saldo USD`,
`Exposición no confiable CRC`, etc.

En este modelo no existe una dimensión de moneda compartida: `moneda` es una
columna de `fact_garantia`, y `fact_incidencia` no la tiene, porque un
incumplimiento es un hecho de calidad, no de dinero. Un segmentador de moneda
filtraría los importes pero **no** las incidencias, y la página parecería
filtrada cuando solo lo estaría a medias.

Con medidas por moneda, cada cifra dice en su propio nombre en qué moneda está.

---

## 6. Página 1 — Exposición

> **¿Qué proporción del saldo tiene respaldo confiable?**

Página 16:9. Título arriba. Reservar la franja inferior para el control de cifras.

### Segmentaciones

| Campo | Configuración |
|---|---|
| `dim_corte[etiqueta]` | **Selección única** activada, con `abril 2026` elegido |
| `dim_geografia[zona]` | Selección múltiple |

### Tarjetas

| Título | Medida |
|---|---|
| Respaldo confiable · ₡ CRC | `% exposición con respaldo confiable (CRC)` |
| Respaldo confiable · US$ USD | `% exposición con respaldo confiable (USD)` |
| Avalúos del corte | `Avalúos` |
| Tasa de incumplimiento | `Tasa de incumplimiento` |
| Variación vs. corte anterior · pp | `Variación de la tasa (pp)` |

En las dos primeras, poner de subtítulo: *"sobre el saldo atribuible a
garantías"*. El crédito que no se pudo atribuir está aparte, en
`mart_credito_no_atribuible`, y no entra en el denominador.

**Colores:** Formato del visual > fondo o color > **fx > Formato por = Valor de
campo** → `Color KPI confiabilidad CRC` (y `USD`, y `Color variación` en la
última). La ruta exacta cambia según la versión; puede estar bajo General >
Efectos. Los umbrales 90 % y 80 % son ilustrativos, no metas acordadas.

### Gráficos

| Visual | Campos |
|---|---|
| Columnas apiladas al 100 % · CRC | Eje X `dim_corte[etiqueta]`; Leyenda `dim_confiabilidad[etiqueta]`; Eje Y `Saldo CRC` |
| Columnas apiladas al 100 % · USD | Igual, con `Saldo USD` |
| Líneas | Eje X `dim_corte[etiqueta]`; Eje Y `Tasa de incumplimiento` |
| Dispersión | Eje X `LTV por punto`; Eje Y `Saldo equivalente (ordenamiento)`; Leyenda `dim_confiabilidad[etiqueta]`; **Valores/Detalles `fact_garantia[id_fila_visual]`** |
| Tabla | `control_almacen[comprobacion]`, `[esperado]`, `[obtenido]`, `[resultado]` |

En la dispersión, agregar a tooltips `id_avaluo`, `numero_finca`, `moneda` y
`saldo`. Título: *"LTV vs. saldo equivalente — tipo de cambio supuesto, no es
cartera consolidada"*.

En la tabla de control: formato condicional de fondo en `resultado`, verde para
`OK`. Mantener el texto visible para que el estado no dependa solo del color.
**Desactivar totales:** las columnas esperado/obtenido son unidades distintas.

### Editar interacciones

La selección única de corte debe filtrar las tarjetas, pero los gráficos
comparativos tienen que mostrar **ambos** cortes.

1. Seleccionar la segmentación de corte.
2. **Formato > Editar interacciones**.
3. Sobre los dos apilados y el gráfico de líneas: **Ninguno** (el círculo
   tachado).
4. Dejar **Filtrar** en las tarjetas y la dispersión.
5. Salir de Editar interacciones.

La segmentación de zona sí filtra todo salvo la tabla de control, que representa
la corrida completa.

Para esta primera versión, desactivar también las interacciones de los gráficos
entre sí. Las segmentaciones son los controles explícitos.

---

## 7. Página 2 — Diagnóstico

> **¿Qué falla y dónde conviene revisar?**

Mismas segmentaciones: corte (selección única, último corte) y zona.

### Pareto de incidencias

1. **Gráfico de líneas y columnas agrupadas**.
2. Eje X: `dim_regla[rule_id]`.
3. Columnas: `Incidencias`.
4. Línea: `% acumulado de incidencias`.
5. Menú `…` → **Ordenar por > Incidencias > Descendente**. Sin ese orden la línea
   no sube de forma monótona y el Pareto no se lee.
6. Activar el eje secundario de la línea, de 0 a 100 %.
7. Tooltips: `dim_regla[nombre]` y `dim_regla[responsable]`.

### Concentración por cantón

1. **Barras agrupadas**. Eje Y `dim_geografia[canton]`, Eje X
   `Exposición no confiable CRC`.
2. Filtros de este objeto visual → filtro de cantón → **Top N > Superior > 10**,
   y arrastrar `Exposición no confiable CRC` a *Por valor*.
3. Al lado, una **tabla** con `canton`, `Exposición no confiable CRC` y
   `Avalúos no confiables`.

La tabla auxiliar existe para distinguir **exposición concentrada en una sola
finca grande** de **muchos casos repartidos**. No es lo mismo y se decide
distinto. Ojo: `Avalúos no confiables` cuenta también casos sin saldo atribuible,
así que el conteo y el importe no describen exactamente el mismo conjunto.

### Por perito

**Líneas y columnas agrupadas**: eje `dim_perito[perito_id]`, columnas
`Tasa de incumplimiento`, línea `Tasa global de referencia`. Ambos ejes en la
misma escala porcentual. Tooltip: `Avalúos`.

**Título:** *"Tasa por perito — diagnóstico, no evaluación de desempeño"*.

La línea es la tasa de toda la cartera del corte y zona seleccionados,
**ponderada por cantidad de avalúos** (12,0 % en abril), no el promedio simple de
los porcentajes individuales (20,3 %), que le daría el mismo peso a un perito con
400 avalúos que a uno con 12.

Agregar `dim_perito[activo]` como color o leyenda: hay peritos inactivos con
avalúos vigentes, y eso es un hallazgo de control interno.

### Evolución entre los dos cortes

**Columnas agrupadas.** Eje: `mart_evolucion[categoria]`, Valor:
`Identificadores en la categoría`. En filtros **del visual**, dejar `CORREGIDO`,
`PERSISTENTE`, `NUEVO` y `SALIO`.

**Columnas agrupadas, no cascada.** Las cuatro cantidades son conteos de
categorías, no aumentos y disminuciones con signo de un saldo conciliado. Una
cascada con todos los valores positivos sugeriría una acumulación que no existe.

Al lado, tarjetas con `Tasa de persistencia` y
`% de salidas del incumplimiento por corrección`.

**Escribir sobre estos visuales:** *"Comparación global entre los dos cortes; no
responde a los filtros de zona ni de corte."* `mart_evolucion` está desconectada
a propósito. No agregar relaciones para forzar ese filtrado.

### Cobertura de reglas

**Matriz.** Filas `dim_regla[rule_id]`, valores `Cobertura de reglas` y
`Evaluaciones no aplicables`. Barras de datos en la cobertura, formato
porcentaje.

R-07 baja a 60,5 %: hay tipologías sin terreno valorado y esos casos son
`NO_APLICA`, no `CUMPLE`. Una regla que no aplica no es una regla que pasó.

**Título:** *"Cobertura global del corte seleccionado"*. Esta matriz responde a
corte y regla pero **no** a zona, perito ni tipología, porque
`fact_cobertura_regla` ya viene agregado por corte y regla. Es correcto, no es
una relación rota. Una regla inactiva sale vacía, que no es lo mismo que 0 %.

---

## 8. Página 3 — Lista de trabajo

> **¿Qué casos se programan este mes?**

Corresponde al último corte que procesó el almacén.

### Encabezado

- **Tarjeta ancha:** `Titular del múltiplo`. Es la conclusión del proyecto en una
  frase y va arriba de todo.
- Tarjetas: `Casos en la lista del mes`, `Casos pendientes fuera de la lista`,
  `Meses de rezago` — esta última titulada *"Meses de carga estimada con el cupo
  actual"*.

`Meses de rezago` es una razón de volumen sobre cupo (480 marcados ÷ 150 de
capacidad = 3,2 meses). No mide antigüedad real del atraso ni contempla los
casos nuevos que entren.

### Tabla de casos programados

Visual de **Tabla**, con estas columnas de `mart_lista_trabajo` en orden:
`prioridad`, `id_avaluo`, `numero_finca`, `canton`, `tipologia`,
`nivel_confiabilidad`, `accion_sugerida`, `moneda`, `saldo`, `ltv`,
`dias_antiguedad`, `reglas_incumplidas`, `detalle`, `responsables`, `perito_id`.

- En **Filtros de este objeto visual**, agregar `entra_este_mes` = `True`.
  **Solo en esta tabla, nunca a nivel de página:** si no, las tarjetas de
  pendientes quedarían recortadas por el filtro del plan mensual.
- Ordenar por `prioridad` ascendente.
- Usar **No resumir** en los campos numéricos de detalle.
- **Desactivar la fila de totales:** los saldos están en monedas distintas.
- Mostrar `ltv` como porcentaje.
- Formato condicional en `nivel_confiabilidad`: rojo `NO_CONFIABLE`, ámbar
  `REVISAR`.

### Comparación de criterios

Otra **tabla** con `mart_comparacion_priorizacion`: `criterio`, `descripcion`,
`casos_revisados`, `no_confiables_atendidos`, `no_confiables_en_cartera` y la
medida `Cobertura de priorización`.

Ordenar por `orden` y **desactivar totales**: son tres escenarios alternativos
sobre la misma cartera, no se suman.

`Cobertura de priorización` divide entre 100 el porcentaje del CSV. Sin eso,
Power BI mostraría 100 % como 10 000 %.

### Texto al pie

> Primero se programan las garantías no confiables, de mayor a menor saldo
> equivalente. Después, las que requieren verificación, con el mismo criterio. La
> selección del mes se calcula en Python y SQL; filtrar el informe no recalcula
> ni repone cupos.
>
> El orden cruza monedas con el tipo de cambio supuesto de
> `reference/parametros.csv`. Se usa solo para ordenar: ninguna cifra de
> exposición de este tablero está convertida.

No sincronizar la segmentación de corte de otras páginas con esta.

### Exportar

Menú **… del visual > Exportar datos**. En Desktop genera un CSV que se abre con
Excel. No existe un "Inicio > Exportar datos".

---

## 9. El control de cifras, a la vista

Ya está en el pie de la página 1. Agregar una **tarjeta** con `Estado del
modelo`. Que las cifras cuadren es parte del entregable, no un detalle de log.

---

## 10. Verificación

Se contrastan las cifras contra los marts que **no** se cargaron y contra
`reports/memo_ejecutivo.md`, que sale del mismo modelo por otro camino.

Con el corte en **abril 2026** y sin filtro de zona:

| Qué se mira | Debe dar |
|---|---|
| `% exposición con respaldo confiable (CRC)` | **85,9 %** |
| `% exposición con respaldo confiable (USD)` | **88,3 %** |
| `Avalúos` | **4.000** |
| `Tasa de incumplimiento` | **12,0 %** |
| `Variación de la tasa (pp)` | **−18,0 pp** |
| `Tasa global de referencia` | **12,0 %** |
| `Casos en la lista del mes` | **150** |
| `Casos pendientes fuera de la lista` | **330** |
| `Meses de rezago` | **3,2** |
| `Cobertura de priorización` (fila 1) | **100,0 %** |
| `Múltiplo de cobertura` | **4,18** |
| `Cobertura de reglas` en R-07 | **60,5 %** |
| Comprobaciones en `OK` | **11 de 11** |

Cambiando el corte a **marzo 2026**: `% exposición con respaldo confiable (CRC)`
debe dar **68,8 %**, USD **70,0 %**, y `Variación de la tasa (pp)` debe quedar
**vacía** porque no hay corte anterior.

Los desgloses completos están en `data/marts/mart_exposicion.csv`,
`mart_pareto_reglas.csv` y `mart_cobertura_reglas.csv`.

### Pruebas del comportamiento del modelo

1. Filtrar por una regla: las **incidencias** deben cambiar y
   `Valor garantía CRC` **no** debe cambiar. La regla no filtra el hecho de
   garantías.
2. Si se pone `dim_regla` junto a una medida de garantía, el mismo total se
   repite en cada fila. Es esperado por lo anterior: no sumar esas filas ni
   presentar el visual como "importe por regla". Esa repetición no prueba
   duplicación en el modelo.
3. Filtrar por cantón: incidencias y saldos deben responder por separado.
4. En la página 1, las tarjetas responden al corte y los gráficos comparativos
   conservan ambos cortes.
5. En la página 3, los casos del mes (150) más los pendientes (330) deben dar el
   total de filas del mart (480).
6. La línea del Pareto debe ser creciente y terminar en 100 %.

### Si algo no coincide

| Síntoma | Primera revisión |
|---|---|
| Los saldos son absurdamente grandes | La configuración regional del paso 1 no se aplicó |
| Los avalúos no confiables se cuentan de más | Una relación quedó bidireccional, o se creó entre los dos hechos |
| DAX no reconoce una tabla o columna | Los nombres de las consultas no coinciden con los de la tabla del paso 2 |
| `TRUE()` da error en la lista | `entra_este_mes` no quedó como Verdadero/Falso en Power Query |
| No deja marcar `dim_fecha` como tabla de fechas | Correcto: omitir ese paso, existe el miembro con fecha nula |
| Se ve un solo punto en la dispersión | Falta `id_fila_visual` en Valores/Detalles |
| El corte anterior desaparece de los gráficos | Falta Editar interacciones en la segmentación de corte |
| La cobertura no responde a zona | Correcto: es global por corte y regla |
| Evolución o lista no responden a las segmentaciones | Correcto: son tablas desconectadas con alcance propio |
| Aparece 10 000 % en la comparación | Usar `Cobertura de priorización`, que divide entre 100 |
| Rutas rotas tras mover el proyecto | Power Query > Configuración del origen de datos |

---

## 11. Cierre

En **cada página**, un cuadro de texto: **"Datos simulados. Ninguna cifra
describe una cartera real."**

1. Guardar `dashboards/cartera_garantias_dq.pbix`.
2. Capturar las tres páginas con Recortes de Windows a `dashboards/`:
   `01_exposicion.png`, `02_diagnostico.png`, `03_lista_trabajo.png`. El `.pbix`
   no se ve desde GitHub; las capturas sí.
3. Enlazar las capturas desde el `README.md`.
4. Marcar la fase 5 como completa en el `README.md` y en la sección 17 de
   `docs/MANUAL.md`.

No hace falta publicar en el servicio de Power BI para guardar el PBIX ni para
documentar el proyecto en GitHub.

### Si se regeneran los datos

Los CSV se reescriben en el mismo lugar, así que en Power BI basta **Inicio >
Actualizar**. No hay que rehacer relaciones ni medidas.

Si cambió la semilla o los parámetros: correr las etapas afectadas, reconstruir
el almacén, confirmar las once comprobaciones, regenerar el memo, actualizar en
Power BI y rehacer las capturas. `generar_memo.py` no actualiza las cifras que
estén escritas a mano en el README.
