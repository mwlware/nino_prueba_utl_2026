# NIÑO — Prueba Técnica UTL Senado 2026

Pipeline de datos electorales del **Congreso 2026** (preconteo del 8 de marzo de 2026)
para 4 municipios de Boyacá: Tunja, Duitama, Sogamoso y Paipa.
Análisis central: **arrastre Cámara → Senado** de Alianza Verde.

## Candidato

- **Nombre:** Brandon Esteven Niño Quiroga
- **Email:** brandonq718@gmail.com
- **Repo:** https://github.com/mwlware/nino_prueba_utl_2026

## Instalación

```bash
git clone https://github.com/mwlware/nino_prueba_utl_2026.git
cd nino_prueba_utl_2026
pip install -r requirements.txt
```

Requisitos: Python 3.10+ y conexión a internet (para descargar datos de la Registraduría).
Tiempo estimado de instalación + ejecución: **< 5 minutos**.

## Pipeline de ejecución

```bash
# 1. Scraper: descarga 4 municipios × 2 corporaciones (CA + SE) y carga a SQLite
python scraper/scraper.py

# 2. Verificar BD y generar manifest de evaluación
python outputs/generar_manifest.py

# 3. Exportar datos para dashboard
python dashboard/export_data.py

# 4. Generar visualizaciones
python viz/heatmap.py
python viz/scatter.py

# 5. Abrir dashboard en el navegador (datos embebidos, sin servidor)
#    Windows:
start dashboard/index.html
#    macOS:
open dashboard/index.html
#    Linux:
xdg-open dashboard/index.html
```

Comandos adicionales del scraper:

```bash
# Solo algunos municipios
python scraper/scraper.py --municipios TUNJA PAIPA

# Preflight: ver conteo esperado sin descargar (bonus)
python scraper/scraper.py --preflight
```

Re-ejecutar cualquier paso es seguro: el pipeline es **idempotente** (`INSERT OR IGNORE`).

## API

Endpoint JSON estático de la Registraduría (sin autenticación, sin cabeceras especiales):

```
https://resultadospreccongreso2026.registraduria.gov.co/json/ACT/{CORP}/{CODIGO}.json
```

| Parámetro   | Valores                                                                                                                                     |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `{CORP}`   | `CA` (Cámara) o `SE` (Senado)                                                                                                          |
| `{CODIGO}` | Código territorial interno (no DANE). Departamento:`0700`, municipio: 7 dígitos (ej. `0700001`), zona: 9 dígitos (ej. `070000101`) |

**Campos principales del JSON:**

| Campo                       | Descripción                                                                         |
| --------------------------- | ------------------------------------------------------------------------------------ |
| `elec`                    | Identificador de elección                                                           |
| `amb`                     | Código del ámbito consultado                                                       |
| `mdhm`                    | Fecha/hora del boletín (ej.`"03082211"` = 8 marzo 22:11)                          |
| `camaras[].cam`           | Tipo de cámara:`"1"` = territorial CA, `"0"` = nacional SE, `"4"` = indígena |
| `partotabla[].act.codpar` | Código del partido                                                                  |
| `partotabla[].act.vot`    | Votos totales del partido en el ámbito                                              |
| `cantotabla[].codcan`     | Código de candidato (`"0"` = solo por la lista)                                   |
| `cantotabla[].nomcan`     | Nombre del candidato                                                                 |
| `cantotabla[].apecan`     | Apellido del candidato                                                               |
| `cantotabla[].vot`        | Votos del candidato                                                                  |
| `cantotabla[].cedula`     | Cédula del candidato                                                                |
| `totales.act.mesesc`      | Mesas escrutadas                                                                     |
| `totales.act.votant`      | Total votantes                                                                       |
| `mapagan[]`               | Nomenclator: array con`amb`, `nombre`, `mesesc` de cada subdivisión           |

**Nomenclator:** el JSON del departamento (`0700`) trae en `mapagan` el listado completo
de 123 municipios de Boyacá con sus códigos `amb` y nombres. Se usa para poblar la tabla
`municipios` sin hardcodear.

**Granularidad:** el grano más fino disponible públicamente es **zona** (9 dígitos).
No existe endpoint de puesto ni de mesa individual.

## Municipios en la BD

