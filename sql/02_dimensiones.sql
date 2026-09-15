-- =============================================================================
-- 02_dimensiones.sql — Las siete dimensiones
-- =============================================================================
-- Todas usan clave subrogada entera y conservan la clave natural como atributo.
-- Las que pueden recibir un valor ausente llevan un miembro -1 "NO INFORMADO":
-- R-02 permite que llegue un avalúo sin perito, y ese avalúo debe seguir
-- contándose en la cartera, no desaparecer del modelo por un LEFT JOIN fallido.
--
-- Los nombres de mes se resuelven con una lista literal y no con strftime('%B'),
-- que en DuckDB devuelve inglés sin importar la configuración regional. Estas
-- etiquetas llegan a los segmentadores del tablero, así que se ven.
-- =============================================================================

CREATE OR REPLACE MACRO mes_largo(n) AS
    (['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
      'setiembre', 'octubre', 'noviembre', 'diciembre'])[n];

CREATE OR REPLACE MACRO mes_corto(n) AS
    (['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago',
      'set', 'oct', 'nov', 'dic'])[n];

CREATE OR REPLACE TABLE dim_corte AS
SELECT
    row_number() OVER (ORDER BY corte)                      AS sk_corte,
    corte,
    last_day(TRY_CAST(corte || '-01' AS DATE))              AS fecha_corte,
    mes_largo(month(TRY_CAST(corte || '-01' AS DATE)))
        || ' ' || year(TRY_CAST(corte || '-01' AS DATE))    AS etiqueta,
    row_number() OVER (ORDER BY corte)                      AS orden
FROM (SELECT DISTINCT corte FROM stg_avaluos);

CREATE OR REPLACE TABLE dim_fecha AS
WITH rango AS (
    SELECT least(min(fecha_inspeccion), min(fecha_valor))    AS desde,
           greatest(max(fecha_informe), max(fecha_valor))    AS hasta
    FROM stg_avaluos
)
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER) AS sk_fecha,
    d                                      AS fecha,
    year(d)                                AS anio,
    month(d)                               AS mes,
    quarter(d)                             AS trimestre,
    strftime(d, '%Y-%m')                   AS anio_mes,
    mes_corto(month(d)) || ' ' || year(d)  AS etiqueta_mes
FROM rango, unnest(generate_series(desde, hasta, INTERVAL 1 DAY)) AS t(d);

INSERT INTO dim_fecha VALUES (-1, NULL, NULL, NULL, NULL, 'No informado', 'No informado');

CREATE OR REPLACE TABLE dim_geografia AS
SELECT
    row_number() OVER (ORDER BY provincia, canton, distrito) AS sk_geografia,
    provincia, canton, distrito, zona, radio_km
FROM stg_geografia;

INSERT INTO dim_geografia VALUES (-1, 'No informado', 'No informado', 'No informado', 'No informado', NULL);

CREATE OR REPLACE TABLE dim_tipologia AS
SELECT
    row_number() OVER (ORDER BY tipologia) AS sk_tipologia,
    tipologia, requiere_construccion, cobertura_min, cobertura_max, moneda_habitual
FROM stg_tipologias;

INSERT INTO dim_tipologia VALUES (-1, 'No informado', 'NO_APLICA', NULL, NULL, NULL);

CREATE OR REPLACE TABLE dim_perito AS
SELECT
    row_number() OVER (ORDER BY perito_id) AS sk_perito,
    perito_id, activo
FROM stg_peritos;

INSERT INTO dim_perito VALUES (-1, 'No informado', 'NO');

-- Traduce el resultado técnico a la acción de negocio. Es la dimensión que
-- convierte "incumple R-04" en "hay que re-inspeccionar".
CREATE OR REPLACE TABLE dim_confiabilidad AS
SELECT * FROM (VALUES
    (1, 'CONFIABLE',    'Confiable',    'Ninguna',                 'Sin incumplimientos'),
    (2, 'REVISAR',      'Revisar',      'Verificación documental', 'Solo incumplimientos que no bloquean'),
    (3, 'NO_CONFIABLE', 'No confiable', 'Re-inspección',           'Al menos un incumplimiento bloqueante')
) AS t(sk_confiabilidad, nivel, etiqueta, accion_sugerida, definicion);

CREATE OR REPLACE TABLE dim_regla AS
SELECT
    row_number() OVER (ORDER BY rule_id) AS sk_regla,
    rule_id, nombre, dimension, accion, campo_principal, responsable,
    activa, justificacion
FROM stg_reglas;
