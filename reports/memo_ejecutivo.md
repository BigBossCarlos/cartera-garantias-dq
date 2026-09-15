# Memo ejecutivo — Cartera de garantías inmobiliarias

**Asunto:** confiabilidad de los avalúos que respaldan la cartera y orden de atención  
**Cortes analizados:** marzo de 2026 y abril de 2026  
**Preparado por:** Análisis de Datos — Garantías

> **DATOS SIMULADOS.** El problema es real; la entidad, la cartera y las cifras
> son sintéticas. Ninguna cifra de este memo describe el desempeño de una
> organización existente. Ver `docs/MANUAL.md`, sección 15.

> Documento generado por `src/generar_memo.py` a partir de `data/marts/`.
> No editar a mano: se regenera con los datos.

---

## 1. La conclusión

Con la **misma capacidad de 150 avalúos al mes**, ordenar la revisión por
exposición en riesgo en vez de por antigüedad cubre **4,18 veces más saldo
expuesto**.

No es una proyección ni un ahorro estimado: son los dos ordenamientos aplicados
sobre los mismos datos del corte de abril de 2026.

| Criterio | Casos | No confiables atendidos | Exposición cubierta (CRC) | Exposición cubierta (USD) |
|---|---:|---:|---:|---:|
| Por exposición en riesgo | 150 | 140 de 140 (100,0 %) | ₡39.489,7 M | US$81,2 M |
| Por antigüedad, cartera completa | 150 | 16 de 140 (11,4 %) | ₡897,1 M | US$36,2 M |
| Por antigüedad, solo los marcados | 150 | 16 de 140 (11,4 %) | ₡897,1 M | US$36,2 M |

El criterio propuesto atiende **140 de los 140 avalúos no confiables**
del corte; el criterio actual alcanza 16 (11,4 %), porque ordena por fecha
sin mirar calidad.

La tercera fila es el control de la comparación: restringe el criterio de antigüedad
al mismo universo de 150 casos marcados. Contra esa
base el múltiplo sigue siendo 4,18, así que la
ventaja viene del orden y no de mirar una población distinta.

**El proyecto no reduce el esfuerzo de revisión: cambia el orden.** Las horas
disponibles son las mismas; lo que cambia es dónde se gastan.

---

## 2. Cuánta exposición está respaldada por avalúos confiables

Las cifras se presentan **separadas por moneda**. El proyecto no consolida cartera
a un tipo de cambio: hacerlo introduciría un supuesto que no aporta al diagnóstico.

### Colones (CRC) — corte de abril de 2026

| Nivel | Acción sugerida | Avalúos | Saldo | % del saldo | LTV promedio | Antigüedad mediana |
|---|---|---:|---:|---:|---:|---:|
| CONFIABLE | Ninguna | 2.213 | ₡1.557.083,9 M | 85,9 % | 0,62 | 258 días |
| REVISAR | Verificación documental | 232 | ₡215.771,2 M | 11,9 % | 0,81 | 658 días |
| NO_CONFIABLE | Re-inspección | 78 | ₡39.489,7 M | 2,2 % | 0,71 | 389 días |

Entre marzo de 2026 y abril de 2026 el saldo con respaldo confiable pasó de **68,8 % a 85,9 %**, y el saldo
no confiable de **5,9 % a 2,2 %**.

### Dólares (USD) — corte de abril de 2026

| Nivel | Acción sugerida | Avalúos | Saldo | % del saldo | LTV promedio | Antigüedad mediana |
|---|---|---:|---:|---:|---:|---:|
| CONFIABLE | Ninguna | 1.307 | US$1.519,2 M | 88,3 % | 0,62 | 251 días |
| REVISAR | Verificación documental | 108 | US$119,3 M | 6,9 % | 0,64 | 885 días |
| NO_CONFIABLE | Re-inspección | 62 | US$81,2 M | 4,7 % | 0,94 | 340 días |

Entre marzo de 2026 y abril de 2026 el saldo con respaldo confiable pasó de **70,0 % a 88,3 %**, y el saldo
no confiable de **7,3 % a 4,7 %**.

