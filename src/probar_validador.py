"""
probar_validador.py — Verifica el validador contra el ground truth.

El generador sabe qué defectos sembró. Este script compara esa verdad conocida
con lo que detectó validar.py, en ambas direcciones:

    no detectadas   el generador lo sembró y el validador no lo vio
    no esperadas    el validador lo marcó y el generador no lo sembró

Qué prueba esto y qué no
------------------------
Prueba que la implementación de cada regla coincide con la intención con la que
se sembraron los defectos. Es una verificación de correctitud del código.

NO prueba que el validador detectaría errores que nadie anticipó. Los datos son
sintéticos y el generador define el universo de defectos posibles. Un resultado
perfecto aquí es lo mínimo exigible, no un logro.

Uso
---
    python src/probar_validador.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
GT = RAIZ / "data" / "ground_truth"
OUT = RAIZ / "data" / "output"


def cargar():
    for ruta, sugerencia in [(GT / "incumplimientos_sembrados.csv", "python src/generar.py"),
                             (OUT / "incidencias.csv", "python src/validar.py")]:
        if not ruta.exists():
            sys.exit(f"Falta {ruta.relative_to(RAIZ)}. Corré: {sugerencia}")
    return (pd.read_csv(GT / "incumplimientos_sembrados.csv", encoding="utf-8", keep_default_na=False),
            pd.read_csv(OUT / "incidencias.csv", encoding="utf-8", keep_default_na=False),
            pd.read_csv(OUT / "avaluos_validados.csv", encoding="utf-8", keep_default_na=False))


def como_conjunto(df: pd.DataFrame) -> set:
    """numero_finca desambigua los pares R-01, que comparten id_avaluo a propósito."""
    return set(df[["corte", "id_avaluo", "numero_finca", "rule_id"]].itertuples(index=False, name=None))


def comparar_por_regla(esperadas: set, detectadas: set) -> pd.DataFrame:
    reglas = sorted({t[3] for t in esperadas | detectadas})
    filas = []
    for r in reglas:
        esp = {t for t in esperadas if t[3] == r}
        det = {t for t in detectadas if t[3] == r}
        vp, fn, fp = len(esp & det), len(esp - det), len(det - esp)
        filas.append({
            "regla": r, "sembradas": len(esp), "detectadas": len(det),
            "correctas": vp, "no_detectadas": fn, "no_esperadas": fp,
            "recall": f"{vp / len(esp):.1%}" if esp else "—",
            "precision": f"{vp / len(det):.1%}" if det else "—",
        })
    return pd.DataFrame(filas)


def main():
    gt, inc, val = cargar()
    esperadas, detectadas = como_conjunto(gt), como_conjunto(inc)

    print("=" * 78)
    print("PRUEBA DEL VALIDADOR CONTRA GROUND TRUTH")
    print("=" * 78)

    print("\nPor regla y corte")
    for corte in sorted({t[0] for t in esperadas | detectadas}):
        esp = {t for t in esperadas if t[0] == corte}
        det = {t for t in detectadas if t[0] == corte}
        print(f"\n  Corte {corte}")
        print(comparar_por_regla(esp, det).to_string(index=False).replace("\n", "\n  "))

    fn, fp = esperadas - detectadas, detectadas - esperadas
    if fn:
        print(f"\nNO DETECTADAS ({len(fn)}): {dict(Counter(t[3] for t in fn))}")
        for t in sorted(fn)[:5]:
            print(f"   {t}")
    if fp:
        print(f"\nNO ESPERADAS ({len(fp)}): {dict(Counter(t[3] for t in fp))}")
        for t in sorted(fp)[:5]:
            print(f"   {t}")

    # Coherencia interna: los conteos del validador deben cuadrar con sus propias incidencias
    print("\nCoherencia interna del validador")
    problemas = []
    reglas = [c for c in val.columns if c.startswith("R-")]
    marcadas = val[reglas].eq("INCUMPLE").sum().sum()
    if marcadas != len(inc):
        problemas.append(f"celdas INCUMPLE ({marcadas}) != filas de incidencias ({len(inc)})")

    esperado_nivel = val.apply(
        lambda f: "NO_CONFIABLE" if f["n_bloquea"] > 0 else ("REVISAR" if f["n_revisa"] > 0 else "CONFIABLE"),
        axis=1)
    if not esperado_nivel.equals(val["nivel_confiabilidad"]):
        problemas.append("nivel_confiabilidad no se deriva de n_bloquea / n_revisa")

    no_aplica = val[reglas].eq("NO_APLICA").sum()
    print(f"  celdas INCUMPLE = filas de incidencias: {marcadas} = {len(inc)}")
    print(f"  nivel_confiabilidad derivado correctamente: {esperado_nivel.equals(val['nivel_confiabilidad'])}")
    print(f"  NO_APLICA por regla: {no_aplica[no_aplica > 0].to_dict() or 'ninguno'}")
    for p in problemas:
        print(f"  PROBLEMA: {p}")

    ok = not fn and not fp and not problemas
    print("\n" + "=" * 78)
    if ok:
        total = len(esperadas)
        print(f"CORRECTO. {total} incumplimientos sembrados, {total} detectados, "
              f"ninguna marca no esperada.")
        print("Recordatorio: esto verifica la implementación, no el desempeño sobre")
        print("errores no anticipados. Ver docs/MANUAL.md, sección 15.")
    else:
        print("HAY DISCREPANCIAS. Revisar el detalle de arriba.")
    print("=" * 78)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
