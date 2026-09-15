-- =============================================================================
-- 04_marts.sql — Tablas de consumo para Power BI y el memo ejecutivo
-- =============================================================================

-- --- 1. Exposición por nivel de confiabilidad --------------------------------
-- Segmentada por moneda, siempre. No se consolida: ver D-03 y D-07.
CREATE OR REPLACE TABLE mart_exposicion AS
SELECT
    f.corte,
    f.moneda,
    f.nivel_confiabilidad,
    d.accion_sugerida,
    count(*)                                      AS avaluos,
    count(*) FILTER (f.tiene_credito)             AS avaluos_con_credito,
    sum(f.valor_garantia)                         AS valor_garantia,
    sum(f.saldo)                                  AS saldo,
    round(avg(f.ltv), 4)                          AS ltv_promedio,
    round(median(f.dias_antiguedad))              AS dias_antiguedad_mediana,
    round(100.0 * sum(f.saldo) / sum(sum(f.saldo)) OVER (PARTITION BY f.corte, f.moneda), 2)
                                                  AS pct_saldo_del_corte
FROM fact_garantia f
JOIN dim_confiabilidad d ON d.sk_confiabilidad = f.sk_confiabilidad
GROUP BY f.corte, f.moneda, f.nivel_confiabilidad, d.accion_sugerida;


-- --- 2. Pareto de reglas ------------------------------------------------------
-- Qué reglas concentran los incumplimientos y cuánta exposición arrastran.
CREATE OR REPLACE TABLE mart_pareto_reglas AS
WITH por_regla AS (
    SELECT
        i.corte,
        i.rule_id,
        r.nombre,
        r.dimension,
        i.accion,
        r.responsable,
        count(*)                             AS incidencias,
        count(DISTINCT i.id_avaluo || '|' || coalesce(i.numero_finca, '(sin finca)')) AS avaluos_afectados
    FROM fact_incidencia i
    JOIN dim_regla r ON r.sk_regla = i.sk_regla
    GROUP BY i.corte, i.rule_id, r.nombre, r.dimension, i.accion, r.responsable
)
SELECT
    *,
    round(100.0 * incidencias / sum(incidencias) OVER (PARTITION BY corte), 2) AS pct,
    round(100.0 * sum(incidencias) OVER (
              PARTITION BY corte ORDER BY incidencias DESC
              ROWS UNBOUNDED PRECEDING)
          / sum(incidencias) OVER (PARTITION BY corte), 2) AS pct_acumulado,
    row_number() OVER (PARTITION BY corte ORDER BY incidencias DESC) AS ranking
FROM por_regla;


-- --- 3. Cobertura de reglas ---------------------------------------------------
-- Una regla que solo puede evaluar el 85 % de la cartera no puede presentarse
-- como si cubriera todo.
CREATE OR REPLACE TABLE mart_cobertura_reglas AS
SELECT
    c.corte,
    c.rule_id,
    r.nombre,
    r.accion,
    c.avaluos,
    c.cumple,
    c.incumple,
    c.no_aplica,
    round(100.0 * (c.cumple + c.incumple) / c.avaluos, 2) AS pct_cobertura
FROM fact_cobertura_regla c
JOIN dim_regla r ON r.sk_regla = c.sk_regla;