**Cómo leer los tres niveles.** *No confiable* es un avalúo que incumple al menos una
regla BLOQUEA: un defecto que lo invalida como respaldo y exige re-inspección.
*Revisar* incumple solo reglas REVISA: el avalúo sirve, pero hay algo que verificar
documentalmente. La distinción está declarada regla por regla en
`reference/reglas_datos.csv`, con responsable y justificación.

---

## 3. Por qué falla

En el corte de abril de 2026, **tres reglas explican 72,9 % de los
incumplimientos**. Atacar esas tres primero es lo que mueve la aguja.

| # | Regla | Dimensión | Acción | Responsable | Incidencias | % | % acumulado |
|---:|---|---|---|---|---:|---:|---:|
| 1 | **R-08** El avalúo no debe superar la vigencia de política | VIGENCIA | REVISA | Jefe de Garantías | 194 | 35,1 % | 35,1 % |
| 2 | **R-06** La coordenada debe corresponder al distrito declarado | INTEGRIDAD | REVISA | Perito Revisor | 121 | 21,9 % | 57,0 % |
| 3 | **R-07** El valor por m² de terreno debe estar dentro del rango de la zona | PLAUSIBILIDAD | REVISA | Perito Revisor | 88 | 15,9 % | 72,9 % |
| 4 | **R-03** El valor total debe cuadrar con la suma de sus componentes | CONSISTENCIA | BLOQUEA | Perito Revisor | 54 | 9,8 % | 82,6 % |
| 5 | **R-02** Los campos obligatorios deben venir informados | COMPLETITUD | BLOQUEA | Coordinación de Calidad | 37 | 6,7 % | 89,3 % |
| 6 | **R-04** La tipología y lo construido deben ser compatibles | CONSISTENCIA | BLOQUEA | Perito Revisor | 26 | 4,7 % | 94,0 % |
| 7 | **R-05** Las fechas deben tener orden lógico | CRONOLOGIA | BLOQUEA | Coordinación de Calidad | 17 | 3,1 % | 97,1 % |
| 8 | **R-01** No pueden existir dos avalúos con el mismo identificador | UNICIDAD | BLOQUEA | Coordinación de Calidad | 16 | 2,9 % | 100,0 % |

La regla dominante es **R-08 — el avalúo no debe superar la vigencia de política**, con 194 incidencias (35,1 %).
Es una regla REVISA y su responsable declarado en el catálogo es **Jefe de Garantías**.

### Dónde se concentra

- **CRC:** tres cantones concentran 63,1 % de la exposición no confiable — San Ramón (Alajuela), Talamanca (Limón), Sarapiquí (Heredia).
- **USD:** tres cantones concentran 49,5 % de la exposición no confiable — Belén (Heredia), Tibás (San José), Curridabat (San José).

La concentración es la razón por la que una lista de trabajo ordenada por exposición
funciona: el problema no está repartido de forma uniforme por el país.

### Por perito

La tasa de incumplimiento va de 6,0 % a 100,0 % entre los 10 peritos del corte.
Es un insumo de **diagnóstico y capacitación, no de sanción**: con dos cortes no hay
serie suficiente para atribuir desempeño, y el volumen por perito es desigual.

Atención: 1 perito(s) marcados como **inactivos** siguen
apareciendo como autores de avalúos vigentes en la cartera. Es un hallazgo de
control interno, independiente de la calidad de esos avalúos.

---

## 4. Cómo evolucionó entre cortes

Los 4.192 identificadores presentes en alguno de los dos cortes se clasifican
sin residuo. Las categorías separan **corrección real** de **rotación de cartera**: un
avalúo que desaparece porque se canceló el crédito no es una mejora de calidad.

| Categoría | Avalúos | Qué significa |
|---|---:|---|
| CUMPLE | 2.611 | Cumplía en ambos cortes |
| CORREGIDO | 708 | Incumplía en marzo de 2026, cumple en abril de 2026 |
| PERSISTENTE | 354 | Incumplía antes y sigue incumpliendo |
| NUEVO | 118 | Cumplía antes y ahora incumple |
| ENTRA_CUMPLIENDO | 201 | Entró a la cartera sin incumplimientos |
| SALIO | 118 | Salió de la cartera incumpliendo |
| SALIO_CUMPLIENDO | 82 | Salió de la cartera cumpliendo |

