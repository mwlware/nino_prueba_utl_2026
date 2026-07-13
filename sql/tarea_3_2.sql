-- Tarea 3.2: Dominancia — zonas donde un candidato concentra >60% de los votos
--             de su partido en esa zona.
-- Fórmula: votos_candidato / votos_partido_en_zona > 0.60
-- Se excluye codcan='0' (SOLO POR LA LISTA) porque no es un candidato real.
-- NOTA: el grano más fino disponible es ZONA (no mesa). Se documenta esta limitación.

SELECT
    m.nombre                                                AS municipio,
    v.zona,
    v.corporacion,
    COALESCE(p.nombre, 'Partido ' || v.codpar)              AS partido,
    c.nomcan || ' ' || c.apecan                             AS candidato,
    v.votos                                                 AS votos_candidato,
    partido_zona.votos_partido                              AS votos_partido_zona,
    ROUND(CAST(v.votos AS REAL) / partido_zona.votos_partido * 100, 1) AS pct_dominancia
FROM votos v
-- Total del partido en la misma zona (suma todos los codcan incluyendo lista)
JOIN (
    SELECT corporacion, zona, codpar, SUM(votos) AS votos_partido
    FROM votos
    GROUP BY corporacion, zona, codpar
) partido_zona
    ON v.corporacion = partido_zona.corporacion
   AND v.zona        = partido_zona.zona
   AND v.codpar      = partido_zona.codpar
JOIN municipios m ON v.amb = m.amb
JOIN candidatos c
    ON v.codcan      = c.codcan
   AND v.amb         = c.amb
   AND v.codpar      = c.codpar
   AND v.corporacion = c.corporacion
LEFT JOIN partidos p
    ON v.codpar      = p.codpar
   AND v.corporacion = p.corporacion
WHERE v.codcan != '0'                                       -- excluir voto de lista
  AND partido_zona.votos_partido > 0                        -- evitar división por cero
  AND CAST(v.votos AS REAL) / partido_zona.votos_partido > 0.60
ORDER BY pct_dominancia DESC;
