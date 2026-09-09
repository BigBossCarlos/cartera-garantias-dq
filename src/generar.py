"""
generar.py — Datos sintéticos del proyecto cartera-garantias-dq.

Produce dos cortes mensuales de una cartera de garantías inmobiliarias, la
tabla de créditos que respaldan, y el ground truth de qué incumplimientos se
sembraron en cada avalúo. Todo reproducible: misma semilla, mismos archivos.

Salidas
-------
data/raw/avaluos_2026_03.csv                  corte de marzo, 4.000 avalúos
data/raw/avaluos_2026_04.csv                  corte de abril, 4.000 avalúos
data/raw/creditos.csv                         créditos por corte
data/ground_truth/incumplimientos_sembrados.csv   (corte, id_avaluo, rule_id)
data/ground_truth/evolucion_esperada.csv          categoría esperada de cada avalúo

Uso
---
    python src/generar.py

Los parámetros de negocio salen de reference/. Los parámetros de simulación
(cuántos defectos, de qué tipo, con qué propensión por perito) viven en este
archivo, en el bloque PARÁMETROS, porque describen el experimento y no el
dominio.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

# =============================================================================
# RUTAS
# =============================================================================
RAIZ = Path(__file__).resolve().parents[1]
REF = RAIZ / "reference"
RAW = RAIZ / "data" / "raw"
GT = RAIZ / "data" / "ground_truth"

# =============================================================================
# PARÁMETROS DE SIMULACIÓN
# Ver docs/diccionario_datos.md, sección 7. Cualquier cambio aquí debe
# reflejarse allí.
# =============================================================================
SEMILLA = 2026
N_CORTE = 4000

CORTES = {
    "2026-03": pd.Timestamp("2026-03-31"),
    "2026-04": pd.Timestamp("2026-04-30"),
}
VIGENCIA_MESES = 24                    # R-08
PASO_REDONDEO = {"CRC": 1000, "USD": 1}  # R-03

# --- marzo -------------------------------------------------------------------
N_NO_CONFIABLE = 320
N_REVISAR = 880
DIST_BLOQUEA = {"R-01": 40, "R-02": 90, "R-03": 90, "R-04": 50, "R-05": 50}
DIST_REVISA = {"R-06": 200, "R-07": 200, "R-08": 480}
P_REVISA_EXTRA_EN_BLOQUEA = 0.30       # un NO_CONFIABLE que además trae una REVISA
P_SEGUNDA_REVISA = 0.15                # un REVISAR con dos REVISA distintas

# --- evolución marzo → abril -------------------------------------------------
N_SALEN_DEFECTUOSOS = 120              # 10 % de los 1.200
N_CORREGIDOS = 720                     # 60 %
N_PERSISTEN = 360                      # 30 %
N_SALEN_TOTAL = 200
N_ENTRAN = 200
N_NUEVOS = 120
DIST_NUEVOS = {"R-01": 4, "R-02": 10, "R-03": 10, "R-04": 8, "R-05": 4,
               "R-06": 22, "R-07": 22, "R-08": 40}

# --- cartera de créditos ------------------------------------------------------
FINALIDADES_CON_CREDITO = ["Garantía hipotecaria", "Leasing", "Actualización de garantía"]
FINALIDADES_SIN_CREDITO = ["Seguro", "Contable", "Compraventa"]
P_CON_CREDITO = 0.80
LTV_MIN, LTV_MAX = 0.45, 0.85

# --- peritos: carga de trabajo y propensión a error ---------------------------
# La propensión es parámetro del experimento, no dato de referencia: por eso
# no vive en peritos.csv. Cualquier perito no listado recibe 1.0.
CARGA_PERITO = {"PER-001": 1.6, "PER-003": 1.5, "PER-007": 1.3}
PROPENSION_PERITO = {"PER-003": 3.0, "PER-007": 2.2, "PER-005": 0.5, "PER-002": 0.7}

# --- mezcla de la cartera -----------------------------------------------------
PESO_ZONA = {"GAM_CENTRO": 0.40, "GAM_PERIFERIA": 0.25, "CIUDAD_INTERMEDIA": 0.18,
             "RURAL": 0.07, "COSTA": 0.10}

PESO_TIPOLOGIA_POR_ZONA = {
    "GAM_CENTRO":        {"Casa de habitación": 30, "Apartamento": 22, "Condominio horizontal": 12,
                          "Local comercial": 14, "Edificio de oficinas": 8, "Bodega o nave industrial": 6,
                          "Terreno baldío urbano": 8},
    "GAM_PERIFERIA":     {"Casa de habitación": 45, "Apartamento": 10, "Condominio horizontal": 12,
                          "Local comercial": 10, "Bodega o nave industrial": 8, "Terreno baldío urbano": 15},
    "CIUDAD_INTERMEDIA": {"Casa de habitación": 45, "Local comercial": 15, "Bodega o nave industrial": 8,
                          "Terreno baldío urbano": 15, "Terreno baldío rural": 7, "Finca agrícola": 10},
    "RURAL":             {"Casa de habitación": 30, "Terreno baldío rural": 25, "Finca agrícola": 35,
                          "Terreno baldío urbano": 10},
    "COSTA":             {"Casa de habitación": 30, "Condominio horizontal": 25, "Apartamento": 15,
                          "Terreno baldío urbano": 20, "Terreno baldío rural": 10},
}

# Área de terreno por tipología: (mínimo, moda, máximo) en m², distribución triangular
AREA_TERRENO = {
    "Terreno baldío urbano": (150, 300, 2000),
    "Terreno baldío rural": (1000, 5000, 80000),
    "Casa de habitación": (120, 250, 1200),
    "Apartamento": (40, 90, 250),
    "Condominio horizontal": (150, 300, 800),
    "Local comercial": (100, 300, 3000),
    "Bodega o nave industrial": (500, 2000, 20000),
    "Edificio de oficinas": (300, 800, 5000),
    "Finca agrícola": (10000, 50000, 400000),
}

# Valor unitario de terreno por defecto (min, max), SOLO cuando rangos_vu.csv no
# tiene la combinación. Son órdenes de magnitud ilustrativos, no valores de mercado.
VU_TERRENO_DEFAULT = {
    ("GAM_CENTRO", "CRC"): (150_000, 600_000),        ("GAM_CENTRO", "USD"): (300, 1200),
    ("GAM_PERIFERIA", "CRC"): (60_000, 250_000),      ("GAM_PERIFERIA", "USD"): (120, 500),
    ("CIUDAD_INTERMEDIA", "CRC"): (30_000, 150_000),  ("CIUDAD_INTERMEDIA", "USD"): (60, 300),
    ("RURAL", "CRC"): (5_000, 40_000),                ("RURAL", "USD"): (10, 80),
    ("COSTA", "CRC"): (40_000, 300_000),              ("COSTA", "USD"): (80, 600),
}
# Valor unitario de construcción depreciado (min, max). Ilustrativo.
VU_CONSTRUCCION = {"CRC": (250_000, 850_000), "USD": (500, 1700)}

# Ventana de fecha de valor para avalúos limpios de la población inicial.
# Empieza justo en el umbral de vigencia de marzo: los que caigan en abril de
# 2024 estarán vigentes en marzo y vencidos en abril sin que nadie los toque.
FECHA_VALOR_MIN = CORTES["2026-03"] - pd.DateOffset(months=VIGENCIA_MESES)
FECHA_VALOR_MAX = pd.Timestamp("2026-02-28")

# Los que entran en abril son recientes
FECHA_ENTRANTES_MIN = pd.Timestamp("2026-03-01")
FECHA_ENTRANTES_MAX = pd.Timestamp("2026-04-15")

COLUMNAS_AVALUO = [
    "id_avaluo", "numero_finca", "finalidad", "fecha_inspeccion", "fecha_valor", "fecha_informe",
    "provincia", "canton", "distrito", "latitud", "longitud", "tipologia_inmueble", "moneda",
    "area_terreno_m2", "valor_unitario_terreno_m2", "area_construccion_m2",
    "valor_unitario_construccion_m2", "valor_obras_complementarias", "valor_total_inmueble", "perito_id",
]
VALORES_AUSENTES = ["", "N/A", " "]


# =============================================================================
# REFERENCIAS
# =============================================================================
class Referencias:
    """Carga las tablas de reference/ y expone lo que el generador necesita."""

    def __init__(self, carpeta: Path):
        self.geografia = pd.read_csv(carpeta / "geografia.csv", encoding="utf-8")
        tip = pd.read_csv(carpeta / "tipologias.csv", encoding="utf-8")
        self.tipologias = tip[tip["activa"] == "SI"].set_index("tipologia")
        per = pd.read_csv(carpeta / "peritos.csv", encoding="utf-8")
        self.peritos = per.loc[per["activo"] == "SI", "perito_id"].tolist()

        vu = pd.read_csv(carpeta / "rangos_vu.csv", encoding="utf-8").dropna(subset=["vu_min", "vu_max"])
        self.rangos_vu = {(r.zona, r.tipologia, r.moneda): (float(r.vu_min), float(r.vu_max))
                          for r in vu.itertuples()}

        # Peso de muestreo de cada distrito: peso de su zona repartido entre sus distritos
        conteo = self.geografia["zona"].value_counts()
        self.peso_distrito = self.geografia["zona"].map(lambda z: PESO_ZONA[z] / conteo[z]).to_numpy(dtype=float).copy()
        self.peso_distrito /= self.peso_distrito.sum()

        self.peso_perito = np.array([CARGA_PERITO.get(p, 1.0) for p in self.peritos])
        self.peso_perito /= self.peso_perito.sum()

    def requiere_construccion(self, tipologia: str) -> str:
        return self.tipologias.loc[tipologia, "requiere_construccion"]

    def cobertura(self, tipologia: str) -> tuple[float, float]:
        fila = self.tipologias.loc[tipologia]
        return float(fila["cobertura_min"]), float(fila["cobertura_max"])

    def tiene_rango(self, zona: str, tipologia: str, moneda: str) -> bool:
        return (zona, tipologia, moneda) in self.rangos_vu


# =============================================================================
# UTILIDADES
# =============================================================================
def redondear(valor: float, paso: float) -> float:
    """Redondeo half-up al paso indicado. Solo se aplica al valor total."""
    return math.floor(valor / paso + 0.5) * paso


def calcular_total(fila: pd.Series) -> float:
    suma = (fila["area_terreno_m2"] * fila["valor_unitario_terreno_m2"]
            + fila["area_construccion_m2"] * fila["valor_unitario_construccion_m2"]
            + fila["valor_obras_complementarias"])
    return redondear(suma, PASO_REDONDEO[fila["moneda"]])


def fecha_aleatoria(rng, fecha_min, fecha_max, sesgo_reciente: float = 0.6):
    """Fecha entre los límites, sesgada hacia lo reciente porque la cartera crece."""
    dias = (fecha_max - fecha_min).days
    u = rng.random() ** sesgo_reciente
    return (fecha_min + pd.Timedelta(days=int(u * dias))).normalize()


def desplazar(lat0, lon0, distancia_km, angulo):
    """Punto a una distancia y rumbo dados. Suficiente para radios de decenas de km."""
    dlat = distancia_km * math.cos(angulo) / 111.0
    dlon = distancia_km * math.sin(angulo) / (111.0 * math.cos(math.radians(lat0)))
    return round(lat0 + dlat, 6), round(lon0 + dlon, 6)


def coordenada_dentro(rng, lat0, lon0, radio_km):
    """Coordenada claramente dentro del radio: como mucho al 60 % de la distancia."""
    r = radio_km * 0.6 * math.sqrt(rng.random())
    return desplazar(lat0, lon0, r, rng.random() * 2 * math.pi)


def fecha_umbral_vigencia(corte: pd.Timestamp) -> pd.Timestamp:
    """Un avalúo está vigente si fecha_valor >= corte - VIGENCIA_MESES."""
    return corte - pd.DateOffset(months=VIGENCIA_MESES)


# =============================================================================
# POBLACIÓN LIMPIA
# =============================================================================
def generar_avaluo_limpio(rng, ref: Referencias, uid: int, secuencia: int,
                          fecha_min, fecha_max) -> dict:
    """Un avalúo que cumple todas las reglas. La base sobre la que se siembran defectos."""
    geo = ref.geografia.iloc[rng.choice(len(ref.geografia), p=ref.peso_distrito)]
    zona = geo["zona"]

    pesos = PESO_TIPOLOGIA_POR_ZONA[zona]
    tipologias = [t for t in pesos if t in ref.tipologias.index]
    p = np.array([pesos[t] for t in tipologias], dtype=float)
    tipologia = tipologias[rng.choice(len(tipologias), p=p / p.sum())]

    moneda_habitual = ref.tipologias.loc[tipologia, "moneda_habitual"]
    moneda = moneda_habitual if rng.random() < 0.85 else ("USD" if moneda_habitual == "CRC" else "CRC")

    fecha_valor = fecha_aleatoria(rng, fecha_min, fecha_max)
    fecha_inspeccion = fecha_valor - pd.Timedelta(days=int(rng.integers(0, 21)))
    fecha_informe = fecha_valor + pd.Timedelta(days=int(rng.integers(1, 13)))

    lat, lon = coordenada_dentro(rng, geo["lat_centroide"], geo["lon_centroide"], geo["radio_km"])

    a_min, a_moda, a_max = AREA_TERRENO[tipologia]
    area_terreno = round(float(rng.triangular(a_min, a_moda, a_max)), 2)

    if ref.tiene_rango(zona, tipologia, moneda):
        vu_min, vu_max = ref.rangos_vu[(zona, tipologia, moneda)]
    else:
        vu_min, vu_max = VU_TERRENO_DEFAULT[(zona, moneda)]
    ancho = vu_max - vu_min
    vu_terreno = round(float(rng.uniform(vu_min + 0.10 * ancho, vu_max - 0.10 * ancho)), 2)

    requiere = ref.requiere_construccion(tipologia)
    construye = requiere == "SI" or (requiere == "OPCIONAL" and rng.random() < 0.5)
    if construye:
        cob_min, cob_max = ref.cobertura(tipologia)
        if requiere == "OPCIONAL":
            cob_min, cob_max = 0.01, max(0.02, cob_max)
        area_construccion = round(area_terreno * float(rng.uniform(cob_min, cob_max)), 2)
        vu_construccion = round(float(rng.uniform(*VU_CONSTRUCCION[moneda])), 2)
        obras = round(area_construccion * vu_construccion * float(rng.uniform(0.0, 0.08)), 2)
    else:
        area_construccion, vu_construccion = 0.0, 0.0
        obras = 0.0 if rng.random() < 0.7 else round(area_terreno * vu_terreno * float(rng.uniform(0.005, 0.03)), 2)

    con_credito = rng.random() < P_CON_CREDITO
    finalidad = str(rng.choice(FINALIDADES_CON_CREDITO if con_credito else FINALIDADES_SIN_CREDITO))

    provincia_num = ["San José", "Alajuela", "Cartago", "Heredia", "Guanacaste", "Puntarenas", "Limón"].index(geo["provincia"]) + 1
    filial = f"-{rng.integers(1, 400):03d}" if tipologia in ("Apartamento", "Condominio horizontal") else ""

    fila = {
        "_uid": uid,
        "id_avaluo": f"AV-{fecha_valor.year}-{secuencia:06d}",
        "numero_finca": f"{provincia_num}-{rng.integers(100000, 999999)}{filial}",
        "finalidad": finalidad,
        "fecha_inspeccion": fecha_inspeccion,
        "fecha_valor": fecha_valor,
        "fecha_informe": fecha_informe,
        "provincia": geo["provincia"], "canton": geo["canton"], "distrito": geo["distrito"],
        "latitud": lat, "longitud": lon,
        "tipologia_inmueble": tipologia, "moneda": moneda,
        "area_terreno_m2": area_terreno, "valor_unitario_terreno_m2": vu_terreno,
        "area_construccion_m2": area_construccion, "valor_unitario_construccion_m2": vu_construccion,
        "valor_obras_complementarias": obras,
        "perito_id": ref.peritos[rng.choice(len(ref.peritos), p=ref.peso_perito)],
        "_zona": zona, "_requiere": requiere, "_con_credito": con_credito,
    }
    fila["valor_total_inmueble"] = calcular_total(pd.Series(fila))
    return fila


def generar_poblacion(rng, ref, n, uid_inicio, secuencia_inicio, fecha_min, fecha_max) -> pd.DataFrame:
    filas = [generar_avaluo_limpio(rng, ref, uid_inicio + i, secuencia_inicio + i, fecha_min, fecha_max)
             for i in range(n)]
    return pd.DataFrame(filas).set_index("_uid", drop=False)


# =============================================================================
# SEMBRADO DE INCUMPLIMIENTOS
# Cada función altera el DataFrame en sitio y devuelve la lista de
# (uid, regla) que sembró. El ground truth se construye con esas listas.
# =============================================================================
def sembrar_r01(df, uids, rng):
    """Identificador duplicado. Se siembra por pares: el segundo toma el id del primero."""
    salida = []
    for a, b in zip(uids[0::2], uids[1::2]):
        df.loc[b, "id_avaluo"] = df.loc[a, "id_avaluo"]
        salida += [(a, "R-01"), (b, "R-01")]
    return salida


def sembrar_r02(df, uids, rng):
    """Campo obligatorio ausente. Evita campos que otras reglas necesitan para evaluar."""
    campos = ["perito_id", "numero_finca", "fecha_informe", "valor_obras_complementarias"]
    salida = []
    for uid in uids:
        if df.loc[uid, "area_construccion_m2"] > 0 and rng.random() < 0.25:
            campo = "valor_unitario_construccion_m2"        # obligatoriedad condicional
        else:
            campo = str(rng.choice(campos))
        if df[campo].dtype != object:
            df[campo] = df[campo].astype(object)
        df.loc[uid, campo] = str(rng.choice(VALORES_AUSENTES))
        salida.append((uid, "R-02"))
    return salida


def sembrar_r03(df, uids, rng):
    """Total que no cuadra: desvío de entre 3 y 20 %, redondeado para que parezca legítimo."""
    salida = []
    for uid in uids:
        signo = 1 if rng.random() < 0.5 else -1
        factor = 1 + signo * float(rng.uniform(0.03, 0.20))
        paso = PASO_REDONDEO[df.loc[uid, "moneda"]]
        df.loc[uid, "valor_total_inmueble"] = redondear(df.loc[uid, "valor_total_inmueble"] * factor, paso)
        salida.append((uid, "R-03"))
    return salida


def sembrar_r04(df, uids, rng):
    """Tipología incompatible con lo construido. Baldío con construcción, o edificada sin ella.
    En el 40 % de los casos el total no se recalcula, así que también falla R-03."""
    salida = []
    for uid in uids:
        if df.loc[uid, "_requiere"] == "NO":
            df.loc[uid, "area_construccion_m2"] = round(float(rng.triangular(60, 120, 300)), 2)
            df.loc[uid, "valor_unitario_construccion_m2"] = round(float(rng.uniform(*VU_CONSTRUCCION[df.loc[uid, "moneda"]])), 2)
        else:
            df.loc[uid, "area_construccion_m2"] = 0.0
            df.loc[uid, "valor_unitario_construccion_m2"] = 0.0
        salida.append((uid, "R-04"))
        if rng.random() < 0.60:
            df.loc[uid, "valor_total_inmueble"] = calcular_total(df.loc[uid])
        else:
            salida.append((uid, "R-03"))
    return salida


def sembrar_r05(df, uids, rng, corte):
    """Fechas fuera de orden o en el futuro. Las futuras se ponen lejos de ambos cortes."""
    salida = []
    for uid in uids:
        fv = df.loc[uid, "fecha_valor"]
        variante = rng.choice(["inspeccion_despues", "informe_antes", "futura", "brecha_larga"], p=[0.4, 0.3, 0.15, 0.15])
        if variante == "inspeccion_despues":
            df.loc[uid, "fecha_inspeccion"] = fv + pd.Timedelta(days=int(rng.integers(5, 41)))
        elif variante == "informe_antes":
            df.loc[uid, "fecha_informe"] = fv - pd.Timedelta(days=int(rng.integers(3, 31)))
        elif variante == "futura":
            df.loc[uid, "fecha_informe"] = pd.Timestamp("2026-07-01") + pd.Timedelta(days=int(rng.integers(0, 120)))
        else:
            df.loc[uid, "fecha_inspeccion"] = fv - pd.Timedelta(days=int(rng.integers(45, 120)))
        salida.append((uid, "R-05"))
    return salida


def sembrar_r06(df, uids, rng):
    """Coordenada lejos del distrito: desplazamiento de 40 a 120 km, o lat/lon invertidas."""
    salida = []
    for uid in uids:
        if rng.random() < 0.2:
            df.loc[uid, ["latitud", "longitud"]] = [df.loc[uid, "longitud"], df.loc[uid, "latitud"]]
        else:
            lat, lon = desplazar(df.loc[uid, "latitud"], df.loc[uid, "longitud"],
                                 float(rng.uniform(40, 120)), rng.random() * 2 * math.pi)
            df.loc[uid, ["latitud", "longitud"]] = [lat, lon]
        salida.append((uid, "R-06"))
    return salida


def sembrar_r07(df, uids, rng, ref):
    """Valor unitario fuera del rango de la zona. El total se recalcula: solo falla R-07."""
    salida = []
    for uid in uids:
        vu_min, vu_max = ref.rangos_vu[(df.loc[uid, "_zona"], df.loc[uid, "tipologia_inmueble"], df.loc[uid, "moneda"])]
        if rng.random() < 0.65 or vu_min * 0.6 < 1:
            nuevo = vu_max * float(rng.uniform(1.6, 4.0))
        else:
            nuevo = vu_min * float(rng.uniform(0.2, 0.6))
        df.loc[uid, "valor_unitario_terreno_m2"] = round(nuevo, 2)
        df.loc[uid, "valor_total_inmueble"] = calcular_total(df.loc[uid])
        salida.append((uid, "R-07"))
    return salida


def sembrar_r08(df, uids, rng, corte):
    """Avalúo vencido: fecha de valor entre 25 y 60 meses antes del corte."""
    salida = []
    for uid in uids:
        fv = (corte - pd.DateOffset(months=int(rng.integers(25, 61)))
              - pd.Timedelta(days=int(rng.integers(0, 28)))).normalize()
        df.loc[uid, "fecha_valor"] = fv
        df.loc[uid, "fecha_inspeccion"] = fv - pd.Timedelta(days=int(rng.integers(0, 21)))
        df.loc[uid, "fecha_informe"] = fv + pd.Timedelta(days=int(rng.integers(1, 13)))
        salida.append((uid, "R-08"))
    return salida


def elegibles(df, regla, ref, uids):
    """Qué avalúos pueden recibir una regla dada. R-04 y R-07 tienen restricciones."""
    if regla == "R-04":
        return [u for u in uids if df.loc[u, "_requiere"] in ("SI", "NO")]
    if regla == "R-07":
        return [u for u in uids if ref.tiene_rango(df.loc[u, "_zona"], df.loc[u, "tipologia_inmueble"], df.loc[u, "moneda"])]
    return list(uids)


def asignar_reglas(df, ref, rng, pool: list[int], distribucion: dict[str, int]) -> dict[str, list[int]]:
    """Reparte el pool entre reglas respetando cuotas y elegibilidad.
    Si una regla no tiene suficientes elegibles, el excedente va a R-08 o R-02."""
    libres = list(pool)
    rng.shuffle(libres)
    asignacion: dict[str, list[int]] = {r: [] for r in distribucion}
    faltante = 0
    for regla in ["R-07", "R-04", "R-01", "R-02", "R-03", "R-05", "R-06", "R-08"]:
        if regla not in distribucion:
            continue
        cuota = distribucion[regla]
        if regla == "R-01":
            cuota -= cuota % 2
        cand = elegibles(df, regla, ref, libres)
        toma = cand[:cuota]
        faltante += cuota - len(toma)
        asignacion[regla] = toma
        libres = [u for u in libres if u not in set(toma)]
    respaldo = "R-08" if "R-08" in asignacion else "R-02"
    asignacion[respaldo] += libres[:faltante]
    libres = libres[faltante:]
    assert not libres, f"Quedaron {len(libres)} avalúos sin regla asignada"
    return asignacion


def sembrar(df, ref, rng, asignacion: dict[str, list[int]], corte) -> list[tuple[int, str]]:
    gt = []
    gt += sembrar_r07(df, asignacion.get("R-07", []), rng, ref)   # REVISA primero: recalculan total
    gt += sembrar_r06(df, asignacion.get("R-06", []), rng)
    gt += sembrar_r08(df, asignacion.get("R-08", []), rng, corte)
    gt += sembrar_r04(df, asignacion.get("R-04", []), rng)        # BLOQUEA después
    gt += sembrar_r03(df, asignacion.get("R-03", []), rng)
    gt += sembrar_r05(df, asignacion.get("R-05", []), rng, corte)
    gt += sembrar_r02(df, asignacion.get("R-02", []), rng)
    gt += sembrar_r01(df, asignacion.get("R-01", []), rng)
    return gt


def elegir_con_propension(df, n, rng, excluir: set[int]) -> list[int]:
    """Muestreo sin reemplazo ponderado por la propensión del perito de cada avalúo."""
    cand = df[~df["_uid"].isin(excluir)]
    w = cand["perito_id"].map(lambda p: PROPENSION_PERITO.get(p, 1.0)).to_numpy(dtype=float)
    return [int(u) for u in rng.choice(cand["_uid"].to_numpy(), size=n, replace=False, p=w / w.sum())]


# =============================================================================
# CORTE DE MARZO
# =============================================================================
def construir_marzo(rng, ref):
    limpio = generar_poblacion(rng, ref, N_CORTE, 0, 1, FECHA_VALOR_MIN, FECHA_VALOR_MAX)
    marzo = limpio.copy()
    corte = CORTES["2026-03"]

    pool_bloquea = elegir_con_propension(marzo, N_NO_CONFIABLE, rng, excluir=set())
    pool_revisa = elegir_con_propension(marzo, N_REVISAR, rng, excluir=set(pool_bloquea))

    # NO_CONFIABLE: una BLOQUEA cada uno; algunos traen además una REVISA
    asig_b = asignar_reglas(marzo, ref, rng, pool_bloquea, DIST_BLOQUEA)
    extras = [u for u in pool_bloquea if rng.random() < P_REVISA_EXTRA_EN_BLOQUEA]
    asig_extra = asignar_reglas(marzo, ref, rng, extras, _proporcional(DIST_REVISA, len(extras)))

    # REVISAR: una REVISA cada uno; algunos traen una segunda distinta
    asig_r = asignar_reglas(marzo, ref, rng, pool_revisa, DIST_REVISA)
    regla_de = {u: r for r, us in asig_r.items() for u in us}
    segundas = [u for u in pool_revisa if rng.random() < P_SEGUNDA_REVISA]
    asig_seg: dict[str, list[int]] = {r: [] for r in DIST_REVISA}
    for u in segundas:
        opciones = [r for r in DIST_REVISA if r != regla_de[u] and u in elegibles(marzo, r, ref, [u])]
        if opciones:
            asig_seg[str(rng.choice(opciones))].append(u)

    gt = []
    gt += sembrar(marzo, ref, rng, _fusionar(asig_r, asig_seg), corte)
    gt += sembrar(marzo, ref, rng, _fusionar(asig_extra, {}), corte)
    gt += sembrar(marzo, ref, rng, asig_b, corte)

    pares_r01 = list(zip(asig_b["R-01"][0::2], asig_b["R-01"][1::2]))
    return limpio, marzo, sorted(set(pool_bloquea) | set(pool_revisa)), pares_r01, gt


def _proporcional(dist: dict[str, int], n: int) -> dict[str, int]:
    total = sum(dist.values())
    out = {r: int(round(v / total * n)) for r, v in dist.items()}
    diff = n - sum(out.values())
    out[max(out, key=out.get)] += diff
    return out


def _fusionar(a: dict[str, list[int]], b: dict[str, list[int]]) -> dict[str, list[int]]:
    return {r: a.get(r, []) + b.get(r, []) for r in set(a) | set(b)}


# =============================================================================
# CORTE DE ABRIL
# =============================================================================
def construir_abril(rng, ref, limpio, marzo, defectuosos, pares_r01, gt_marzo):
    corte = CORTES["2026-04"]
    umbral_abril = fecha_umbral_vigencia(corte)
    en_par = {u for p in pares_r01 for u in p}
    singles = [u for u in defectuosos if u not in en_par]
    rng.shuffle(singles)

    # Destino de los pares R-01 (atómico): 2 salen, 12 se corrigen, 6 persisten
    pares = list(pares_r01)
    rng.shuffle(pares)
    salen = [u for p in pares[:2] for u in p]
    corrigen = [u for p in pares[2:14] for u in p]
    persisten = [u for p in pares[14:] for u in p]

    # El resto con singles hasta completar 120 / 720 / 360
    salen += singles[: N_SALEN_DEFECTUOSOS - len(salen)]
    resto = singles[N_SALEN_DEFECTUOSOS - 4:]
    corrigen += resto[: N_CORREGIDOS - len(corrigen)]
    persisten += resto[N_CORREGIDOS - 24:]
    assert (len(salen), len(corrigen), len(persisten)) == (N_SALEN_DEFECTUOSOS, N_CORREGIDOS, N_PERSISTEN), \
        (len(salen), len(corrigen), len(persisten))

    # Salidas de avalúos limpios hasta completar 200
    limpios_marzo = [u for u in marzo["_uid"] if u not in set(defectuosos)]
    rng.shuffle(limpios_marzo)
    salen_limpios = limpios_marzo[: N_SALEN_TOTAL - N_SALEN_DEFECTUOSOS]
    salen_todos = set(salen) | set(salen_limpios)

    # Construcción de abril: partir de marzo, quitar salidas, corregir, agregar entrantes
    abril = marzo[~marzo["_uid"].isin(salen_todos)].copy()
    for u in corrigen:
        abril.loc[u, limpio.columns] = limpio.loc[u]
        reglas_u = {r for uid, r in gt_marzo if uid == u}
        if "R-08" in reglas_u:                     # una corrección de vigencia es un re-avalúo
            fv = fecha_aleatoria(rng, pd.Timestamp("2026-03-01"), pd.Timestamp("2026-04-10"), 1.0)
            abril.loc[u, "fecha_valor"] = fv
            abril.loc[u, "fecha_inspeccion"] = fv - pd.Timedelta(days=int(rng.integers(0, 21)))
            abril.loc[u, "fecha_informe"] = fv + pd.Timedelta(days=int(rng.integers(1, 13)))
            nuevo_vu = abril.loc[u, "valor_unitario_terreno_m2"] * float(rng.uniform(1.02, 1.12))
            clave = (abril.loc[u, "_zona"], abril.loc[u, "tipologia_inmueble"], abril.loc[u, "moneda"])
            if clave in ref.rangos_vu:                # el re-avalúo sube, pero no sale del rango
                nuevo_vu = min(nuevo_vu, ref.rangos_vu[clave][1] * 0.98)
            abril.loc[u, "valor_unitario_terreno_m2"] = round(nuevo_vu, 2)
            abril.loc[u, "valor_total_inmueble"] = calcular_total(abril.loc[u])

    entrantes = generar_poblacion(rng, ref, N_ENTRAN, N_CORTE, N_CORTE + 1, FECHA_ENTRANTES_MIN, FECHA_ENTRANTES_MAX)
    abril = pd.concat([abril, entrantes])
    abril = _homogeneizar_tipos(abril, marzo)
    assert len(abril) == N_CORTE

    # Un avalúo corregido debe quedar limpio en abril. Si recibiera un incumplimiento
    # nuevo, para quien compara los cortes sería un persistente, no un corregido.
    # Por eso los corregidos quedan fuera del pool de nuevos, y si alguno vence solo
    # al restaurar su versión limpia, se le corre la fecha.
    for u in corrigen:
        if pd.Timestamp(abril.loc[u, "fecha_valor"]) < umbral_abril:
            for c in ("fecha_inspeccion", "fecha_valor", "fecha_informe"):
                abril.loc[u, c] = pd.Timestamp(abril.loc[u, c]) + pd.Timedelta(days=45)

    # Nuevos incumplimientos: primero los que vencen solos, después los sembrados
    intactos = [u for u in abril["_uid"] if u not in set(persisten) and u not in set(corrigen)]
    cruzan = [u for u in intactos if pd.Timestamp(abril.loc[u, "fecha_valor"]) < umbral_abril]
    rng.shuffle(cruzan)
    naturales_r08 = cruzan[: DIST_NUEVOS["R-08"]]
    for u in cruzan[DIST_NUEVOS["R-08"]:]:      # exceso: se les corre la fecha para que no venzan
        for c in ("fecha_inspeccion", "fecha_valor", "fecha_informe"):
            abril.loc[u, c] = pd.Timestamp(abril.loc[u, c]) + pd.Timedelta(days=45)

    dist = dict(DIST_NUEVOS)
    dist["R-08"] -= len(naturales_r08)
    candidatos = [u for u in intactos if u not in set(naturales_r08)]
    pool_nuevos = elegir_con_propension(abril.loc[candidatos], sum(dist.values()), rng, excluir=set())

    # R-08 sembrado solo en entrantes: un avalúo que entra ya viejo. No se cambia la fecha a un existente.
    entrantes_ids = set(entrantes["_uid"])
    entr_en_pool = [u for u in pool_nuevos if u in entrantes_ids]
    r08_semb = entr_en_pool[: dist["R-08"]]
    dist["R-06"] += dist["R-08"] - len(r08_semb)
    dist["R-08"] = 0
    asig = asignar_reglas(abril, ref, rng, [u for u in pool_nuevos if u not in set(r08_semb)], {k: v for k, v in dist.items() if v > 0})
    asig["R-08"] = r08_semb

    gt_abril = [(u, r) for (u, r) in gt_marzo if u in set(persisten)]
    gt_abril += [(u, "R-08") for u in naturales_r08]
    # Un persistente por otra regla también puede vencer solo. Sigue siendo persistente,
    # pero el incumplimiento de R-08 es real y el ground truth debe registrarlo.
    gt_abril += [(u, "R-08") for u in persisten if pd.Timestamp(abril.loc[u, "fecha_valor"]) < umbral_abril]
    gt_abril += sembrar(abril, ref, rng, asig, corte)
    gt_abril = sorted(set(gt_abril))

    nuevos = set(naturales_r08) | set(pool_nuevos)
    assert len(nuevos) == N_NUEVOS, len(nuevos)

    destinos = {**{u: "SALIO" for u in salen}, **{u: "CORREGIDO" for u in corrigen},
                **{u: "PERSISTENTE" for u in persisten}, **{u: "NUEVO" for u in nuevos}}
    return abril, gt_abril, destinos, salen_todos, set(entrantes["_uid"]), len(naturales_r08)


def _homogeneizar_tipos(nuevo: pd.DataFrame, modelo: pd.DataFrame) -> pd.DataFrame:
    for c in modelo.columns:
        if modelo[c].dtype == object and nuevo[c].dtype != object:
            nuevo[c] = nuevo[c].astype(object)
    return nuevo


# =============================================================================
# CRÉDITOS
# =============================================================================
def construir_creditos(rng, limpio, marzo, abril, salen_todos, entrantes):
    filas = []
    base = pd.concat([limpio, abril[abril["_uid"].isin(entrantes)]])

    def credito(uid, corte, saldo, estado):
        f = base.loc[uid]
        filas.append({"corte": corte, "id_credito": f"CR-{uid:06d}", "id_avaluo": f["id_avaluo"],
                      "moneda": f["moneda"], "saldo": round(saldo, 2),
                      "fecha_desembolso": (f["fecha_informe"] + pd.Timedelta(days=int(rng.integers(5, 61)))).date(),
                      "estado": estado})

    for uid in marzo["_uid"]:
        if not limpio.loc[uid, "_con_credito"]:
            continue
        f = limpio.loc[uid]
        meses = max(1, (CORTES["2026-03"] - f["fecha_informe"]).days // 30)
        monto = f["valor_total_inmueble"] * float(rng.uniform(LTV_MIN, LTV_MAX))
        saldo_03 = monto * (1 - 0.004) ** meses
        credito(uid, "2026-03", saldo_03, "VIGENTE")
        if uid in salen_todos:
            credito(uid, "2026-04", 0.0, "CANCELADO")
        else:
            credito(uid, "2026-04", saldo_03 * (1 - float(rng.uniform(0.003, 0.012))), "VIGENTE")

    for uid in entrantes:
        f = abril.loc[uid]
        if not f["_con_credito"]:
            continue
        credito(uid, "2026-04", f["valor_total_inmueble"] * float(rng.uniform(LTV_MIN, LTV_MAX)), "VIGENTE")

    return pd.DataFrame(filas)


# =============================================================================
# SALIDA
# =============================================================================
def exportar_avaluos(df: pd.DataFrame) -> pd.DataFrame:
    out = df[COLUMNAS_AVALUO].copy()
    for c in ("fecha_inspeccion", "fecha_valor", "fecha_informe"):
        out[c] = out[c].map(lambda v: v.strftime("%Y-%m-%d") if isinstance(v, pd.Timestamp) else v)
    return out.reset_index(drop=True)


def main():
    rng = np.random.default_rng(SEMILLA)
    ref = Referencias(REF)
    RAW.mkdir(parents=True, exist_ok=True)
    GT.mkdir(parents=True, exist_ok=True)

    limpio, marzo, defectuosos, pares_r01, gt_marzo = construir_marzo(rng, ref)
    abril, gt_abril, destinos, salen_todos, entrantes, naturales = construir_abril(
        rng, ref, limpio, marzo, defectuosos, pares_r01, gt_marzo)
    creditos = construir_creditos(rng, limpio, marzo, abril, salen_todos, entrantes)

    exportar_avaluos(marzo).to_csv(RAW / "avaluos_2026_03.csv", index=False, encoding="utf-8")
    exportar_avaluos(abril).to_csv(RAW / "avaluos_2026_04.csv", index=False, encoding="utf-8")
    creditos.to_csv(RAW / "creditos.csv", index=False, encoding="utf-8")

    # Ground truth. id_avaluo tal como aparece en el archivo del corte.
    gt = pd.DataFrame(
        [("2026-03", marzo.loc[u, "id_avaluo"], marzo.loc[u, "numero_finca"], r) for u, r in gt_marzo]
        + [("2026-04", abril.loc[u, "id_avaluo"], abril.loc[u, "numero_finca"], r) for u, r in gt_abril],
        columns=["corte", "id_avaluo", "numero_finca", "rule_id"]).drop_duplicates()
    gt.to_csv(GT / "incumplimientos_sembrados.csv", index=False, encoding="utf-8")

    evol = []
    for u in sorted(set(marzo["_uid"]) | set(abril["_uid"])):
        en_m, en_a = u in marzo.index, u in abril.index
        cat = destinos.get(u)
        if cat is None:
            cat = "SALIO_CUMPLIENDO" if (en_m and not en_a) else ("ENTRA_CUMPLIENDO" if (en_a and not en_m) else "CUMPLE")
        evol.append({"id_avaluo_marzo": marzo.loc[u, "id_avaluo"] if en_m else "",
                     "id_avaluo_abril": abril.loc[u, "id_avaluo"] if en_a else "",
                     "categoria": cat})
    pd.DataFrame(evol).to_csv(GT / "evolucion_esperada.csv", index=False, encoding="utf-8")

    # Resumen y verificación de los parámetros de diseño
    inc_m = {u for u, _ in gt_marzo}
    inc_a = {u for u, _ in gt_abril}
    bloq_m = {u for u, r in gt_marzo if r in ("R-01", "R-02", "R-03", "R-04", "R-05")}
    print(f"Marzo : {len(marzo)} avalúos | con incumplimiento {len(inc_m)} | NO_CONFIABLE {len(bloq_m)} | REVISAR {len(inc_m - bloq_m)}")
    print(f"Abril : {len(abril)} avalúos | con incumplimiento {len(inc_a)}")
    c = Counter(destinos.values())
    print(f"Evolución: corregidos {c['CORREGIDO']} | persistentes {c['PERSISTENTE']} | salen {c['SALIO']} | nuevos {c['NUEVO']} (de ellos {naturales} vencen solos)")
    print(f"Incidencias sembradas: marzo {len(gt_marzo)}, abril {len(gt_abril)}")
    print("Reglas marzo:", dict(sorted(Counter(r for _, r in gt_marzo).items())))
    print("Reglas abril:", dict(sorted(Counter(r for _, r in gt_abril).items())))
    print(f"Créditos: {len(creditos)} filas | {creditos.groupby('corte')['estado'].value_counts().to_dict()}")

    assert len(inc_m) == N_NO_CONFIABLE + N_REVISAR and len(bloq_m) == N_NO_CONFIABLE
    assert len(inc_a) == N_PERSISTEN + N_NUEVOS
    assert len(marzo) == len(abril) == N_CORTE
    print("\nParámetros de diseño verificados. Archivos en data/raw y data/ground_truth.")


if __name__ == "__main__":
    main()
