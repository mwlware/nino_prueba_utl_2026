# CLAUDE.md — Prueba Técnica UTL Senado · Analista de Datos (Congreso Boyacá 2026)

Contexto persistente para Claude Code. La API ya fue mapeada con datos reales (ver abajo). No inventes campos: todo lo aquí descrito está verificado contra el JSON real, salvo lo marcado como PENDIENTE.

## Qué es
Pipeline de datos del **Congreso 2026** (elección del 8 de marzo de 2026), dos corporaciones: **Cámara (CA)** y **Senado (SE)**, para 4 municipios de Boyacá. Análisis central: **arrastre CA→SE**. Entrega en repo GitHub PUBLIC evaluado por `outputs/generar_manifest.py`.

## Fuente de datos: API de la Registraduría (JSON estático, sin auth)
```
https://resultadospreccongreso2026.registraduria.gov.co/json/ACT/{CORP}/{CODIGO}.json
```
- `{CORP}`: `CA` (Cámara) o `SE` (Senado).
- `{CODIGO}`: código territorial interno de la Registraduría (NO es DANE). Boyacá = `0700`. Municipio = 7 dígitos.
- Sin cabeceras especiales, sin cookies, sin token. `requests.get(url).json()`.

### Municipios objetivo (código `amb`)
| Municipio | amb |
|---|---|
| Tunja | 0700001 |
| Duitama | 0700079 |
| Sogamoso | 0700277 |
| Paipa | 0700181 |

El JSON de departamento (`0700`) trae en `mapagan` el mapa completo `amb → nombre` de todos los municipios; úsalo como nomenclator (Reto 1.1) en vez de hardcodear.

## Estructura real del JSON (verificada con /CA/0700001.json)
Nivel raíz:
- `elec`, `amb` (código del ámbito consultado), `mdhm` (fecha/hora del boletín; "03082211" = 8 marzo 22:11).
- `totales.act`: agregados del ámbito (`metota` mesas instaladas, `mesesc` mesas escrutadas, `pmesesc`, `votant`, `votnul`, `votblan`, `votval`, ...).
- `camaras`: array. Cada elemento tiene un `cam`:
  - `cam="1"` → Cámara ordinaria territorial (la que importa para el análisis).
  - `cam="4"` → circunscripción especial indígena. `cam="5"` → especial afro. (Guárdalas si quieres, pero el arrastre se hace sobre `cam="1"`.)
  - Dentro: `totales.act` y `partotabla` (array de partidos).
- `partotabla[].act`: `codpar` (código de partido), `cam`, `vot` (total del partido en el ámbito), `pvot`, y `cantotabla` (array de candidatos).
- `cantotabla[]`: `amb`, `codcan` (código candidato; **`0` = "SOLO POR LA LISTA"**), `cedula`, `nomcan`, `apecan`, `vot`, `pvot`, `pref`, `empate`.
- `mapagan`: array a nivel DEPARTAMENTO con el ganador por municipio: `amb`, `codpar` (partido ganador), `vot`, `votant`, `votcan`, `mesesc`, `nombre` (municipio), `hayEmpate`.

Para SE la estructura es análoga (confirmar en la primera descarga: probablemente `senados[]` en vez de `camaras[]`, con `codpar` de listas al Senado).

## codpar confirmados (Cámara, Tunja) y homologación CA→SE
| Partido | codpar CA | codpar SE | Color |
|---|---|---|---|
| Alianza Verde | 5 | 57 | `#007C34` |
| Pacto Histórico | 87 | 92 | `#7B2D8B` |
| Centro Democrático | 10 | 10 | `#1E477D` |
| Conservador | 2 | 2 | `#E07B00` |

Otros codpar vistos en Tunja CA: 121, 122, 120, 15, 137 (nombres no vienen en el JSON).
**Los nombres de partido NO están en el JSON**: mantén un dict `codpar → nombre` para los conocidos; el join siempre es por `codpar`.

## PENDIENTE CRÍTICO: granularidad puesto/mesa
El endpoint `/CA/{municipio}.json` es **agregado a nivel municipio** (no trae mesas). Pero:
- Reto 3.1 pide ratio **por puesto y municipio**.
- Reto 3.2 pide **mesas** con dominancia > 60%.
- Reto 5.2 (scatter) pide un punto **por mesa**.