| Municipio | Código`amb` | Zonas | Mesas | Votos CA | Votos SE |
| --------- | -------------- | ----- | ----- | -------- | -------- |
| Tunja     | 0700001        | 6     | 424   | 72,461   | 74,243   |
| Duitama   | 0700079        | 5     | 287   | 48,187   | 48,843   |
| Sogamoso  | 0700277        | 5     | 301   | 50,881   | 50,847   |
| Paipa     | 0700181        | 3     | 95    | 16,807   | 16,393   |

Total: **21,413 filas** en la tabla `votos`, **4,508 candidatos**, **25 partidos**.

## Hallazgos principales

### 1. Arrastre Verde (CA → SE) varía drásticamente entre municipios

El ratio `votos_SE_Verde / votos_CA_Verde` mide cuántos votos "arrastra" la lista de
Cámara hacia el Senado para Alianza Verde:

| Municipio | Votos CA Verde | Votos SE Verde | Ratio           | Interpretación             |
| --------- | -------------- | -------------- | --------------- | --------------------------- |
| Duitama   | 6,507          | 8,371          | **1.286** | SE obtiene 29% más que CA  |
| Tunja     | 15,836         | 16,296         | **1.029** | Arrastre neutro (+3%)       |
| Sogamoso  | 8,086          | 8,195          | **1.013** | Prácticamente igual        |
| Paipa     | 7,171          | 4,161          | **0.580** | SE pierde 42% respecto a CA |

**Paipa es la anomalía:** Verde pierde casi la mitad de sus votos al pasar de Cámara a
Senado, sugiriendo que el electorado de Cámara en Paipa vota por candidatos locales
de Verde pero no sigue la lista al Senado. En Duitama ocurre lo contrario: la marca
Verde en Senado arrastra más que los candidatos locales de Cámara.

### 2. El top de votos CA no coincide con el top de atribución SE

El candidato con más votos absolutos en Cámara es **Héctor David Chaparro** (Conservador,
13,861 votos en los 4 municipios), pero no aparece en el top 5 de atribución al Senado
porque el Partido Conservador obtiene pocos votos en SE comparado con su base de CA
(ratio bajo de arrastre). En cambio, **Ramiro Barragán Adame** (Verde, 4,294 votos solo en
Tunja) genera una atribución SE de 4,418.7 porque Verde tiene un ratio de arrastre >= 1.0
en Tunja: cada voto de Cámara "vale" más de un voto de Senado.

### 3. Dominancia de candidatos

45 zonas muestran dominancia >60% (un candidato concentra más del 60% de los votos de
su partido). Chaparro (Conservador) domina consistentemente en Duitama (74%) y Paipa
(82%). Las zonas pequeñas (98, 99 — cárceles, hospitales) muestran 100% por volúmenes
muy bajos.

### 4. Correlación CA-SE casi perfecta a nivel zona

El scatter de votos totales CA vs SE por zona muestra `r = 1.000` con pendiente 1.015:
la participación es prácticamente idéntica entre corporaciones en cada zona, con SE
recibiendo ~1.5% más votos en promedio.

## Bonus implementados

| Bonus                              | Puntos | Descripción                                                                             |
| ---------------------------------- | ------ | ---------------------------------------------------------------------------------------- |
| `--preflight`                    | +3     | Muestra conteo esperado de requests sin descargar                                        |
| 4 índices SQL con justificación  | +2     | `idx_votos_amb`, `idx_votos_codpar`, `idx_votos_zona`, `idx_votos_corp_amb`      |
| Explicación atribución 3.3       | +2     | Documentado en Hallazgos punto 2: por qué top CA ≠ top atribución SE                  |
| Dark mode (CSS custom properties)  | +3     | Toggle en dashboard con re-render de gráficos y tiles del mapa                          |
| Exportar CSV                       | +2     | 3 botones: comparativo, municipio, arrastre                                              |
| Mapa coroplético 123 municipios   | extra  | Mapa Leaflet de todo Boyacá con toggle CA/SE, búsqueda, panel de detalle y leyenda     |
| Scraper extendido a 123 municipios | +3     | `export_data.py` descarga y mapea los 123 municipios del departamento vía `mapagan` |
| Heatmap anotado                    | —     | Top 8 candidatos × 4 municipios, % por municipio                                        |
| Scatter OLS + Pearson              | —     | r, pendiente, n impreso en consola y anotado en gráfico                                 |
