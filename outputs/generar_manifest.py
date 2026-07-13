"""
Genera outputs/evaluation_manifest.json verificando BD y queries SQL.
Valida que los 4 municipios estén cargados y que las 3 queries ejecuten sin error.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime

# === META (editar con datos reales del candidato) ===
META = {
    "nombre": "Brandon Niño",
    "email": "brandon@example.com",
    "repo": "https://github.com/usuario/PruebaTecnica",
    "fecha_generacion": None,  # se llena automáticamente
}

# Rutas
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "db", "puestos_2026.db")
SQL_DIR = os.path.join(PROJECT_ROOT, "sql")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "outputs", "evaluation_manifest.json")

# Municipios esperados
MUNICIPIOS_ESPERADOS = {
    "0700001": "TUNJA",
    "0700079": "DUITAMA",
    "0700277": "SOGAMOSO",
    "0700181": "PAIPA",
}

QUERIES = [
    ("tarea_3_1.sql", "Ratio arrastre Verde CA->SE por zona y municipio"),
    ("tarea_3_2.sql", "Dominancia >60% candidato vs partido en zona"),
    ("tarea_3_3.sql", "Top 5 candidatos por atribucion SE"),
]


def verificar_municipios(con):
    """Verifica que los 4 municipios tengan votos cargados."""
    resultados = {}
    for amb, nombre in MUNICIPIOS_ESPERADOS.items():
        row = con.execute(
            "SELECT COUNT(*), SUM(votos) FROM votos WHERE amb = ?", (amb,)
        ).fetchone()
        filas, total_votos = row[0], row[1] or 0

        # Contar zonas distintas
        zonas = con.execute(
            "SELECT COUNT(DISTINCT zona) FROM votos WHERE amb = ?", (amb,)
        ).fetchone()[0]

        # Mesas (desde totales del municipio no están en BD, pero zonas sí)
        resultados[nombre] = {
            "amb": amb,
            "filas_votos": filas,
            "total_votos": total_votos,
            "zonas": zonas,
            "cargado": filas > 0,
        }
    return resultados


def verificar_queries(con):
    """Ejecuta las 3 queries SQL y reporta resultado."""
    resultados = []
    for archivo, descripcion in QUERIES:
        filepath = os.path.join(SQL_DIR, archivo)
        entry = {"archivo": archivo, "descripcion": descripcion}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                sql = f.read()
            rows = con.execute(sql).fetchall()
            entry["status"] = "OK"
            entry["filas_resultado"] = len(rows)
            if rows:
                entry["muestra_primera_fila"] = [str(v) for v in rows[0]]
        except FileNotFoundError:
            entry["status"] = "ERROR"
            entry["error"] = f"Archivo no encontrado: {filepath}"
        except sqlite3.Error as e:
            entry["status"] = "ERROR"
            entry["error"] = str(e)
        resultados.append(entry)
    return resultados


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: BD no encontrada en {DB_PATH}")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")

    # --- Verificar municipios ---
    print("=== Verificacion de municipios ===")
    municipios = verificar_municipios(con)
    cargados = sum(1 for m in municipios.values() if m["cargado"])
    total_esperados = len(MUNICIPIOS_ESPERADOS)

    for nombre, info in municipios.items():
        estado = "OK" if info["cargado"] else "FALTA"
        print(f"  {nombre:20s} [{estado}] {info['filas_votos']:>6} filas, "
              f"{info['total_votos']:>7} votos, {info['zonas']} zonas")

    print(f"\n  >>> {cargados}/{total_esperados} municipios cargados <<<")

    # --- Verificar queries SQL ---
    print("\n=== Verificacion de queries SQL ===")
    queries = verificar_queries(con)
    for q in queries:
        if q["status"] == "OK":
            print(f"  {q['archivo']:20s} SQL OK  ({q['filas_resultado']} filas)")
        else:
            print(f"  {q['archivo']:20s} ERROR: {q['error']}")

    # --- Conteo general de tablas ---
    print("\n=== Filas por tabla ===")
    tablas_info = {}
    for tabla in ["municipios", "partidos", "candidatos", "votos", "carga_log"]:
        count = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        tablas_info[tabla] = count
        print(f"  {tabla}: {count}")

    con.close()

    # --- Generar manifest ---
    META["fecha_generacion"] = datetime.now().isoformat()

    manifest = {
        "meta": META,
        "verificacion": {
            "municipios_cargados": f"{cargados}/{total_esperados}",
            "municipios": municipios,
            "tablas": tablas_info,
            "queries_sql": queries,
        },
        "archivos": {
            "schema": "db/schema.sql",
            "etl": "db/etl.py",
            "base_datos": "db/puestos_2026.db",
            "scraper": "scraper/scraper.py",
            "sql": [f"sql/{q[0]}" for q in QUERIES],
            "sample_data": "sample_data/",
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n=== Manifest generado: {OUTPUT_PATH} ===")


if __name__ == "__main__":
    main()
