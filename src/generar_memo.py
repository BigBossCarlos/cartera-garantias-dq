"""
generar_memo.py — Redacta el memo ejecutivo a partir de los marts.

Lee los CSV de data/marts/ y escribe reports/memo_ejecutivo.md. No recalcula
nada: toda cifra del memo sale de un mart que ya pasó la reconciliación de
sql/05_control.sql. Si una comprobación del almacén no cuadra, no publica.

Por qué un script y no un documento escrito a mano
--------------------------------------------------
Si se regeneran los datos con otra semilla, el memo se regenera con ellos. Una
cifra tecleada a mano quedaría vieja sin que nadie lo note.

Sobre las monedas
-----------------
La exposición se reporta SIEMPRE segmentada por moneda. El único número que
mezcla CRC y USD es el de mart_comparacion_priorizacion, que usa el tipo de
cambio de reference/parametros.csv para ORDENAR la lista de trabajo y producir
una razón adimensional. Ver docs/MANUAL.md, sección 15, limitación 5.

Uso
---
    python src/generar_memo.py

Salidas
-------
reports/memo_ejecutivo.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
MARTS = RAIZ / "data" / "marts"
REPORTS = RAIZ / "reports"
SALIDA = REPORTS / "memo_ejecutivo.md"

SIMBOLO = {"CRC": "₡", "USD": "US$"}
NOMBRE_MES = {"01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
              "05": "mayo", "06": "junio", "07": "julio", "08": "agosto",
              "09": "setiembre", "10": "octubre", "11": "noviembre", "12": "diciembre"}

NECESARIOS = ["control_almacen", "mart_exposicion", "mart_pareto_reglas",
              "mart_concentracion", "mart_evolucion", "mart_lista_trabajo",
              "mart_comparacion_priorizacion", "mart_perito",
              "mart_credito_no_atribuible", "mart_cobertura_reglas"]


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------

def num(x, dec: int = 0) -> str:
    """Formato costarricense: punto para miles, coma para decimales."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def millones(x: float, moneda: str) -> str:
    """Los saldos en colones llegan a los billones. Se reportan en millones."""
    return f"{SIMBOLO[moneda]}{num(x / 1_000_000, 1)} M"


def pct(x: float, dec: int = 1) -> str:
    return f"{num(x, dec)} %"


def mes_largo(corte: str) -> str:
    anio, mes = corte.split("-")
    return f"{NOMBRE_MES[mes]} de {anio}"


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def cargar() -> dict:
    faltan = [n for n in NECESARIOS if not (MARTS / f"{n}.csv").exists()]
    if faltan:
        sys.exit(f"Faltan marts: {faltan}\nCorré primero: python src/construir_almacen.py")

    datos = {n: pd.read_csv(MARTS / f"{n}.csv", encoding="utf-8") for n in NECESARIOS}

    control = datos["control_almacen"]
    fallidas = control[control["resultado"] != "OK"]
    if not fallidas.empty:
        print(fallidas.to_string(index=False))
        sys.exit(f"\n{len(fallidas)} comprobaciones del almacén no cuadran. "
                 f"El memo no se publica.")

    return datos


# ---------------------------------------------------------------------------
# Secciones
# ---------------------------------------------------------------------------

def encabezado(actual: str, anterior: str) -> list:
    return [
        "# Memo ejecutivo — Cartera de garantías inmobiliarias",
        "",
        "**Asunto:** confiabilidad de los avalúos que respaldan la cartera y orden de atención  ",
        f"**Cortes analizados:** {mes_largo(anterior)} y {mes_largo(actual)}  ",
        "**Preparado por:** Análisis de Datos — Garantías",
        "",
        "> **DATOS SIMULADOS.** El problema es real; la entidad, la cartera y las cifras",
        "> son sintéticas. Ninguna cifra de este memo describe el desempeño de una",
        "> organización existente. Ver `docs/MANUAL.md`, sección 15.",
        "",
        "> Documento generado por `src/generar_memo.py` a partir de `data/marts/`.",
        "> No editar a mano: se regenera con los datos.",
        "",
        "---",
        "",
    ]


