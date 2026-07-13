"""
ETL: carga JSON de la Registraduría (Congreso 2026) a SQLite.
Idempotente: INSERT OR IGNORE sobre UNIQUE constraints.
"""

import sqlite3
import json
import os
from datetime import datetime

# Ruta por defecto de la BD y schema
DB_PATH = os.path.join(os.path.dirname(__file__), "puestos_2026.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# Dict de partidos conocidos: codpar → (nombre, color)
# codpar varía entre CA y SE para el mismo partido
PARTIDOS_CONOCIDOS = {
    # Cámara
    ("5", "CA"):   ("Alianza Verde",      "#007C34"),
    ("87", "CA"):  ("Pacto Histórico",    "#7B2D8B"),
    ("10", "CA"):  ("Centro Democrático", "#1E477D"),
    ("2", "CA"):   ("Conservador",        "#E07B00"),
    # Senado
    ("57", "SE"):  ("Alianza Verde",      "#007C34"),
    ("92", "SE"):  ("Pacto Histórico",    "#7B2D8B"),
    ("10", "SE"):  ("Centro Democrático", "#1E477D"),
    ("2", "SE"):   ("Conservador",        "#E07B00"),
}

# cam principal por corporación
CAM_PRINCIPAL = {"CA": "1", "SE": "0"}


def init_db(db_path=DB_PATH):
    """Crea la BD y ejecuta el schema si no existe."""
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        con.executescript(f.read())
    return con


def normalizar_nombre(texto):
    """Normaliza nombres: título, sin espacios extra."""
    if not texto:
        return texto
    return " ".join(texto.strip().split()).title()


def cargar_municipios_desde_mapagan(con, mapagan):
    """Inserta municipios desde el array mapagan (nivel departamento)."""
    for item in mapagan:
        con.execute(
            "INSERT OR IGNORE INTO municipios (amb, nombre) VALUES (?, ?)",
            (item["amb"], item["nombre"].strip()),
        )
    con.commit()


def cargar_json(con, data, corporacion, nivel="zona"):
    """
    Carga un JSON de la Registraduría a la BD.
    - data: dict parseado del JSON
    - corporacion: 'CA' o 'SE'
    - nivel: 'zona' si el JSON es de una zona, 'municipio' si es agregado
    """
    amb_json = data["amb"]
    # Determinar amb del municipio (7 dígitos) y zona (9 dígitos si aplica)
    amb_municipio = amb_json[:7]
    # Si es zona (9 dígitos) se usa como está; si no, zona = amb (fallback)
    zona = amb_json if (nivel == "zona" and len(amb_json) == 9) else amb_municipio

    cam_objetivo = CAM_PRINCIPAL[corporacion]
    insertadas = 0
    omitidas = 0

    # Buscar la cámara principal dentro de camaras[]
    camara = None
    for c in data.get("camaras", []):
        if c.get("cam") == cam_objetivo:
            camara = c
            break

    if camara is None:
        print(f"  WARN: No se encontró cam={cam_objetivo} en {amb_json} ({corporacion})")
        return insertadas, omitidas

    # Recorrer partidos
    for partido in camara.get("partotabla", []):
        act = partido.get("act", {})
        codpar = act.get("codpar", "")

        # Insertar partido si no existe
        nombre_partido, color = PARTIDOS_CONOCIDOS.get(
            (codpar, corporacion), (None, None)
        )
        con.execute(
            "INSERT OR IGNORE INTO partidos (codpar, corporacion, nombre, color) VALUES (?, ?, ?, ?)",
            (codpar, corporacion, nombre_partido, color),
        )

        # Recorrer candidatos del partido
        for cand in act.get("cantotabla", []):
            codcan = cand.get("codcan", "0")
            votos_val = int(cand.get("vot", 0))
            nomcan = normalizar_nombre(cand.get("nomcan", ""))
            apecan = normalizar_nombre(cand.get("apecan", ""))
            cedula = cand.get("cedula", "")

            # Insertar candidato
            con.execute(
                "INSERT OR IGNORE INTO candidatos (codcan, amb, codpar, corporacion, nomcan, apecan, cedula) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (codcan, amb_municipio, codpar, corporacion, nomcan, apecan, cedula),
            )

            # Insertar votos
            cursor = con.execute(
                "INSERT OR IGNORE INTO votos (corporacion, amb, zona, codpar, codcan, votos) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (corporacion, amb_municipio, zona, codpar, codcan, votos_val),
            )
            if cursor.rowcount > 0:
                insertadas += 1
            else:
                omitidas += 1

    con.commit()

    # Registrar en carga_log
    con.execute(
        "INSERT INTO carga_log (timestamp, municipio, corporacion, nivel, filas_insertadas, filas_omitidas) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), amb_municipio, corporacion, nivel, insertadas, omitidas),
    )
    con.commit()

    return insertadas, omitidas


def cargar_json_file(con, filepath, corporacion, nivel="zona"):
    """Wrapper que lee un archivo JSON y llama a cargar_json."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return cargar_json(con, data, corporacion, nivel)


# --- Punto de entrada para pruebas ---
if __name__ == "__main__":
    import requests

    print("=== ETL: carga de prueba Tunja CA + SE ===\n")

    con = init_db()

    # Cargar nomenclator desde departamento
    print("Cargando nomenclator de municipios desde departamento...")
    dept = requests.get(
        "https://resultadospreccongreso2026.registraduria.gov.co/json/ACT/CA/0700.json",
        timeout=30,
    ).json()
    # mapagan está dentro de camaras[0]
    for cam in dept.get("camaras", []):
        mg = cam.get("mapagan", [])
        if mg:
            cargar_municipios_desde_mapagan(con, mg)
            print(f"  {len(mg)} municipios cargados desde cam={cam['cam']}")
            break

    # Zonas de Tunja
    ZONAS_TUNJA = ["01", "02", "03", "90", "98", "99"]
    AMB_TUNJA = "0700001"

    for corp in ["CA", "SE"]:
        print(f"\n--- {corp} Tunja ---")
        for z in ZONAS_TUNJA:
            url = f"https://resultadospreccongreso2026.registraduria.gov.co/json/ACT/{corp}/{AMB_TUNJA}{z}.json"
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                print(f"  Zona {z}: HTTP {r.status_code}, saltando")
                continue
            data = r.json()
            ins, omi = cargar_json(con, data, corp, nivel="zona")
            print(f"  Zona {z}: {ins} insertadas, {omi} omitidas")

    # Resumen
    print("\n=== Filas por tabla ===")
    for tabla in ["municipios", "partidos", "candidatos", "votos", "carga_log"]:
        count = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        print(f"  {tabla}: {count}")

    con.close()
