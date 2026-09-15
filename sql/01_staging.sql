-- =============================================================================
-- 01_staging.sql — Tipado y normalización
-- =============================================================================
-- Los CSV se leen como texto y se convierten aquí con TRY_CAST. Un valor como
-- "N/A" en un campo numérico no rompe la carga: queda en NULL y las capas de
-- arriba lo tratan como ausencia. El validador ya lo marcó con R-02.
--
-- Se usa SELECT * REPLACE para conservar las columnas R-01..R-10 sin nombrarlas:
-- cuáles existen depende de qué reglas estén activas en el catálogo.
-- =============================================================================

CREATE OR REPLACE TABLE stg_avaluos AS
SELECT * REPLACE (
    TRY_CAST(fecha_inspeccion  AS DATE)    AS fecha_inspeccion,
    TRY_CAST(fecha_valor       AS DATE)    AS fecha_valor,
    TRY_CAST(fecha_informe     AS DATE)    AS fecha_informe,
    TRY_CAST(latitud           AS DOUBLE)  AS latitud,
    TRY_CAST(longitud          AS DOUBLE)  AS longitud,
    TRY_CAST(area_terreno_m2                AS DECIMAL(14,2)) AS area_terreno_m2,
    TRY_CAST(valor_unitario_terreno_m2      AS DECIMAL(16,2)) AS valor_unitario_terreno_m2,
    TRY_CAST(area_construccion_m2           AS DECIMAL(14,2)) AS area_construccion_m2,
    TRY_CAST(valor_unitario_construccion_m2 AS DECIMAL(16,2)) AS valor_unitario_construccion_m2,
    TRY_CAST(valor_obras_complementarias    AS DECIMAL(18,2)) AS valor_obras_complementarias,
    TRY_CAST(valor_total_inmueble           AS DECIMAL(18,2)) AS valor_total_inmueble,
    TRY_CAST(n_bloquea AS INTEGER) AS n_bloquea,
    TRY_CAST(n_revisa  AS INTEGER) AS n_revisa
)
FROM read_csv('@RAIZ@/data/output/avaluos_validados.csv', all_varchar = true);

CREATE OR REPLACE TABLE stg_creditos AS
SELECT
    corte,
    id_credito,
    id_avaluo,
    moneda,
    TRY_CAST(saldo AS DECIMAL(18,2))       AS saldo,
    TRY_CAST(fecha_desembolso AS DATE)     AS fecha_desembolso,
    estado
FROM read_csv('@RAIZ@/data/raw/creditos.csv', all_varchar = true);

CREATE OR REPLACE TABLE stg_incidencias AS
SELECT corte, id_avaluo, numero_finca, rule_id, accion,
       campo, valor_observado, condicion_esperada
FROM read_csv('@RAIZ@/data/output/incidencias.csv', all_varchar = true);

CREATE OR REPLACE TABLE stg_control_validador AS
SELECT * FROM read_csv('@RAIZ@/data/output/control_cifras.csv');

-- --- Referencias -------------------------------------------------------------
CREATE OR REPLACE TABLE stg_geografia  AS SELECT * FROM read_csv('@RAIZ@/reference/geografia.csv');
CREATE OR REPLACE TABLE stg_tipologias AS SELECT * FROM read_csv('@RAIZ@/reference/tipologias.csv');
CREATE OR REPLACE TABLE stg_peritos    AS SELECT * FROM read_csv('@RAIZ@/reference/peritos.csv');
CREATE OR REPLACE TABLE stg_reglas     AS SELECT * FROM read_csv('@RAIZ@/reference/reglas_datos.csv');

CREATE OR REPLACE TABLE stg_parametros AS
SELECT parametro, TRY_CAST(valor AS DOUBLE) AS valor, unidad, fuente
FROM read_csv('@RAIZ@/reference/parametros.csv', all_varchar = true);

-- --- Resultado por avalúo y regla, en formato largo ---------------------------
-- El validador entrega una columna por regla. Para analizar cobertura hace falta
-- el formato largo. El patrón '^R-' evita listar las reglas a mano: si mañana se
-- activa R-09, aparece sola.
CREATE OR REPLACE TABLE stg_resultado_regla AS
SELECT corte, id_avaluo, numero_finca, rule_id, estado
FROM (
    UNPIVOT (SELECT corte, id_avaluo, numero_finca, COLUMNS('^R-') FROM stg_avaluos)
    ON COLUMNS('^R-')
    INTO NAME rule_id VALUE estado
);

-- --- Identificadores repetidos ------------------------------------------------
-- Cuántos avalúos comparten cada id_avaluo dentro de un corte. Es lo que R-01
-- detecta, y tiene una consecuencia que arrastra todo el modelo: cuando dos
-- avalúos comparten identificador, el crédito no puede atribuirse a ninguno.
CREATE OR REPLACE TABLE stg_id_repetido AS
SELECT corte, id_avaluo, count(*) AS n_avaluos_con_ese_id
FROM stg_avaluos
GROUP BY corte, id_avaluo;
