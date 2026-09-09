"""
validar.py — Aplica las reglas de calidad a los cortes de la cartera.

El catálogo manda: este script lee reference/reglas_datos.csv y aplica
únicamente las reglas marcadas como activas. Activar R-09 o R-10 es cambiar
una celda del CSV, no tocar código.

Salidas (en data/output/)
-------------------------
avaluos_validados.csv   una fila por avalúo y corte, con el resultado de cada regla
incidencias.csv         una fila por incumplimiento detectado
control_cifras.csv      una fila por corte, para verificar que nada se perdió

Uso
---
    python src/validar.py

Tres resultados posibles por regla y avalúo:
    CUMPLE      la regla se evaluó y el dato pasó
    INCUMPLE    la regla se evaluó y el dato falló
    NO_APLICA   la regla no pudo evaluarse

NO_APLICA no es CUMPLE. Un avalúo sin rango de referencia para su zona no
"pasó" R-07: nadie pudo opinar. Contarlo como aprobado inflaría la tasa de
confiabilidad con registros que nunca se revisaron.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
REF = RAIZ / "reference"
RAW = RAIZ / "data" / "raw"
OUT = RAIZ / "data" / "output"

CUMPLE, INCUMPLE, NO_APLICA = "CUMPLE", "INCUMPLE", "NO_APLICA"

# --- Parámetros de negocio. Ver docs/diccionario_datos.md, sección 6. ---------
PASO_REDONDEO = {"CRC": 1000, "USD": 1}          # R-03
MAX_DIAS_INSPECCION_A_VALOR = 30                 # R-05
MAX_DIAS_VALOR_A_INFORME = 15                    # R-05
VIGENCIA_MESES = 24                              # R-08
LAT_MIN, LAT_MAX = 8.0, 11.3                     # R-06
LON_MIN, LON_MAX = -86.0, -82.5                  # R-06

VALORES_AUSENTES = {"", "N/A", "n/a", "NA", "null", "NULL", "-"}

CAMPOS_OBLIGATORIOS = [
    "id_avaluo", "numero_finca", "finalidad", "fecha_inspeccion", "fecha_valor", "fecha_informe",
    "provincia", "canton", "distrito", "latitud", "longitud", "tipologia_inmueble", "moneda",
    "area_terreno_m2", "valor_unitario_terreno_m2", "area_construccion_m2",
    "valor_obras_complementarias", "valor_total_inmueble", "perito_id",
]
# valor_unitario_construccion_m2 es de obligatoriedad condicional: se trata aparte.

CORTES_FIN_DE_MES = {"2026-03": "2026-03-31", "2026-04": "2026-04-30"}


# =============================================================================
# UTILIDADES DE LECTURA
# =============================================================================
def es_ausente(serie: pd.Series) -> pd.Series:
    """Vacío, espacios y marcadores como N/A cuentan como ausencia."""
    return serie.astype(str).str.strip().isin(VALORES_AUSENTES)


def a_numero(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce")


def a_fecha(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, errors="coerce", format="%Y-%m-%d")


def resultado(indice, estado=NO_APLICA) -> pd.DataFrame:
    """Esqueleto que devuelve toda regla: un estado y el detalle de la incidencia."""
    return pd.DataFrame({"estado": estado, "campo": "", "valor_observado": "",
                         "condicion_esperada": ""}, index=indice)


def haversine(lat1, lon1, lat2, lon2):
    """Distancia en km. Vectorizada."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


