-- =============================================================================
-- 03_hechos.sql — Las dos tablas de hechos
-- =============================================================================
-- fact_garantia    grano: un avalúo en un corte          8.000 filas
-- fact_incidencia  grano: un incumplimiento detectado    ~2.000 filas
--
-- Comparten dimensiones y NUNCA se unen entre sí. Un avalúo con tres
-- incumplimientos aparece tres veces en fact_incidencia: si se uniera con
-- fact_garantia, su valor de garantía se sumaría tres veces y una cartera de
-- ₡80 mil millones se reportaría como ₡95 mil millones.
--
-- Por eso fact_incidencia lleva sus propias claves a geografía, perito y
-- tipología: el Pareto de reglas se puede filtrar por cantón sin tocar la otra
-- tabla de hechos.
-- =============================================================================

-- --- El crédito no siempre es atribuible --------------------------------------
-- Consecuencia directa de R-01: si dos avalúos comparten identificador, no hay
-- forma de saber cuál respalda el crédito. Atribuirlo a ambos duplicaría el
-- saldo; atribuirlo a uno al azar sería inventar. Se deja sin atribuir y se
-- reporta aparte, en mart_credito_no_atribuible.
CREATE OR REPLACE TABLE int_credito_vigente AS
SELECT corte, id_avaluo, sum(saldo) AS saldo, count(*) AS n_creditos
FROM stg_creditos
WHERE estado = 'VIGENTE' AND saldo > 0
GROUP BY corte, id_avaluo;

CREATE OR REPLACE TABLE fact_garantia AS
WITH base AS (
    SELECT
        a.*,
        r.n_avaluos_con_ese_id,
        (r.n_avaluos_con_ese_id = 1) AS credito_atribuible,
        c.saldo                      AS saldo_credito,
        p.valor                      AS tipo_cambio
    FROM stg_avaluos a
    JOIN stg_id_repetido r          ON r.corte = a.corte AND r.id_avaluo = a.id_avaluo
    LEFT JOIN int_credito_vigente c ON c.corte = a.corte AND c.id_avaluo = a.id_avaluo
    CROSS JOIN (SELECT valor FROM stg_parametros WHERE parametro = 'tipo_cambio_ordenamiento') p
)
SELECT
    -- Claves a dimensiones
    dc.sk_corte,
    coalesce(df.sk_fecha, -1)   AS sk_fecha_valor,
    coalesce(dg.sk_geografia, -1) AS sk_geografia,
    coalesce(dt.sk_tipologia, -1) AS sk_tipologia,
    coalesce(dp.sk_perito, -1)    AS sk_perito,
    dcf.sk_confiabilidad,

    -- Dimensiones degeneradas: identifican la fila, no tienen atributos propios
    b.id_avaluo,
    b.numero_finca,

    -- Atributos de la fila
    b.corte,
    b.moneda,
    b.finalidad,
    b.fecha_valor,
    b.nivel_confiabilidad,
    b.credito_atribuible,
    (b.saldo_credito IS NOT NULL AND b.credito_atribuible) AS tiene_credito,

    -- Métricas
    b.valor_total_inmueble AS valor_garantia,
    CASE WHEN b.credito_atribuible THEN b.saldo_credito END AS saldo,
    CASE WHEN b.credito_atribuible AND b.valor_total_inmueble > 0
         THEN round(b.saldo_credito / b.valor_total_inmueble, 4) END AS ltv,
    date_diff('day', b.fecha_valor, dc.fecha_corte) AS dias_antiguedad,
    b.n_bloquea,
    b.n_revisa,

    -- Saldo llevado a colones SOLO para ordenar y comparar. Ver D-07:
    -- la exposición se reporta siempre segmentada por moneda.
    CASE WHEN b.credito_atribuible
         THEN b.saldo_credito * CASE WHEN b.moneda = 'USD' THEN b.tipo_cambio ELSE 1 END END
         AS saldo_equivalente_crc,

    -- Exposición en riesgo: saldo respaldado por una garantía no confiable
    CASE WHEN b.nivel_confiabilidad = 'NO_CONFIABLE' AND b.credito_atribuible
         THEN b.saldo_credito END AS exposicion_no_confiable

FROM base b
JOIN dim_corte dc            ON dc.corte = b.corte
JOIN dim_confiabilidad dcf   ON dcf.nivel = b.nivel_confiabilidad
LEFT JOIN dim_fecha df       ON df.fecha = b.fecha_valor
LEFT JOIN dim_geografia dg   ON dg.provincia = b.provincia
                            AND dg.canton    = b.canton
                            AND dg.distrito  = b.distrito
LEFT JOIN dim_tipologia dt   ON dt.tipologia = b.tipologia_inmueble
LEFT JOIN dim_perito dp      ON dp.perito_id = b.perito_id;


CREATE OR REPLACE TABLE fact_incidencia AS
SELECT
    g.sk_corte,
    dr.sk_regla,
    g.sk_fecha_valor,
    g.sk_geografia,
    g.sk_tipologia,
    g.sk_perito,
    g.sk_confiabilidad,

    i.id_avaluo,
    i.numero_finca,
    i.corte,
    i.rule_id,
    i.accion,
    i.campo,
    i.valor_observado,
    i.condicion_esperada,

    1 AS incidencias
FROM stg_incidencias i
JOIN dim_regla dr ON dr.rule_id = i.rule_id
-- numero_finca desambigua los pares de R-01, que comparten id_avaluo a propósito.
-- Se compara con IS NOT DISTINCT FROM, no con '=': R-02 permite que numero_finca
-- llegue vacío, y en SQL NULL = NULL es falso. Con '=' se perdían las incidencias
-- de los avalúos sin número de finca, que son justamente los que más importan.
JOIN fact_garantia g ON g.corte = i.corte
                    AND g.id_avaluo = i.id_avaluo
                    AND g.numero_finca IS NOT DISTINCT FROM i.numero_finca;


-- Cobertura: qué pudo evaluarse y qué no. NO_APLICA no es CUMPLE.
CREATE OR REPLACE TABLE fact_cobertura_regla AS
SELECT
    dc.sk_corte,
    dr.sk_regla,
    rr.corte,
    rr.rule_id,
    count(*)                                        AS avaluos,
    count(*) FILTER (rr.estado = 'CUMPLE')          AS cumple,
    count(*) FILTER (rr.estado = 'INCUMPLE')        AS incumple,
    count(*) FILTER (rr.estado = 'NO_APLICA')       AS no_aplica
FROM stg_resultado_regla rr
JOIN dim_corte dc ON dc.corte = rr.corte
JOIN dim_regla dr ON dr.rule_id = rr.rule_id
GROUP BY dc.sk_corte, dr.sk_regla, rr.corte, rr.rule_id;
