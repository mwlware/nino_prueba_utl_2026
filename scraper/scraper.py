"""
Scraper: descarga resultados del Congreso 2026 desde la API de la Registraduría
y los carga a SQLite vía db/etl.py.

Uso:
  python scraper/scraper.py                     # 4 municipios, CA y SE
  python scraper/scraper.py --municipios TUNJA PAIPA
  python scraper/scraper.py --preflight         # conteo esperado sin descargar
"""

import argparse
import json
import os
import sys
import time
import requests

# Agregar raíz del proyecto al path para importar db.etl
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.etl import init_db, cargar_json, cargar_municipios_desde_mapagan

# === Configuración ===

BASE_URL = "https://resultadospreccongreso2026.registraduria.gov.co/json/ACT"
SAMPLE_DIR = os.path.join(PROJECT_ROOT, "sample_data")

# Municipios objetivo con sus zonas descubiertas en Fase 0
MUNICIPIOS = {
    "TUNJA":    {"amb": "0700001", "zonas": ["01", "02", "03", "90", "98", "99"]},
    "DUITAMA":  {"amb": "0700079", "zonas": ["01", "02", "90", "98", "99"]},
    "SOGAMOSO": {"amb": "0700277", "zonas": ["01", "02", "90", "98", "99"]},
    "PAIPA":    {"amb": "0700181", "zonas": ["01", "02", "99"]},
}

CORPORACIONES = ["CA", "SE"]

# Retry con backoff exponencial
MAX_RETRIES = 3
BACKOFF_BASE = 2  # segundos


def descargar_json(url, retries=MAX_RETRIES):
    """Descarga un JSON con retry y backoff exponencial."""
    for intento in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if intento == retries:
                print(f"  ERROR: {url} falló tras {retries} intentos: {e}")
                return None
            espera = BACKOFF_BASE ** intento
            print(f"  Reintento {intento}/{retries} en {espera}s: {e}")
            time.sleep(espera)
    return None


def guardar_sample(data, corp, amb_code):
    """Guarda JSON en sample_data/ como respaldo reproducible."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    filepath = os.path.join(SAMPLE_DIR, f"{corp}_{amb_code}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def preflight(municipios_sel):
    """Muestra conteo esperado de descargas sin ejecutar (bonus +3)."""
    print("=== PREFLIGHT: conteo esperado (sin descargar) ===\n")
    total_zonas = 0
    total_requests = 0
    for nombre in municipios_sel:
        info = MUNICIPIOS[nombre]
        n_zonas = len(info["zonas"])
        n_reqs = n_zonas * len(CORPORACIONES)
        total_zonas += n_zonas
        total_requests += n_reqs
        print(f"  {nombre} ({info['amb']}): {n_zonas} zonas × {len(CORPORACIONES)} corp = {n_reqs} requests")

    print(f"\n  Total: {len(municipios_sel)} municipios, {total_zonas} zonas, {total_requests} requests HTTP")
    print("  Corporaciones: CA (cam=1), SE (cam=0)")
    print("  Destino: db/puestos_2026.db")
    print("\n  (Ejecutar sin --preflight para descargar)")


def cargar_nomenclator(con):
    """Carga la tabla municipios desde mapagan del departamento."""
    print("Cargando nomenclator de municipios desde departamento (0700)...")
    data = descargar_json(f"{BASE_URL}/CA/0700.json")
    if data is None:
        print("  ERROR: no se pudo descargar el departamento. Abortando.")
        sys.exit(1)
    for cam in data.get("camaras", []):
        mg = cam.get("mapagan", [])
        if mg:
            cargar_municipios_desde_mapagan(con, mg)
            print(f"  {len(mg)} municipios insertados desde mapagan")
            return
    print("  WARN: no se encontró mapagan en el departamento")


def scrape(municipios_sel):
    """Descarga y carga los municipios seleccionados."""
    # Borrar BD anterior solo si se pide explícitamente; por defecto es idempotente
    con = init_db()

    # Nomenclator
    cargar_nomenclator(con)

    total_ins = 0
    total_omi = 0
    samples_guardados = 0

    for nombre in municipios_sel:
        info = MUNICIPIOS[nombre]
        amb = info["amb"]
        print(f"\n=== {nombre} ({amb}) ===")

        for corp in CORPORACIONES:
            print(f"  --- {corp} ---")
            for z in info["zonas"]:
                codigo = f"{amb}{z}"
                url = f"{BASE_URL}/{corp}/{codigo}.json"
                data = descargar_json(url)
                if data is None:
                    continue

                # Guardar sample (solo 2-3 por municipio, las primeras zonas)
                if samples_guardados < 3 or z in ("01",):
                    guardar_sample(data, corp, codigo)
                    samples_guardados += 1

                ins, omi = cargar_json(con, data, corp, nivel="zona")
                print(f"    Zona {z}: {ins} insertadas, {omi} omitidas")
                total_ins += ins
                total_omi += omi

    # Resumen final
    print(f"\n{'='*50}")
    print(f"Total: {total_ins} filas insertadas, {total_omi} omitidas")
    print(f"\n=== Filas por tabla ===")
    for tabla in ["municipios", "partidos", "candidatos", "votos", "carga_log"]:
        count = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        print(f"  {tabla}: {count}")

    # Conteo por municipio
    print(f"\n=== Votos por municipio ===")
    rows = con.execute("""
        SELECT m.nombre, v.corporacion, COUNT(*) as filas, SUM(v.votos) as total_votos
        FROM votos v JOIN municipios m ON v.amb = m.amb
        WHERE v.amb IN ('0700001','0700079','0700277','0700181')
        GROUP BY v.amb, v.corporacion
        ORDER BY m.nombre, v.corporacion
    """).fetchall()
    for nombre_m, corp, filas, total in rows:
        print(f"  {nombre_m:20s} {corp}: {filas:>5} filas, {total:>7} votos")

    con.close()


def main():
    parser = argparse.ArgumentParser(
        description="Scraper Congreso Boyacá 2026 — Registraduría"
    )
    parser.add_argument(
        "--municipios", nargs="+", default=None,
        help="Municipios a descargar (TUNJA, DUITAMA, SOGAMOSO, PAIPA). Por defecto: los 4.",
        choices=list(MUNICIPIOS.keys()),
    )
    parser.add_argument(
        "--preflight", action="store_true",
        help="Muestra conteo esperado sin descargar (bonus +3).",
    )
    args = parser.parse_args()

    municipios_sel = args.municipios or list(MUNICIPIOS.keys())

    if args.preflight:
        preflight(municipios_sel)
    else:
        scrape(municipios_sel)


if __name__ == "__main__":
    main()