PRIMER TAREA antes del schema: **encontrar el endpoint de puesto/mesa**. En Chrome, sobre la página de Tunja, hacer drill-down (municipio → puesto → mesa) y capturar en F12 → Network la URL con código más largo (probablemente `{amb}` extendido con dígitos de zona/puesto/mesa; la mesa es un id de 19 dígitos). Si existe, el scraper debe bajar hasta ahí. Si NO existe públicamente, trabajar al grano más fino disponible y documentarlo en el README (se sacrifica parte de 3.2/5.2, pero se conserva lo demás).

## Modelo de datos (SQLite) — objetivo
Diseñar con columna de grano fino para que sirva a mesa o puesto según lo que se consiga:
- `municipios(amb PK, nombre)` — desde `mapagan`.
- `partidos(codpar PK, nombre, corporacion)` — nombre desde dict conocido; codpar es la clave.
- `candidatos(id PK, codcan, amb, codpar, nomcan, apecan, cedula, corporacion)`.
- `votos(id PK, corporacion, mesa_id/puesto NULLABLE, amb, codpar, codcan, votos, UNIQUE(corporacion, COALESCE(mesa_id,amb), codpar, codcan))`.
- `carga_log(id, timestamp, municipio, corporacion, filas_insertadas, filas_omitidas)`.
- 3+ índices (bonus +2): sobre `votos(amb)`, `votos(codpar)`, `votos(mesa_id)` con comentario de qué query optimizan.
- Idempotencia (evita −5): `INSERT OR IGNORE` sobre el `UNIQUE`.

## Reto 1 — Scraper
- CLI: `python scraper.py` (4 municipios × CA y SE por defecto), `--municipios TUNJA PAIPA`, `--preflight` (conteo esperado sin descargar; +3 bonus).
- retry/backoff, log de progreso, idempotente. Guardar 2-3 JSON reales en `sample_data/` como respaldo reproducible.
- README 1.1: patrón de URL, 8+ campos JSON (elec, amb, mdhm, codpar, vot, codcan, nomcan, mesesc...), nomenclator (`mapagan`), y que no requiere cabeceras.

## Reto 3 — SQL (fórmulas)
- **3.1** Ratio arrastre por puesto y municipio: `votos_SE_Verde / votos_CA_Verde` (Verde CA codpar=5, SE codpar=57).
- **3.2** Dominancia: mesas donde `(votos_candidato / votos_partido_en_mesa) > 0.60`. Construir desde cero.
- **3.3** Atribución determinística, top 5: `A = (votos_cand / votos_partido) * votos_SE_partido`.

## Reto 4 — Dashboard (index.html autocontenido, sin servidor)
Secciones: Comparativo (votos CA totales de los 4 municipios), Por Municipio (selector → top 10 candidatos CA + partido líder SE), Arrastre (selector → ratio Verde por puesto, línea de referencia en 1.0). Colores obligatorios (tabla arriba). Datos desde `data.json`. Bonus: dark mode (+3), Exportar CSV (+2). **Mapa Leaflet de Boyacá** (4 burbujas: Tunja 5.5353,-73.3577 · Paipa 5.7797,-73.1168 · Sogamoso 5.7143,-72.9339 · Duitama 5.8267,-73.0334; tamaño = votos CA, color = partido ganador) — agregarlo solo cuando las 3 secciones obligatorias funcionen.

## Reto 5 — Visualizaciones Python
- `heatmap_municipios.png`: top 8 candidatos CA × 4 municipios, % del total por municipio, anotado. (Funciona con datos municipio-level.)
- `scatter_ca_se.png`: punto = mesa, color por municipio, recta OLS, `r` de Pearson. `scatter.py` imprime `r=X.XXX | pendiente=X.XXX | n_mesas=NNN`. (Requiere grano mesa.)

## README — headings exactos
`# NIÑO — Prueba Técnica UTL Senado 2026` · `## Candidato` · `## Instalación` · `## Pipeline de ejecución` · `## API` · `## Municipios en la BD` · `## Hallazgos principales` · `## Bonus implementados`. Reproducible en < 10 min o −10.

## Reglas de trabajo
Una fase a la vez, verificando con ejecución real. No inventar campos: parsear el JSON real. Respetar nombres de archivo/estructura exactos. Idempotencia y 4 municipios innegociables. Comentarios en español. Commits por fase.