-- --- 4. Evolución entre cortes ------------------------------------------------
-- El FULL OUTER JOIN es necesario, no decorativo: hay avalúos que están en marzo
-- y no en abril (salieron de cartera) y viceversa (entraron).
--
-- Se agrega primero por (corte, id_avaluo) porque un identificador puede
-- corresponder a más de un avalúo: es justo lo que detecta R-01. Sin ese paso,
-- el join multiplicaría filas.
CREATE OR REPLACE TABLE mart_evolucion AS
WITH por_id AS (
    SELECT
        corte,
        id_avaluo,
        count(*)                                       AS avaluos_con_ese_id,
        max(CASE WHEN nivel_confiabilidad <> 'CONFIABLE' THEN 1 ELSE 0 END) AS incumple,
        max(CASE WHEN nivel_confiabilidad = 'NO_CONFIABLE' THEN 1 ELSE 0 END) AS bloquea,
        sum(saldo)                                     AS saldo,
        any_value(moneda)                              AS moneda
    FROM fact_garantia
    GROUP BY corte, id_avaluo
),
m AS (SELECT * FROM por_id WHERE corte = (SELECT min(corte) FROM por_id)),
a AS (SELECT * FROM por_id WHERE corte = (SELECT max(corte) FROM por_id))
SELECT
    coalesce(m.id_avaluo, a.id_avaluo)          AS id_avaluo,
    coalesce(m.moneda, a.moneda)                AS moneda,
    m.incumple                                  AS incumplia_marzo,
    a.incumple                                  AS incumple_abril,
    m.saldo                                     AS saldo_marzo,
    a.saldo                                     AS saldo_abril,
    coalesce(m.avaluos_con_ese_id, 0)           AS avaluos_marzo,
    coalesce(a.avaluos_con_ese_id, 0)           AS avaluos_abril,
    CASE
        WHEN m.id_avaluo IS NULL AND a.incumple = 1 THEN 'NUEVO'
        WHEN m.id_avaluo IS NULL                    THEN 'ENTRA_CUMPLIENDO'
        WHEN a.id_avaluo IS NULL AND m.incumple = 1 THEN 'SALIO'
        WHEN a.id_avaluo IS NULL                    THEN 'SALIO_CUMPLIENDO'
        WHEN m.incumple = 1 AND a.incumple = 1      THEN 'PERSISTENTE'
        WHEN m.incumple = 1 AND a.incumple = 0      THEN 'CORREGIDO'
        WHEN m.incumple = 0 AND a.incumple = 1      THEN 'NUEVO'
        ELSE 'CUMPLE'
    END AS categoria
FROM m FULL OUTER JOIN a USING (id_avaluo);


-- --- 5. Concentración geográfica ----------------------------------------------
CREATE OR REPLACE TABLE mart_concentracion AS
SELECT
    f.corte,
    g.zona,
    g.provincia,
    g.canton,
    f.moneda,
    count(*)                                           AS avaluos,
    count(*) FILTER (f.nivel_confiabilidad = 'NO_CONFIABLE') AS no_confiables,
    round(100.0 * count(*) FILTER (f.nivel_confiabilidad <> 'CONFIABLE') / count(*), 2)
                                                       AS tasa_incumplimiento,
    sum(f.saldo)                                       AS saldo,
    sum(f.exposicion_no_confiable)                     AS exposicion_no_confiable
FROM fact_garantia f
JOIN dim_geografia g ON g.sk_geografia = f.sk_geografia
GROUP BY f.corte, g.zona, g.provincia, g.canton, f.moneda;


-- --- 6. Desempeño por perito --------------------------------------------------
-- Diagnóstico, no castigo: identifica dónde hace falta capacitación o dónde una
-- plantilla de captura está induciendo el error.
CREATE OR REPLACE TABLE mart_perito AS
SELECT
    f.corte,
    p.perito_id,
    p.activo,
    count(*)                                                  AS avaluos,
    count(*) FILTER (f.nivel_confiabilidad <> 'CONFIABLE')     AS avaluos_con_incumplimiento,
    count(*) FILTER (f.nivel_confiabilidad = 'NO_CONFIABLE')   AS avaluos_no_confiables,
    round(100.0 * count(*) FILTER (f.nivel_confiabilidad <> 'CONFIABLE') / count(*), 2)
                                                              AS tasa_incumplimiento,
    sum(f.exposicion_no_confiable)                            AS exposicion_no_confiable
FROM fact_garantia f
JOIN dim_perito p ON p.sk_perito = f.sk_perito
GROUP BY f.corte, p.perito_id, p.activo;


