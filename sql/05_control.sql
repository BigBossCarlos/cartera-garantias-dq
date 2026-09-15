-- =============================================================================
-- 05_control.sql — Reconciliación del almacén
-- =============================================================================
-- Cada fila es una comprobación con su valor esperado y su valor obtenido.
-- Va al tablero, a la vista, no a un log: un análisis cuyas cifras no cuadran
-- no debería presentarse.
-- =============================================================================

CREATE OR REPLACE TABLE control_almacen AS

-- 1. Ningún avalúo se pierde ni se duplica entre el validador y el hecho
SELECT 1 AS orden,
       'Avalúos: validador = fact_garantia'                      AS comprobacion,
       (SELECT sum(procesados) FROM stg_control_validador)       AS esperado,
       (SELECT count(*) FROM fact_garantia)                      AS obtenido
UNION ALL

-- 2. El grano de fact_garantia es (corte, id_avaluo, numero_finca)
SELECT 2, 'fact_garantia: grano sin duplicados',
       (SELECT count(*) FROM fact_garantia),
       (SELECT count(*) FROM (SELECT DISTINCT corte, id_avaluo, numero_finca FROM fact_garantia))
UNION ALL

-- 3. Toda incidencia del validador encuentra su avalúo
SELECT 3, 'Incidencias: validador = fact_incidencia',
       (SELECT count(*) FROM stg_incidencias),
       (SELECT count(*) FROM fact_incidencia)
UNION ALL

-- 4. Los conteos por nivel coinciden con los del validador
SELECT 4, 'No confiables: validador = modelo',
       (SELECT sum(no_confiable) FROM stg_control_validador),
       (SELECT count(*) FROM fact_garantia WHERE nivel_confiabilidad = 'NO_CONFIABLE')
UNION ALL

SELECT 5, 'A revisar: validador = modelo',
       (SELECT sum(revisar) FROM stg_control_validador),
       (SELECT count(*) FROM fact_garantia WHERE nivel_confiabilidad = 'REVISAR')
UNION ALL

-- 6. Ninguna clave subrogada quedó sin resolver, salvo las esperadas
SELECT 6, 'Geografía sin resolver (esperado 0)',
       0, (SELECT count(*) FROM fact_garantia WHERE sk_geografia = -1)
UNION ALL

SELECT 7, 'Tipología sin resolver (esperado 0)',
       0, (SELECT count(*) FROM fact_garantia WHERE sk_tipologia = -1)
UNION ALL

-- 8. El saldo no se duplica: cada crédito atribuible aparece una sola vez
SELECT 8, 'Saldo del hecho = saldo de créditos atribuibles',
       (SELECT CAST(round(sum(c.saldo)) AS BIGINT)
        FROM int_credito_vigente c
        JOIN stg_id_repetido r ON r.corte = c.corte AND r.id_avaluo = c.id_avaluo
        WHERE r.n_avaluos_con_ese_id = 1),
       (SELECT CAST(round(sum(saldo)) AS BIGINT) FROM fact_garantia)
UNION ALL

-- 9. La cobertura cubre a todos los avalúos por cada regla activa
SELECT 9, 'Cobertura: avalúos x reglas activas',
       (SELECT count(*) FROM fact_garantia)
       * (SELECT count(*) FROM dim_regla WHERE activa = 'SI'),
       (SELECT sum(avaluos) FROM fact_cobertura_regla)
UNION ALL

-- 10. La evolución clasifica a todos los identificadores, sin residuo
SELECT 10, 'Evolución: identificadores clasificados',
       (SELECT count(*) FROM (SELECT DISTINCT id_avaluo FROM fact_garantia)),
       (SELECT count(*) FROM mart_evolucion)
UNION ALL

-- 11. Los incumplimientos del hecho coinciden con los contadores del validador
SELECT 11, 'Incidencias bloqueantes = suma de n_bloquea',
       (SELECT sum(n_bloquea) FROM fact_garantia),
       (SELECT count(*) FROM fact_incidencia WHERE accion = 'BLOQUEA')
ORDER BY orden;

-- Vista con el veredicto, que es lo que consume el tablero
CREATE OR REPLACE VIEW v_control_almacen AS
SELECT orden, comprobacion, esperado, obtenido,
       esperado - obtenido AS diferencia,
       CASE WHEN esperado = obtenido THEN 'OK' ELSE 'REVISAR' END AS resultado
FROM control_almacen
ORDER BY orden;
