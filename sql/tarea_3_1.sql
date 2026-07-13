-- Tarea 3.1: Ratio de arrastre Alianza Verde CA→SE por zona y municipio.
-- Fórmula: votos_SE_Verde / votos_CA_Verde
-- Verde CA = codpar 5, Verde SE = codpar 57.
-- NOTA: el grano más fino disponible en la API es ZONA (no puesto ni mesa).
--       Se documenta esta limitación; la query opera al grano zona.

SELECT
    m.nombre                                      AS municipio,
    ca.zona                                       AS zona,
    ca.votos_ca                                   AS votos_ca_verde,
    se.votos_se                                   AS votos_se_verde,
    ROUND(CAST(se.votos_se AS REAL) / ca.votos_ca, 3) AS ratio_arrastre
FROM (
    SELECT amb, zona, SUM(votos) AS votos_ca
    FROM votos
    WHERE corporacion = 'CA' AND codpar = '5'
    GROUP BY amb, zona
) ca
JOIN (
    SELECT amb, zona, SUM(votos) AS votos_se
    FROM votos
    WHERE corporacion = 'SE' AND codpar = '57'
    GROUP BY amb, zona
) se ON ca.zona = se.zona AND ca.amb = se.amb
JOIN municipios m ON ca.amb = m.amb
WHERE ca.votos_ca > 0
ORDER BY m.nombre, ca.zona;