-- --- 7. Lista de trabajo ------------------------------------------------------
-- La salida accionable del proyecto. Orden lexicográfico deliberado:
-- primero todos los NO_CONFIABLE por saldo descendente, después los REVISAR.
-- Sin índices ponderados: cualquier peso habría que defenderlo después.
CREATE OR REPLACE TABLE mart_lista_trabajo AS
WITH ultimo AS (SELECT max(corte) AS corte FROM fact_garantia),
-- Una incidencia puede repetirse dentro del mismo corte. Se deduplica antes de
-- agregar para que el detalle no repita motivos que la lista de reglas sí une.
incidencias_unicas AS (
    SELECT DISTINCT corte, id_avaluo, numero_finca, rule_id, condicion_esperada
    FROM fact_incidencia
),
motivos AS (
    -- El detalle se arma pegando cada regla a su propia condición y ordenando
    -- por rule_id, igual que reglas_incumplidas. Agregar las dos columnas por
    -- separado no garantiza el mismo orden: el perito leería el motivo de una
    -- regla junto al identificador de otra.
    SELECT i.corte, i.id_avaluo, i.numero_finca,
           string_agg(DISTINCT i.rule_id, ', ' ORDER BY i.rule_id) AS reglas_incumplidas,
           string_agg(i.rule_id || ' ' || coalesce(r.nombre, 'regla sin catalogar')
                      || ': ' || i.condicion_esperada,
                      ' | ' ORDER BY i.rule_id)                    AS detalle,
           string_agg(DISTINCT r.responsable, ', ')                AS responsables
    FROM incidencias_unicas i
    LEFT JOIN dim_regla r ON r.rule_id = i.rule_id
    GROUP BY i.corte, i.id_avaluo, i.numero_finca
),
candidatos AS (
    SELECT
        f.corte, f.id_avaluo, f.numero_finca,
        g.provincia, g.canton, g.distrito, g.zona,
        t.tipologia, p.perito_id, p.activo AS perito_activo,
        f.nivel_confiabilidad, d.accion_sugerida,
        f.moneda, f.valor_garantia, f.saldo, f.ltv,
        -- La fecha del avalúo, no sólo su antigüedad: el expediente se busca por
        -- fecha y la re-inspección se agenda contra ella.
        f.fecha_valor, f.dias_antiguedad, f.saldo_equivalente_crc,
        m.reglas_incumplidas, m.detalle, m.responsables,
        row_number() OVER (
            ORDER BY d.sk_confiabilidad DESC,                 -- NO_CONFIABLE primero
                     f.saldo_equivalente_crc DESC NULLS LAST  -- luego mayor exposición
        ) AS prioridad
    FROM fact_garantia f
    JOIN ultimo u                ON u.corte = f.corte
    JOIN dim_confiabilidad d     ON d.sk_confiabilidad = f.sk_confiabilidad
    LEFT JOIN dim_geografia g    ON g.sk_geografia = f.sk_geografia
    LEFT JOIN dim_tipologia t    ON t.sk_tipologia = f.sk_tipologia
    LEFT JOIN dim_perito p       ON p.sk_perito = f.sk_perito
    LEFT JOIN motivos m          ON m.corte = f.corte
                                AND m.id_avaluo = f.id_avaluo
                                AND m.numero_finca IS NOT DISTINCT FROM f.numero_finca
    WHERE f.nivel_confiabilidad <> 'CONFIABLE'
)
SELECT *,
       prioridad <= (SELECT valor FROM stg_parametros WHERE parametro = 'capacidad_mensual_revision')
           AS entra_este_mes
FROM candidatos;


-- --- 8. La comparación que justifica el proyecto ------------------------------
-- Con la misma capacidad, ¿cuánta exposición no confiable se cubre priorizando
-- por exposición frente a priorizar por antigüedad, que es el criterio actual?
--
-- Es una comparación de dos ordenamientos sobre los mismos datos, no una
-- estimación con supuestos. La razón entre ambos es adimensional: no depende
-- del tipo de cambio salvo por el orden dentro de cada lista.
CREATE OR REPLACE TABLE mart_comparacion_priorizacion AS
WITH cap AS (SELECT CAST(valor AS INTEGER) AS n FROM stg_parametros
             WHERE parametro = 'capacidad_mensual_revision'),