De los 1.180 avalúos que incumplían en marzo de 2026, **708 se corrigieron y 354 persisten**:
una tasa de persistencia de 33,3 % entre los que siguieron en cartera.

Los 118 casos **NUEVO** son la señal que conviene vigilar: avalúos que cumplían
y dejaron de cumplir. La causa más común es el paso del tiempo contra la vigencia de
política, que no requiere que nadie haga nada mal para activarse.

---

## 5. Qué hacer este mes

La lista de trabajo del corte de abril de 2026 tiene **150 casos**, el
tope de capacidad declarado en `reference/parametros.csv`. El orden es lexicográfico
y deliberado:

1. Primero **todos** los *No confiable*, por saldo descendente.
2. Después los *Revisar*, por saldo descendente.

Sin índices ponderados. Cualquier peso inventado habría que defenderlo después; este
orden se explica en una frase.

| Composición | Casos | Acción |
|---|---:|---|
| NO_CONFIABLE | 140 | Re-inspección |
| REVISAR | 10 | Verificación documental |

### Los diez primeros

| # | Avalúo | Cantón | Tipología | Nivel | Moneda | Saldo | Reglas | Responsable |
|---:|---|---|---|---|---|---:|---|---|
| 1 | AV-2025-003808 | San Ramón | Finca agrícola | NO_CONFIABLE | CRC | ₡19.590,0 M | R-02 | Coordinación de Calidad |
| 2 | AV-2025-003629 | Belén | Bodega o nave industrial | NO_CONFIABLE | USD | US$14,6 M | R-03, R-04, R-08 | Jefe de Garantías, Perito Revisor |
| 3 | AV-2024-000859 | Tibás | Edificio de oficinas | NO_CONFIABLE | USD | US$13,9 M | R-02, R-08 | Coordinación de Calidad, Jefe de Garantías |
| 4 | AV-2025-000063 | Curridabat | Edificio de oficinas | NO_CONFIABLE | USD | US$9,6 M | R-02 | Coordinación de Calidad |
| 5 | AV-2024-002074 | Carrillo | Terreno baldío rural | NO_CONFIABLE | USD | US$5,8 M | R-03 | Perito Revisor |
| 6 | AV-2024-002891 | Talamanca | Terreno baldío rural | NO_CONFIABLE | CRC | ₡2.882,7 M | R-04 | Perito Revisor |
| 7 | AV-2025-000013 | Escazú | Edificio de oficinas | NO_CONFIABLE | USD | US$5,6 M | R-02, R-08 | Jefe de Garantías, Coordinación de Calidad |
| 8 | AV-2024-001603 | Santa Ana | Bodega o nave industrial | NO_CONFIABLE | USD | US$5,3 M | R-03, R-04 | Perito Revisor |
| 9 | AV-2025-002445 | Alajuela | Edificio de oficinas | NO_CONFIABLE | USD | US$4,9 M | R-02 | Coordinación de Calidad |
| 10 | AV-2024-000942 | Sarapiquí | Finca agrícola | NO_CONFIABLE | CRC | ₡2.176,4 M | R-03, R-07 | Perito Revisor |

La lista completa está en `data/marts/mart_lista_trabajo.csv` y en la tercera página
del tablero, exportable a Excel desde Power BI.

**Nota sobre el orden.** El ordenamiento cruza monedas usando el tipo de cambio de
`reference/parametros.csv`, que es un supuesto declarado. Se usa **solo para ordenar**:
ninguna cifra de exposición de este memo está convertida.

---

## 6. Por qué se puede confiar en estas cifras

El modelo se reconcilia contra sus propias fuentes en 11 comprobaciones.
Si alguna falla, ni el almacén ni este memo se publican.

