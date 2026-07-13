-- Schema: Resultados Congreso Boyacá 2026
-- Grano más fino disponible en la API: zona (9 dígitos)

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Nomenclator de municipios (poblado desde mapagan del departamento)
CREATE TABLE IF NOT EXISTS municipios (
    amb     TEXT PRIMARY KEY,   -- código Registraduría 7 dígitos, ej. '0700001'
    nombre  TEXT NOT NULL       -- nombre del municipio, ej. 'TUNJA'
);

-- Partidos políticos (codpar varía entre CA y SE para un mismo partido)
CREATE TABLE IF NOT EXISTS partidos (
    codpar      TEXT NOT NULL,
    corporacion TEXT NOT NULL CHECK (corporacion IN ('CA', 'SE')),
    nombre      TEXT,           -- NULL si no está en el dict conocido
    color       TEXT,           -- hex para dashboard, ej. '#007C34'
    PRIMARY KEY (codpar, corporacion)
);

-- Candidatos por corporación y ámbito
CREATE TABLE IF NOT EXISTS candidatos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codcan      TEXT NOT NULL,       -- '0' = SOLO POR LA LISTA
    amb         TEXT NOT NULL,       -- municipio 7 dígitos
    codpar      TEXT NOT NULL,
    corporacion TEXT NOT NULL CHECK (corporacion IN ('CA', 'SE')),
    nomcan      TEXT,
    apecan      TEXT,
    cedula      TEXT,
    FOREIGN KEY (codpar, corporacion) REFERENCES partidos(codpar, corporacion),
    FOREIGN KEY (amb) REFERENCES municipios(amb),
    UNIQUE(corporacion, amb, codpar, codcan)
);

-- Votos: grano = zona (9 dígitos). Si solo hubiera nivel municipio, zona queda igual a amb.
CREATE TABLE IF NOT EXISTS votos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    corporacion TEXT NOT NULL CHECK (corporacion IN ('CA', 'SE')),
    amb         TEXT NOT NULL,       -- municipio 7 dígitos
    zona        TEXT NOT NULL,       -- zona 9 dígitos; si nivel municipio, se usa amb
    codpar      TEXT NOT NULL,
    codcan      TEXT NOT NULL,       -- '0' para voto de lista
    votos       INTEGER NOT NULL,
    FOREIGN KEY (codpar, corporacion) REFERENCES partidos(codpar, corporacion),
    FOREIGN KEY (amb) REFERENCES municipios(amb),
    UNIQUE(corporacion, zona, codpar, codcan)
);

-- Log de carga para trazabilidad e idempotencia
CREATE TABLE IF NOT EXISTS carga_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL,
    municipio         TEXT NOT NULL,
    corporacion       TEXT NOT NULL,
    nivel             TEXT NOT NULL,  -- 'zona' o 'municipio'
    filas_insertadas  INTEGER NOT NULL DEFAULT 0,
    filas_omitidas    INTEGER NOT NULL DEFAULT 0
);

-- === Índices (bonus: 3+ con justificación) ===

-- Optimiza: consultas de arrastre que filtran votos por municipio (reto 3.1)
CREATE INDEX IF NOT EXISTS idx_votos_amb ON votos(amb);

-- Optimiza: joins cruzados CA↔SE por partido para calcular ratio de arrastre (reto 3.1)
CREATE INDEX IF NOT EXISTS idx_votos_codpar ON votos(codpar);

-- Optimiza: agrupación y filtrado por zona para dominancia >60% (reto 3.2)
CREATE INDEX IF NOT EXISTS idx_votos_zona ON votos(zona);

-- Optimiza: consultas que cruzan corporación+municipio (comparativo CA vs SE, reto 4)
CREATE INDEX IF NOT EXISTS idx_votos_corp_amb ON votos(corporacion, amb);
