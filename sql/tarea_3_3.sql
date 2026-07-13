-- Tarea 3.3: Top 5 candidatos CA por atribución determinística al Senado.
-- Fórmula: A = (votos_cand / votos_partido_CA) * votos_SE_partido
-- Se calcula a nivel municipio (sumando todas las zonas).
-- Se excluye codcan='0' (SOLO POR LA LISTA).

SELECT
    m.nombre                                                AS municipio,
    c.nomcan || ' ' || c.apecan                             AS candidato,
    COALESCE(p.nombre, 'Partido ' || cand_v.codpar)         AS partido_ca,
    cand_v.votos_cand                                       AS votos_candidato_ca,
    partido_ca.votos_partido_ca                              AS votos_partido_ca,
    partido_se.votos_partido_se                              AS votos_partido_se,
    ROUND(
        (CAST(cand_v.votos_cand AS REAL) / partido_ca.votos_partido_ca)
        * partido_se.votos_partido_se, 1
    )                                                       AS atribucion_se
FROM (
    -- Votos por candidato CA, agregados por municipio
    SELECT amb, codpar, codcan, SUM(votos) AS votos_cand
    FROM votos
    WHERE corporacion = 'CA' AND codcan != '0'
    GROUP BY amb, codpar, codcan
) cand_v
-- Total del partido en CA por municipio
JOIN (
    SELECT amb, codpar, SUM(votos) AS votos_partido_ca
    FROM votos
    WHERE corporacion = 'CA'
    GROUP BY amb, codpar
) partido_ca ON cand_v.amb = partido_ca.amb AND cand_v.codpar = partido_ca.codpar
-- Total del partido homólogo en SE por municipio (mapeo codpar CA→SE)
-- Verde: 5→57, Pacto: 87→92, CD: 10→10, Conservador: 2→2
JOIN (
    SELECT amb, codpar, SUM(votos) AS votos_partido_se
    FROM votos
    WHERE corporacion = 'SE'
    GROUP BY amb, codpar
) partido_se ON cand_v.amb = partido_se.amb
    AND partido_se.codpar = CASE cand_v.codpar
        WHEN '5'  THEN '57'   -- Alianza Verde
        WHEN '87' THEN '92'   -- Pacto Histórico
        WHEN '10' THEN '10'   -- Centro Democrático
        WHEN '2'  THEN '2'    -- Conservador
        ELSE NULL              -- sin homólogo SE conocido
    END
JOIN municipios m ON cand_v.amb = m.amb
JOIN candidatos c
    ON cand_v.codcan = c.codcan
   AND cand_v.amb    = c.amb
   AND cand_v.codpar = c.codpar
   AND c.corporacion = 'CA'
LEFT JOIN partidos p ON cand_v.codpar = p.codpar AND p.corporacion = 'CA'
WHERE partido_ca.votos_partido_ca > 0
ORDER BY atribucion_se DESC
LIMIT 5;