| # | Comprobación | Esperado | Obtenido | Resultado |
|---:|---|---:|---:|---|
| 1 | Avalúos: validador = fact_garantia | 8.000 | 8.000 | OK |
| 2 | fact_garantia: grano sin duplicados | 8.000 | 8.000 | OK |
| 3 | Incidencias: validador = fact_incidencia | 1.993 | 1.993 | OK |
| 4 | No confiables: validador = modelo | 460 | 460 | OK |
| 5 | A revisar: validador = modelo | 1.220 | 1.220 | OK |
| 6 | Geografía sin resolver (esperado 0) | 0 | 0 | OK |
| 7 | Tipología sin resolver (esperado 0) | 0 | 0 | OK |
| 8 | Saldo del hecho = saldo de créditos atribuibles | 3.593.576.392.818 | 3.593.576.392.818 | OK |
| 9 | Cobertura: avalúos x reglas activas | 64.000 | 64.000 | OK |
| 10 | Evolución: identificadores clasificados | 4.192 | 4.192 | OK |
| 11 | Incidencias bloqueantes = suma de n_bloquea | 489 | 489 | OK |

### Cobertura de cada regla

Una regla puede no aplicar a un avalúo: R-07 mide el valor por m² de terreno, y hay
tipologías sin terreno valorado. Esos casos se marcan **NO_APLICA**, no CUMPLE. La
diferencia importa: una regla que no aplica no es una regla que pasó.

| Regla | Evaluados | Incumple | No aplica | % evaluado |
|---|---:|---:|---:|---:|
| R-07 El valor por m² de terreno debe estar dentro del rango de la zona | 2.421 | 88 | 1.579 | 60,5 % |
| R-04 La tipología y lo construido deben ser compatibles | 3.802 | 26 | 198 | 95,0 % |
| R-03 El valor total debe cuadrar con la suma de sus componentes | 3.988 | 54 | 12 | 99,7 % |
| R-05 Las fechas deben tener orden lógico | 3.990 | 17 | 10 | 99,8 % |

Las otras 4 reglas activas se evaluaron sobre el 100 % de los avalúos
del corte. Ninguna regla se salta registros en silencio: lo que no se evalúa queda
contado y declarado.

### Lo que queda fuera del cruce

No todo el saldo de la cartera se puede atribuir a un avalúo. Se declara en vez de
repartirlo con un supuesto:

| Motivo | Moneda | Créditos | Saldo sin atribuir |
|---|---|---:|---:|
| Identificador compartido por varios avalúos | CRC | 4 | ₡19.104,3 M |
| Identificador compartido por varios avalúos | USD | 3 | US$1,3 M |
| Sin avalúo correspondiente en el corte | CRC | 5 | ₡2.968,3 M |
| Sin avalúo correspondiente en el corte | USD | 3 | US$0,5 M |

---

## 7. Limitaciones de este análisis

1. **Los datos son sintéticos.** El generador define los defectos que el validador
   busca. Detectarlos todos verifica que el código es correcto, no que el sistema
   encontraría errores que nadie anticipó.
2. **Las tasas de incumplimiento y de corrección son parámetros de diseño**, no
   observaciones de campo.
3. **La validación geográfica es aproximada:** distancia al centroide del distrito
   contra un radio declarado, no pertenencia a un polígono.
4. **Los rangos de valor unitario son ilustrativos.** No son una tabla de valores de
   mercado.
5. **No se consolida cartera entre monedas.** El tipo de cambio se usa únicamente
   para ordenar la lista de trabajo.
6. **Dos cortes no son una serie.** Permiten comparar, no proyectar tendencia.

El detalle completo está en `docs/MANUAL.md`, sección 15.

---

## 8. Recomendaciones

1. **Adoptar el orden por exposición en riesgo** para la lista mensual de revisión.
   Es el cambio de mayor efecto y no requiere presupuesto adicional.
2. **Atacar primero las tres reglas del Pareto.** Concentran la mayoría de los
   incumplimientos y tienen responsable identificado en el catálogo.
3. **Vigilar la categoría NUEVO entre cortes.** Un avalúo que deja de cumplir sin que
   nadie lo toque es un problema de proceso, no de un perito.
4. **Revisar el control interno de peritos inactivos** con avalúos vigentes en cartera.
5. **Sustituir los parámetros supuestos por los reales** —tipo de cambio de referencia,
   capacidad del equipo, costo de re-inspección— antes de usar esto para decidir.