ultimo AS (SELECT max(corte) AS corte FROM fact_garantia),
base AS (
    SELECT f.*, d.sk_confiabilidad
    FROM fact_garantia f
    JOIN ultimo u ON u.corte = f.corte
    JOIN dim_confiabilidad d ON d.sk_confiabilidad = f.sk_confiabilidad
),
-- (1) Criterio propuesto: lo no confiable primero, de mayor a menor exposición
por_exposicion AS (
    SELECT * FROM base WHERE nivel_confiabilidad <> 'CONFIABLE'
    ORDER BY sk_confiabilidad DESC, saldo_equivalente_crc DESC NULLS LAST
    LIMIT (SELECT n FROM cap)
),
-- (2) Criterio actual: los avalúos más viejos de toda la cartera
por_antiguedad AS (
    SELECT * FROM base
    ORDER BY dias_antiguedad DESC NULLS LAST
    LIMIT (SELECT n FROM cap)
),
-- (3) Comparación justa: mismo universo que (1), pero ordenado por antigüedad.
-- Aísla el efecto del criterio de orden del efecto de mirar la calidad del dato.
por_antiguedad_filtrado AS (
    SELECT * FROM base WHERE nivel_confiabilidad <> 'CONFIABLE'
    ORDER BY dias_antiguedad DESC NULLS LAST
    LIMIT (SELECT n FROM cap)
),
resumen AS (
    SELECT 1 AS orden, 'Por exposición en riesgo' AS criterio,
           'Propuesto: prioriza lo no confiable de mayor saldo' AS descripcion, * FROM (
        SELECT count(*) AS casos_revisados,
               count(*) FILTER (nivel_confiabilidad = 'NO_CONFIABLE') AS no_confiables_atendidos,
               sum(exposicion_no_confiable) FILTER (moneda = 'CRC')   AS exposicion_cubierta_crc,
               sum(exposicion_no_confiable) FILTER (moneda = 'USD')   AS exposicion_cubierta_usd,
               sum(CASE WHEN nivel_confiabilidad = 'NO_CONFIABLE' THEN saldo_equivalente_crc END)
                                                                      AS exposicion_equivalente
        FROM por_exposicion)
    UNION ALL
    SELECT 2, 'Por antigüedad, cartera completa',
           'Criterio actual: los avalúos más viejos, sin mirar calidad', * FROM (
        SELECT count(*), count(*) FILTER (nivel_confiabilidad = 'NO_CONFIABLE'),
               sum(exposicion_no_confiable) FILTER (moneda = 'CRC'),
               sum(exposicion_no_confiable) FILTER (moneda = 'USD'),
               sum(CASE WHEN nivel_confiabilidad = 'NO_CONFIABLE' THEN saldo_equivalente_crc END)
        FROM por_antiguedad)
    UNION ALL
    SELECT 3, 'Por antigüedad, solo los marcados',
           'Comparación justa: mismo universo, orden por antigüedad', * FROM (
        SELECT count(*), count(*) FILTER (nivel_confiabilidad = 'NO_CONFIABLE'),
               sum(exposicion_no_confiable) FILTER (moneda = 'CRC'),
               sum(exposicion_no_confiable) FILTER (moneda = 'USD'),
               sum(CASE WHEN nivel_confiabilidad = 'NO_CONFIABLE' THEN saldo_equivalente_crc END)
        FROM por_antiguedad_filtrado)
)
SELECT *,
       (SELECT count(*) FROM base WHERE nivel_confiabilidad = 'NO_CONFIABLE')
           AS no_confiables_en_cartera,
       round(100.0 * no_confiables_atendidos
             / (SELECT count(*) FROM base WHERE nivel_confiabilidad = 'NO_CONFIABLE'), 1)
           AS pct_no_confiables_cubiertos,
       round(exposicion_equivalente
             / nullif(max(CASE WHEN orden = 2 THEN exposicion_equivalente END) OVER (), 0), 2)
           AS veces_vs_criterio_actual,
       round(exposicion_equivalente
             / nullif(max(CASE WHEN orden = 3 THEN exposicion_equivalente END) OVER (), 0), 2)
           AS veces_vs_mismo_universo
FROM resumen
ORDER BY orden;


-- --- 9. Crédito no atribuible -------------------------------------------------
-- El costo en dinero de un identificador duplicado: saldo que no puede asignarse
-- a ninguna garantía concreta. Es el puente entre "hay 40 avalúos con R-01" y
-- una cifra que un gerente entiende.
CREATE OR REPLACE TABLE mart_credito_no_atribuible AS
SELECT
    c.corte,
    c.moneda,
    'Identificador compartido por varios avalúos' AS motivo,
    count(DISTINCT c.id_credito)                  AS creditos,
    sum(c.saldo)                                  AS saldo_sin_atribuir
FROM stg_creditos c
JOIN stg_id_repetido r ON r.corte = c.corte AND r.id_avaluo = c.id_avaluo
WHERE c.estado = 'VIGENTE' AND r.n_avaluos_con_ese_id > 1
GROUP BY c.corte, c.moneda
UNION ALL
SELECT
    c.corte,
    c.moneda,
    'Sin avalúo correspondiente en el corte',
    count(DISTINCT c.id_credito),
    sum(c.saldo)
FROM stg_creditos c
LEFT JOIN stg_id_repetido r ON r.corte = c.corte AND r.id_avaluo = c.id_avaluo
WHERE c.estado = 'VIGENTE' AND r.id_avaluo IS NULL
GROUP BY c.corte, c.moneda;