def seccion_conclusion(datos: dict, actual: str) -> list:
    comp = datos["mart_comparacion_priorizacion"].sort_values("orden")
    propuesto = comp.iloc[0]
    criterio_actual = comp[comp["criterio"].str.contains("cartera completa")].iloc[0]
    mismo_universo = comp[comp["criterio"].str.contains("solo los marcados")].iloc[0]

    casos = int(propuesto["casos_revisados"])
    veces = propuesto["veces_vs_criterio_actual"]

    lineas = [
        "## 1. La conclusión",
        "",
        f"Con la **misma capacidad de {num(casos)} avalúos al mes**, ordenar la revisión por",
        f"exposición en riesgo en vez de por antigüedad cubre **{num(veces, 2)} veces más saldo",
        "expuesto**.",
        "",
        "No es una proyección ni un ahorro estimado: son los dos ordenamientos aplicados",
        f"sobre los mismos datos del corte de {mes_largo(actual)}.",
        "",
        "| Criterio | Casos | No confiables atendidos | Exposición cubierta (CRC) | Exposición cubierta (USD) |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, f in comp.iterrows():
        lineas.append(
            f"| {f['criterio']} | {num(f['casos_revisados'])} | "
            f"{num(f['no_confiables_atendidos'])} de {num(f['no_confiables_en_cartera'])} "
            f"({pct(f['pct_no_confiables_cubiertos'])}) | "
            f"{millones(f['exposicion_cubierta_crc'], 'CRC')} | "
            f"{millones(f['exposicion_cubierta_usd'], 'USD')} |"
        )

    lineas += [
        "",
        f"El criterio propuesto atiende **{num(propuesto['no_confiables_atendidos'])} de los "
        f"{num(propuesto['no_confiables_en_cartera'])} avalúos no confiables**",
        f"del corte; el criterio actual alcanza {num(criterio_actual['no_confiables_atendidos'])} "
        f"({pct(criterio_actual['pct_no_confiables_cubiertos'])}), porque ordena por fecha",
        "sin mirar calidad.",
        "",
        "La tercera fila es el control de la comparación: restringe el criterio de antigüedad",
        f"al mismo universo de {num(mismo_universo['casos_revisados'])} casos marcados. Contra esa",
        f"base el múltiplo sigue siendo {num(propuesto['veces_vs_mismo_universo'], 2)}, así que la",
        "ventaja viene del orden y no de mirar una población distinta.",
        "",
        "**El proyecto no reduce el esfuerzo de revisión: cambia el orden.** Las horas",
        "disponibles son las mismas; lo que cambia es dónde se gastan.",
        "",
        "---",
        "",
    ]
    return lineas


def seccion_exposicion(datos: dict, actual: str, anterior: str) -> list:
    exp = datos["mart_exposicion"]
    orden = {"CONFIABLE": 0, "REVISAR": 1, "NO_CONFIABLE": 2}

    lineas = [
        "## 2. Cuánta exposición está respaldada por avalúos confiables",
        "",
        "Las cifras se presentan **separadas por moneda**. El proyecto no consolida cartera",
        "a un tipo de cambio: hacerlo introduciría un supuesto que no aporta al diagnóstico.",
        "",
    ]

    for moneda in sorted(exp["moneda"].unique()):
        bloque = exp[(exp["corte"] == actual) & (exp["moneda"] == moneda)]
        bloque = bloque.sort_values("nivel_confiabilidad", key=lambda s: s.map(orden))
        prev = exp[(exp["corte"] == anterior) & (exp["moneda"] == moneda)]

        lineas += [
            f"### {'Colones' if moneda == 'CRC' else 'Dólares'} ({moneda}) — corte de {mes_largo(actual)}",
            "",
            "| Nivel | Acción sugerida | Avalúos | Saldo | % del saldo | LTV promedio | Antigüedad mediana |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for _, f in bloque.iterrows():
            lineas.append(
                f"| {f['nivel_confiabilidad']} | {f['accion_sugerida']} | {num(f['avaluos'])} | "
                f"{millones(f['saldo'], moneda)} | {pct(f['pct_saldo_del_corte'])} | "
                f"{num(f['ltv_promedio'], 2)} | {num(f['dias_antiguedad_mediana'])} días |"
            )

        def p(df, nivel):
            fila = df[df["nivel_confiabilidad"] == nivel]["pct_saldo_del_corte"]
            return fila.iloc[0] if len(fila) else 0.0

        lineas += [
            "",
            f"Entre {mes_largo(anterior)} y {mes_largo(actual)} el saldo con respaldo confiable pasó de "
            f"**{pct(p(prev, 'CONFIABLE'))} a {pct(p(bloque, 'CONFIABLE'))}**, y el saldo",
            f"no confiable de **{pct(p(prev, 'NO_CONFIABLE'))} a {pct(p(bloque, 'NO_CONFIABLE'))}**.",
            "",
        ]

    lineas += [
        "**Cómo leer los tres niveles.** *No confiable* es un avalúo que incumple al menos una",
        "regla BLOQUEA: un defecto que lo invalida como respaldo y exige re-inspección.",
        "*Revisar* incumple solo reglas REVISA: el avalúo sirve, pero hay algo que verificar",
        "documentalmente. La distinción está declarada regla por regla en",
        "`reference/reglas_datos.csv`, con responsable y justificación.",
        "",
        "---",
        "",
    ]
    return lineas


def seccion_diagnostico(datos: dict, actual: str) -> list:
    par = datos["mart_pareto_reglas"]
    bloque = par[par["corte"] == actual].sort_values("ranking")
    acum_tres = bloque.head(3)["pct_acumulado"].iloc[-1]

    lineas = [
        "## 3. Por qué falla",
        "",
        f"En el corte de {mes_largo(actual)}, **tres reglas explican {pct(acum_tres)} de los",
        "incumplimientos**. Atacar esas tres primero es lo que mueve la aguja.",
        "",
        "| # | Regla | Dimensión | Acción | Responsable | Incidencias | % | % acumulado |",
        "|---:|---|---|---|---|---:|---:|---:|",
    ]
    for _, f in bloque.iterrows():
        lineas.append(
            f"| {f['ranking']} | **{f['rule_id']}** {f['nombre']} | {f['dimension']} | "
            f"{f['accion']} | {f['responsable']} | {num(f['incidencias'])} | "
            f"{pct(f['pct'])} | {pct(f['pct_acumulado'])} |"
        )

    primera = bloque.iloc[0]
    lineas += [
        "",
        f"La regla dominante es **{primera['rule_id']} — {primera['nombre'].lower()}**, con "
        f"{num(primera['incidencias'])} incidencias ({pct(primera['pct'])}).",
        f"Es una regla {primera['accion']} y su responsable declarado en el catálogo es "
        f"**{primera['responsable']}**.",
        "",
        "### Dónde se concentra",
        "",
    ]

    con = datos["mart_concentracion"]
    for moneda in sorted(con["moneda"].unique()):
        b = con[(con["corte"] == actual) & (con["moneda"] == moneda)]
        total = b["exposicion_no_confiable"].sum()
        if total <= 0:
            continue
        top = b.nlargest(3, "exposicion_no_confiable")
        share = 100 * top["exposicion_no_confiable"].sum() / total
        cantones = ", ".join(f"{f['canton']} ({f['provincia']})" for _, f in top.iterrows())
        lineas.append(f"- **{moneda}:** tres cantones concentran {pct(share)} de la exposición "
                      f"no confiable — {cantones}.")

    lineas += [
        "",
        "La concentración es la razón por la que una lista de trabajo ordenada por exposición",
        "funciona: el problema no está repartido de forma uniforme por el país.",
        "",
        "### Por perito",
        "",
    ]

    per = datos["mart_perito"]
    bp = per[per["corte"] == actual].sort_values("tasa_incumplimiento", ascending=False)
    lineas += [
        f"La tasa de incumplimiento va de {pct(bp.iloc[-1]['tasa_incumplimiento'])} a "
        f"{pct(bp.iloc[0]['tasa_incumplimiento'])} entre los {num(len(bp))} peritos del corte.",
        "Es un insumo de **diagnóstico y capacitación, no de sanción**: con dos cortes no hay",
        "serie suficiente para atribuir desempeño, y el volumen por perito es desigual.",
        "",
    ]

    inactivos = bp[bp["activo"] == "NO"]
    if not inactivos.empty:
        lineas += [
            f"Atención: {num(len(inactivos))} perito(s) marcados como **inactivos** siguen",
            "apareciendo como autores de avalúos vigentes en la cartera. Es un hallazgo de",
            "control interno, independiente de la calidad de esos avalúos.",
            "",
        ]

    lineas += ["---", ""]
    return lineas


def seccion_evolucion(datos: dict, actual: str, anterior: str) -> list:
    evo = datos["mart_evolucion"]
    c = evo["categoria"].value_counts().to_dict()

    corregido = c.get("CORREGIDO", 0)
    persistente = c.get("PERSISTENTE", 0)
    nuevo = c.get("NUEVO", 0)
    salio = c.get("SALIO", 0)
    defectuosos = corregido + persistente + salio
    persistencia = 100 * persistente / (corregido + persistente) if corregido + persistente else 0

    return [
        "## 4. Cómo evolucionó entre cortes",
        "",
        f"Los {num(len(evo))} identificadores presentes en alguno de los dos cortes se clasifican",
        "sin residuo. Las categorías separan **corrección real** de **rotación de cartera**: un",
        "avalúo que desaparece porque se canceló el crédito no es una mejora de calidad.",
        "",
        "| Categoría | Avalúos | Qué significa |",
        "|---|---:|---|",
        f"| CUMPLE | {num(c.get('CUMPLE', 0))} | Cumplía en ambos cortes |",
        f"| CORREGIDO | {num(corregido)} | Incumplía en {mes_largo(anterior)}, cumple en {mes_largo(actual)} |",
        f"| PERSISTENTE | {num(persistente)} | Incumplía antes y sigue incumpliendo |",
        f"| NUEVO | {num(nuevo)} | Cumplía antes y ahora incumple |",
        f"| ENTRA_CUMPLIENDO | {num(c.get('ENTRA_CUMPLIENDO', 0))} | Entró a la cartera sin incumplimientos |",
        f"| SALIO | {num(salio)} | Salió de la cartera incumpliendo |",
        f"| SALIO_CUMPLIENDO | {num(c.get('SALIO_CUMPLIENDO', 0))} | Salió de la cartera cumpliendo |",
        "",
        f"De los {num(defectuosos)} avalúos que incumplían en {mes_largo(anterior)}, "
        f"**{num(corregido)} se corrigieron y {num(persistente)} persisten**:",
        f"una tasa de persistencia de {pct(persistencia)} entre los que siguieron en cartera.",
        "",
        f"Los {num(nuevo)} casos **NUEVO** son la señal que conviene vigilar: avalúos que cumplían",
        "y dejaron de cumplir. La causa más común es el paso del tiempo contra la vigencia de",
        "política, que no requiere que nadie haga nada mal para activarse.",
        "",
        "---",
        "",
    ]


def seccion_lista(datos: dict, actual: str) -> list:
    lt = datos["mart_lista_trabajo"]
    bloque = lt[(lt["corte"] == actual) & (lt["entra_este_mes"])]
    no_conf = bloque[bloque["nivel_confiabilidad"] == "NO_CONFIABLE"]
    revisar = bloque[bloque["nivel_confiabilidad"] == "REVISAR"]

    lineas = [
        "## 5. Qué hacer este mes",
        "",
        f"La lista de trabajo del corte de {mes_largo(actual)} tiene **{num(len(bloque))} casos**, el",
        "tope de capacidad declarado en `reference/parametros.csv`. El orden es lexicográfico",
        "y deliberado:",
        "",
        "1. Primero **todos** los *No confiable*, por saldo descendente.",
        "2. Después los *Revisar*, por saldo descendente.",
        "",
        "Sin índices ponderados. Cualquier peso inventado habría que defenderlo después; este",
        "orden se explica en una frase.",
        "",
        "| Composición | Casos | Acción |",
        "|---|---:|---|",
        f"| NO_CONFIABLE | {num(len(no_conf))} | Re-inspección |",
        f"| REVISAR | {num(len(revisar))} | Verificación documental |",
        "",
        "### Los diez primeros",
        "",
        "| # | Avalúo | Cantón | Tipología | Nivel | Moneda | Saldo | Reglas | Responsable |",
        "|---:|---|---|---|---|---|---:|---|---|",
    ]
    for _, f in bloque.nsmallest(10, "prioridad").iterrows():
        lineas.append(
            f"| {f['prioridad']} | {f['id_avaluo']} | {f['canton']} | {f['tipologia']} | "
            f"{f['nivel_confiabilidad']} | {f['moneda']} | {millones(f['saldo'], f['moneda'])} | "
            f"{f['reglas_incumplidas']} | {f['responsables']} |"
        )

    lineas += [
        "",
        "La lista completa está en `data/marts/mart_lista_trabajo.csv` y en la tercera página",
        "del tablero, exportable a Excel desde Power BI.",
        "",
        "**Nota sobre el orden.** El ordenamiento cruza monedas usando el tipo de cambio de",
        "`reference/parametros.csv`, que es un supuesto declarado. Se usa **solo para ordenar**:",
        "ninguna cifra de exposición de este memo está convertida.",
        "",
        "---",
        "",
    ]
    return lineas


def seccion_control(datos: dict, actual: str) -> list:
    control = datos["control_almacen"]
    cob = datos["mart_cobertura_reglas"]
    na = datos["mart_credito_no_atribuible"]

    lineas = [
        "## 6. Por qué se puede confiar en estas cifras",
        "",
        f"El modelo se reconcilia contra sus propias fuentes en {num(len(control))} comprobaciones.",
        "Si alguna falla, ni el almacén ni este memo se publican.",
        "",
        "| # | Comprobación | Esperado | Obtenido | Resultado |",
        "|---:|---|---:|---:|---|",
    ]
    for _, f in control.iterrows():
        lineas.append(
            f"| {f['orden']} | {f['comprobacion']} | {num(f['esperado'])} | "
            f"{num(f['obtenido'])} | {f['resultado']} |"
        )

    bloque_cob = cob[cob["corte"] == actual].sort_values("pct_cobertura")
    parciales = bloque_cob[bloque_cob["no_aplica"] > 0]

    lineas += [
        "",
        "### Cobertura de cada regla",
        "",
        "Una regla puede no aplicar a un avalúo: R-07 mide el valor por m² de terreno, y hay",
        "tipologías sin terreno valorado. Esos casos se marcan **NO_APLICA**, no CUMPLE. La",
        "diferencia importa: una regla que no aplica no es una regla que pasó.",
        "",
    ]
    if parciales.empty:
        lineas += ["Las reglas activas se evaluaron sobre el total de los avalúos del corte.", ""]
    else:
        lineas += [
            "| Regla | Evaluados | Incumple | No aplica | % evaluado |",
            "|---|---:|---:|---:|---:|",
        ]
        for _, f in parciales.iterrows():
            lineas.append(
                f"| {f['rule_id']} {f['nombre']} | {num(f['cumple'] + f['incumple'])} | "
                f"{num(f['incumple'])} | {num(f['no_aplica'])} | {pct(f['pct_cobertura'])} |"
            )
        completas = len(bloque_cob) - len(parciales)
        lineas += [
            "",
            f"Las otras {num(completas)} reglas activas se evaluaron sobre el 100 % de los avalúos",
            "del corte. Ninguna regla se salta registros en silencio: lo que no se evalúa queda",
            "contado y declarado.",
            "",
        ]

    bloque_na = na[na["corte"] == actual]
    if not bloque_na.empty:
        lineas += [
            "### Lo que queda fuera del cruce",
            "",
            "No todo el saldo de la cartera se puede atribuir a un avalúo. Se declara en vez de",
            "repartirlo con un supuesto:",
            "",
            "| Motivo | Moneda | Créditos | Saldo sin atribuir |",
            "|---|---|---:|---:|",
        ]
        for _, f in bloque_na.sort_values(["motivo", "moneda"]).iterrows():
            lineas.append(
                f"| {f['motivo']} | {f['moneda']} | {num(f['creditos'])} | "
                f"{millones(f['saldo_sin_atribuir'], f['moneda'])} |"
            )
        lineas += [""]

    lineas += ["---", ""]
    return lineas


def seccion_cierre() -> list:
    return [
        "## 7. Limitaciones de este análisis",
        "",
        "1. **Los datos son sintéticos.** El generador define los defectos que el validador",
        "   busca. Detectarlos todos verifica que el código es correcto, no que el sistema",
        "   encontraría errores que nadie anticipó.",
        "2. **Las tasas de incumplimiento y de corrección son parámetros de diseño**, no",
        "   observaciones de campo.",
        "3. **La validación geográfica es aproximada:** distancia al centroide del distrito",
        "   contra un radio declarado, no pertenencia a un polígono.",
        "4. **Los rangos de valor unitario son ilustrativos.** No son una tabla de valores de",
        "   mercado.",
        "5. **No se consolida cartera entre monedas.** El tipo de cambio se usa únicamente",
        "   para ordenar la lista de trabajo.",
        "6. **Dos cortes no son una serie.** Permiten comparar, no proyectar tendencia.",
        "",
        "El detalle completo está en `docs/MANUAL.md`, sección 15.",
        "",
        "---",
        "",
        "## 8. Recomendaciones",
        "",
        "1. **Adoptar el orden por exposición en riesgo** para la lista mensual de revisión.",
        "   Es el cambio de mayor efecto y no requiere presupuesto adicional.",
        "2. **Atacar primero las tres reglas del Pareto.** Concentran la mayoría de los",
        "   incumplimientos y tienen responsable identificado en el catálogo.",
        "3. **Vigilar la categoría NUEVO entre cortes.** Un avalúo que deja de cumplir sin que",
        "   nadie lo toque es un problema de proceso, no de un perito.",
        "4. **Revisar el control interno de peritos inactivos** con avalúos vigentes en cartera.",
        "5. **Sustituir los parámetros supuestos por los reales** —tipo de cambio de referencia,",
        "   capacidad del equipo, costo de re-inspección— antes de usar esto para decidir.",
        "",
    ]


# ---------------------------------------------------------------------------

def main():
    datos = cargar()

    cortes = sorted(datos["mart_exposicion"]["corte"].unique())
    if len(cortes) < 2:
        sys.exit(f"Se esperaban dos cortes en mart_exposicion, hay {len(cortes)}: {cortes}")
    anterior, actual = cortes[-2], cortes[-1]

    lineas = []
    lineas += encabezado(actual, anterior)
    lineas += seccion_conclusion(datos, actual)
    lineas += seccion_exposicion(datos, actual, anterior)
    lineas += seccion_diagnostico(datos, actual)
    lineas += seccion_evolucion(datos, actual, anterior)
    lineas += seccion_lista(datos, actual)
    lineas += seccion_control(datos, actual)
    lineas += seccion_cierre()

    REPORTS.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    print(f"Memo escrito en {SALIDA.relative_to(RAIZ)}")
    print(f"  cortes          {anterior} -> {actual}")
    print(f"  lineas          {len(lineas)}")
    print(f"  comprobaciones  {len(datos['control_almacen'])} OK")


if __name__ == "__main__":
    main()