# =============================================================================
# CONTEXTO: referencias y datos enriquecidos
# =============================================================================
class Contexto:
    """Tablas de referencia y columnas derivadas del cruce.

    El orden importa: tipar, enriquecer, y recién después evaluar. Las reglas
    R-04 y R-07 dependen de columnas que no vienen en el archivo de entrada y
    solo existen tras el cruce con las referencias.
    """

    def __init__(self, carpeta: Path):
        self.reglas = pd.read_csv(carpeta / "reglas_datos.csv", encoding="utf-8")
        self.geografia = pd.read_csv(carpeta / "geografia.csv", encoding="utf-8")
        self.tipologias = pd.read_csv(carpeta / "tipologias.csv", encoding="utf-8")
        vu = pd.read_csv(carpeta / "rangos_vu.csv", encoding="utf-8")
        self.rangos_vu = vu.dropna(subset=["vu_min", "vu_max"])

        activas = self.reglas[self.reglas["activa"] == "SI"]
        self.reglas_activas = activas["rule_id"].tolist()
        self.accion = dict(zip(activas["rule_id"], activas["accion"]))

    def enriquecer(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega zona, centroide, radio, requiere_construccion y rango de valor."""
        out = df.merge(
            self.geografia[["provincia", "canton", "distrito", "zona",
                            "lat_centroide", "lon_centroide", "radio_km"]],
            on=["provincia", "canton", "distrito"], how="left", validate="many_to_one")
        out = out.merge(
            self.tipologias[["tipologia", "requiere_construccion", "cobertura_min", "cobertura_max"]]
            .rename(columns={"tipologia": "tipologia_inmueble"}),
            on="tipologia_inmueble", how="left", validate="many_to_one")
        out = out.merge(
            self.rangos_vu[["zona", "tipologia", "moneda", "vu_min", "vu_max"]]
            .rename(columns={"tipologia": "tipologia_inmueble"}),
            on=["zona", "tipologia_inmueble", "moneda"], how="left", validate="many_to_one")
        return out.set_index(df.index)


# =============================================================================
# REGLAS
# Todas comparten firma: (df enriquecido, ctx, corte) -> DataFrame de resultado.
# =============================================================================
def r01_unicidad(df, ctx, corte):
    """No pueden existir dos avalúos con el mismo identificador dentro del corte.
    Se marcan todas las filas del grupo: no hay forma de saber cuál sobra."""
    res = resultado(df.index, CUMPLE)
    falta = es_ausente(df["id_avaluo"])
    res.loc[falta, "estado"] = NO_APLICA
    dup = df["id_avaluo"].duplicated(keep=False) & ~falta
    res.loc[dup, ["estado", "campo", "valor_observado", "condicion_esperada"]] = [
        INCUMPLE, "id_avaluo", "", "único dentro del corte"]
    res.loc[dup, "valor_observado"] = df.loc[dup, "id_avaluo"]
    return res


def r02_completitud(df, ctx, corte):
    """Campos obligatorios informados, incluida la obligatoriedad condicional
    de valor_unitario_construccion_m2 cuando hay área construida."""
    res = resultado(df.index, CUMPLE)
    faltantes = pd.Series([[] for _ in range(len(df))], index=df.index)
    for campo in CAMPOS_OBLIGATORIOS:
        m = es_ausente(df[campo])
        faltantes[m] = faltantes[m].apply(lambda lst, c=campo: lst + [c])

    area = a_numero(df["area_construccion_m2"])
    cond = (area > 0) & es_ausente(df["valor_unitario_construccion_m2"])
    faltantes[cond] = faltantes[cond].apply(lambda lst: lst + ["valor_unitario_construccion_m2"])

    malos = faltantes.str.len() > 0
    res.loc[malos, ["estado", "campo", "condicion_esperada"]] = [INCUMPLE, "", "campo informado"]
    res.loc[malos, "campo"] = faltantes[malos].str.join("; ")
    res.loc[malos, "valor_observado"] = "ausente"
    return res


def r03_consistencia_aritmetica(df, ctx, corte):
    """total = terreno + construcción + obras, con tolerancia de medio paso de redondeo."""
    res = resultado(df.index)
    at, vt = a_numero(df["area_terreno_m2"]), a_numero(df["valor_unitario_terreno_m2"])
    ac, vc = a_numero(df["area_construccion_m2"]), a_numero(df["valor_unitario_construccion_m2"])
    ob, total = a_numero(df["valor_obras_complementarias"]), a_numero(df["valor_total_inmueble"])
    paso = df["moneda"].map(PASO_REDONDEO)

    evaluable = ~(at.isna() | vt.isna() | ac.isna() | vc.isna() | ob.isna() | total.isna() | paso.isna())
    calculado = at * vt + ac * vc + ob
    desvio = (calculado - total).abs()
    malo = evaluable & (desvio > paso / 2)

    res.loc[evaluable, "estado"] = CUMPLE
    res.loc[malo, ["estado", "campo"]] = [INCUMPLE, "valor_total_inmueble"]
    res.loc[malo, "valor_observado"] = total[malo].round(2).astype(str)
    res.loc[malo, "condicion_esperada"] = calculado[malo].round(2).astype(str)
    return res


def r04_coherencia_tipologia(df, ctx, corte):
    """Tipología no edificada exige construcción en cero; tipología edificada la exige positiva.
    Con requiere_construccion = OPCIONAL la regla no puede opinar."""
    res = resultado(df.index)
    req = df["requiere_construccion"]
    ac, vc = a_numero(df["area_construccion_m2"]), a_numero(df["valor_unitario_construccion_m2"])
    evaluable = req.isin(["SI", "NO"]) & ~ac.isna() & ~vc.isna()

    sin_construccion = evaluable & (req == "NO") & ((ac > 0) | (vc > 0))
    con_construccion = evaluable & (req == "SI") & ((ac <= 0) | (vc <= 0))
    malo = sin_construccion | con_construccion

    res.loc[evaluable, "estado"] = CUMPLE
    res.loc[malo, ["estado", "campo"]] = [INCUMPLE, "area_construccion_m2"]
    res.loc[malo, "valor_observado"] = ("área " + ac[malo].round(2).astype(str)
                                        + " / vu " + vc[malo].round(2).astype(str))
    res.loc[sin_construccion, "condicion_esperada"] = "ambos en cero: la tipología no contempla construcción"
    res.loc[con_construccion, "condicion_esperada"] = "ambos mayores a cero: la tipología exige construcción"
    return res


def r05_cronologia(df, ctx, corte):
    """Inspección <= valor <= informe <= corte, sin brechas excesivas."""
    res = resultado(df.index)
    fi, fv, fr = (a_fecha(df["fecha_inspeccion"]), a_fecha(df["fecha_valor"]), a_fecha(df["fecha_informe"]))
    fin = pd.Timestamp(CORTES_FIN_DE_MES[corte])
    evaluable = ~(fi.isna() | fv.isna() | fr.isna())

    desorden = (fi > fv) | (fv > fr)
    futura = fr > fin
    brecha = ((fv - fi).dt.days > MAX_DIAS_INSPECCION_A_VALOR) | ((fr - fv).dt.days > MAX_DIAS_VALOR_A_INFORME)
    malo = evaluable & (desorden | futura | brecha)

    motivo = pd.Series("", index=df.index)
    motivo[evaluable & brecha] = f"brecha mayor a {MAX_DIAS_INSPECCION_A_VALOR}/{MAX_DIAS_VALOR_A_INFORME} días"
    motivo[evaluable & futura] = f"fecha posterior al corte {fin.date()}"
    motivo[evaluable & desorden] = "inspección <= valor <= informe"

    res.loc[evaluable, "estado"] = CUMPLE
    res.loc[malo, ["estado", "campo"]] = [INCUMPLE, "fecha_inspeccion; fecha_valor; fecha_informe"]
    res.loc[malo, "valor_observado"] = (fi[malo].dt.strftime("%Y-%m-%d") + " / "
                                        + fv[malo].dt.strftime("%Y-%m-%d") + " / "
                                        + fr[malo].dt.strftime("%Y-%m-%d"))
    res.loc[malo, "condicion_esperada"] = motivo[malo]
    return res


def r06_integridad_geografica(df, ctx, corte):
    """La coordenada debe caer dentro del radio declarado para el distrito.
    Es aproximada: valida cercanía al centroide, no pertenencia al polígono."""
    res = resultado(df.index)
    lat, lon = a_numero(df["latitud"]), a_numero(df["longitud"])
    evaluable = ~(lat.isna() | lon.isna() | df["lat_centroide"].isna())

    fuera_pais = ~(lat.between(LAT_MIN, LAT_MAX) & lon.between(LON_MIN, LON_MAX))
    distancia = pd.Series(np.nan, index=df.index, dtype=float)
    distancia[evaluable] = haversine(lat[evaluable], lon[evaluable],
                                     df.loc[evaluable, "lat_centroide"], df.loc[evaluable, "lon_centroide"])
    lejos = distancia > df["radio_km"]
    malo = evaluable & (fuera_pais | lejos)

    res.loc[evaluable, "estado"] = CUMPLE
    res.loc[malo, ["estado", "campo"]] = [INCUMPLE, "latitud; longitud"]
    res.loc[malo, "valor_observado"] = (lat[malo].astype(str) + ", " + lon[malo].astype(str))
    res.loc[malo & fuera_pais, "condicion_esperada"] = "coordenada dentro del territorio nacional"
    res.loc[malo & ~fuera_pais, "condicion_esperada"] = (
        "a menos de " + df.loc[malo & ~fuera_pais, "radio_km"].astype(str)
        + " km del centroide; observado " + distancia[malo & ~fuera_pais].round(1).astype(str) + " km")
    return res


def r07_plausibilidad_valor(df, ctx, corte):
    """Valor unitario de terreno dentro del rango de la zona.
    Sin rango de referencia la regla devuelve NO_APLICA, nunca CUMPLE."""
    res = resultado(df.index)
    vt = a_numero(df["valor_unitario_terreno_m2"])
    evaluable = ~(vt.isna() | df["vu_min"].isna() | df["vu_max"].isna())
    malo = evaluable & ~vt.between(df["vu_min"], df["vu_max"])

    res.loc[evaluable, "estado"] = CUMPLE
    res.loc[malo, ["estado", "campo"]] = [INCUMPLE, "valor_unitario_terreno_m2"]
    res.loc[malo, "valor_observado"] = vt[malo].round(2).astype(str)
    res.loc[malo, "condicion_esperada"] = (
        "entre " + df.loc[malo, "vu_min"].round(2).astype(str)
        + " y " + df.loc[malo, "vu_max"].round(2).astype(str)
        + " (" + df.loc[malo, "zona"].astype(str) + ", " + df.loc[malo, "moneda"].astype(str) + ")")
    return res


def r08_vigencia(df, ctx, corte):
    """El avalúo no debe superar la vigencia de política respecto de la fecha de corte."""
    res = resultado(df.index)
    fv = a_fecha(df["fecha_valor"])
    fin = pd.Timestamp(CORTES_FIN_DE_MES[corte])
    umbral = fin - pd.DateOffset(months=VIGENCIA_MESES)
    evaluable = ~fv.isna()
    malo = evaluable & (fv < umbral)

    res.loc[evaluable, "estado"] = CUMPLE
    res.loc[malo, ["estado", "campo"]] = [INCUMPLE, "fecha_valor"]
    res.loc[malo, "valor_observado"] = fv[malo].dt.strftime("%Y-%m-%d")
    res.loc[malo, "condicion_esperada"] = f"no anterior a {umbral.date()} ({VIGENCIA_MESES} meses)"
    return res


def r09_cobertura(df, ctx, corte):
    """Área construida proporcional al terreno. Inactiva por defecto: los rangos de
    cobertura de tipologias.csv necesitan calibración con criterio de valuación."""
    res = resultado(df.index)
    at, ac = a_numero(df["area_terreno_m2"]), a_numero(df["area_construccion_m2"])
    evaluable = (~at.isna()) & (at > 0) & (~ac.isna()) & (ac > 0) & ~df["cobertura_min"].isna()
    cob = ac / at
    malo = evaluable & ~cob.between(df["cobertura_min"], df["cobertura_max"])

    res.loc[evaluable, "estado"] = CUMPLE
    res.loc[malo, ["estado", "campo"]] = [INCUMPLE, "area_construccion_m2"]
    res.loc[malo, "valor_observado"] = "cobertura " + cob[malo].round(2).astype(str)
    res.loc[malo, "condicion_esperada"] = ("entre " + df.loc[malo, "cobertura_min"].astype(str)
                                           + " y " + df.loc[malo, "cobertura_max"].astype(str))
    return res


def r10_coordenadas_repetidas(df, ctx, corte):
    """Coordenada idéntica en fincas distintas: indica copiado del avalúo anterior.
    Inactiva por defecto: falta definir el umbral de precisión decimal."""
    res = resultado(df.index)
    lat, lon = a_numero(df["latitud"]), a_numero(df["longitud"])
    evaluable = ~(lat.isna() | lon.isna())
    clave = lat.round(6).astype(str) + "," + lon.round(6).astype(str)
    fincas = df.groupby(clave)["numero_finca"].transform("nunique")
    malo = evaluable & (fincas > 1)

    res.loc[evaluable, "estado"] = CUMPLE
    res.loc[malo, ["estado", "campo"]] = [INCUMPLE, "latitud; longitud"]
    res.loc[malo, "valor_observado"] = clave[malo]
    res.loc[malo, "condicion_esperada"] = "coordenada no compartida con otra finca"
    return res


CATALOGO = {
    "R-01": r01_unicidad, "R-02": r02_completitud, "R-03": r03_consistencia_aritmetica,
    "R-04": r04_coherencia_tipologia, "R-05": r05_cronologia, "R-06": r06_integridad_geografica,
    "R-07": r07_plausibilidad_valor, "R-08": r08_vigencia,
    "R-09": r09_cobertura, "R-10": r10_coordenadas_repetidas,
}


# =============================================================================
# ORQUESTACIÓN
# =============================================================================
def validar_corte(crudo: pd.DataFrame, ctx: Contexto, corte: str):
    df = ctx.enriquecer(crudo)

    estados, incidencias = {}, []
    for rule_id in ctx.reglas_activas:
        if rule_id not in CATALOGO:
            raise KeyError(f"{rule_id} está activa en reglas_datos.csv pero no implementada en CATALOGO")
        res = CATALOGO[rule_id](df, ctx, corte)
        estados[rule_id] = res["estado"]

        fallos = res[res["estado"] == INCUMPLE]
        if not fallos.empty:
            incidencias.append(pd.DataFrame({
                "corte": corte,
                "id_avaluo": crudo.loc[fallos.index, "id_avaluo"],
                "numero_finca": crudo.loc[fallos.index, "numero_finca"],
                "rule_id": rule_id,
                "accion": ctx.accion[rule_id],
                "campo": fallos["campo"],
                "valor_observado": fallos["valor_observado"],
                "condicion_esperada": fallos["condicion_esperada"],
            }))

    estados = pd.DataFrame(estados, index=crudo.index)
    bloquea = [r for r in ctx.reglas_activas if ctx.accion[r] == "BLOQUEA"]
    revisa = [r for r in ctx.reglas_activas if ctx.accion[r] == "REVISA"]

    validados = crudo.copy()
    validados.insert(0, "corte", corte)
    validados["n_bloquea"] = (estados[bloquea] == INCUMPLE).sum(axis=1) if bloquea else 0
    validados["n_revisa"] = (estados[revisa] == INCUMPLE).sum(axis=1) if revisa else 0
    validados["nivel_confiabilidad"] = np.select(
        [validados["n_bloquea"] > 0, validados["n_revisa"] > 0],
        ["NO_CONFIABLE", "REVISAR"], default="CONFIABLE")
    validados = pd.concat([validados, estados], axis=1)

    inc = (pd.concat(incidencias, ignore_index=True) if incidencias
           else pd.DataFrame(columns=["corte", "id_avaluo", "numero_finca", "rule_id", "accion",
                                      "campo", "valor_observado", "condicion_esperada"]))
    return validados, inc


def construir_control(validados: pd.DataFrame, incidencias: pd.DataFrame, recibidos: dict) -> pd.DataFrame:
    """Reconciliación: lo que entró debe ser lo que salió. Va al tablero, no a un log."""
    filas = []
    for corte, grupo in validados.groupby("corte"):
        conteo = grupo["nivel_confiabilidad"].value_counts()
        c, r, n = (int(conteo.get(k, 0)) for k in ("CONFIABLE", "REVISAR", "NO_CONFIABLE"))
        filas.append({
            "corte": corte,
            "recibidos": recibidos[corte],
            "procesados": len(grupo),
            "confiable": c, "revisar": r, "no_confiable": n,
            "incidencias": int((incidencias["corte"] == corte).sum()),
            "cuadra": "SI" if recibidos[corte] == len(grupo) == c + r + n else "NO",
        })
    return pd.DataFrame(filas)


def main():
    ctx = Contexto(REF)
    archivos = sorted(RAW.glob("avaluos_*.csv"))
    if not archivos:
        sys.exit(f"No hay archivos avaluos_*.csv en {RAW}. Corré primero: python src/generar.py")

    faltan = [r for r in ctx.reglas_activas if r not in CATALOGO]
    if faltan:
        sys.exit(f"Reglas activas sin implementar: {faltan}")

    print(f"Reglas activas ({len(ctx.reglas_activas)}): {', '.join(ctx.reglas_activas)}")
    inactivas = ctx.reglas[ctx.reglas["activa"] == "NO"]["rule_id"].tolist()
    if inactivas:
        print(f"Inactivas por catálogo: {', '.join(inactivas)}")

    todos_val, todas_inc, recibidos = [], [], {}
    for archivo in archivos:
        corte = archivo.stem.replace("avaluos_", "").replace("_", "-")
        if corte not in CORTES_FIN_DE_MES:
            sys.exit(f"Corte '{corte}' sin fecha de cierre declarada en CORTES_FIN_DE_MES")
        crudo = pd.read_csv(archivo, encoding="utf-8", keep_default_na=False, dtype=str)
        faltantes = set(CAMPOS_OBLIGATORIOS + ["valor_unitario_construccion_m2"]) - set(crudo.columns)
        if faltantes:
            sys.exit(f"{archivo.name}: faltan columnas {sorted(faltantes)}")

        recibidos[corte] = len(crudo)
        val, inc = validar_corte(crudo, ctx, corte)
        todos_val.append(val)
        todas_inc.append(inc)
        print(f"  {corte}: {len(crudo)} avalúos, {len(inc)} incidencias")

    validados = pd.concat(todos_val, ignore_index=True)
    incidencias = pd.concat(todas_inc, ignore_index=True)
    control = construir_control(validados, incidencias, recibidos)

    OUT.mkdir(parents=True, exist_ok=True)
    validados.to_csv(OUT / "avaluos_validados.csv", index=False, encoding="utf-8")
    incidencias.to_csv(OUT / "incidencias.csv", index=False, encoding="utf-8")
    control.to_csv(OUT / "control_cifras.csv", index=False, encoding="utf-8")

    print("\nControl de cifras")
    print(control.to_string(index=False))
    if (control["cuadra"] == "NO").any():
        sys.exit("\nLas cifras no cuadran. No se publican resultados.")
    print(f"\nSalidas en {OUT.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
