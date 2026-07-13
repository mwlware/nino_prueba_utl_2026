"""
Exporta datos desde puestos_2026.db a dashboard/data.json para el dashboard.
Incluye mapagan (123 municipios, partido ganador) para el mapa coroplético.
"""

import json
import os
import sqlite3
import sys
import unicodedata
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "db", "puestos_2026.db")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "dashboard", "data.json")
GEOJSON_PATH = os.path.join(PROJECT_ROOT, "maps", "boyaca_simple.geojson")

BASE_URL = "https://resultadospreccongreso2026.registraduria.gov.co/json/ACT"

# Colores por codpar (CA y SE)
COLORES_CODPAR = {
    "5": "#007C34", "57": "#007C34",    # Alianza Verde
    "87": "#7B2D8B", "92": "#7B2D8B",   # Pacto Histórico
    "10": "#1E477D",                     # Centro Democrático
    "2": "#E07B00",                      # Conservador
}
NOMBRES_CODPAR = {
    "5": "Alianza Verde", "57": "Alianza Verde",
    "87": "Pacto Histórico", "92": "Pacto Histórico",
    "10": "Centro Democrático",
    "2": "Conservador",
}

# Alias para join GeoJSON ↔ mapagan por nombre normalizado
ALIAS_NOMBRE = {
    "AQUITANIA (PUEBLOVIEJO)": "AQUITANIA",
    "GUICAN": "GÜICÁN DE LA SIERRA",
    "VILLA DE LEIVA": "VILLA DE LEYVA",
}

def normalizar(s):
    """Mayúsculas sin tildes para join por nombre."""
    s = s.upper().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

AMBS = ["0700001", "0700079", "0700277", "0700181"]
AMB_FILTER = ",".join(f"'{a}'" for a in AMBS)


def export():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    data = {}

    # 1. Comparativo: votos CA totales por municipio
    rows = con.execute(f"""
        SELECT m.nombre, m.amb, SUM(v.votos) as total
        FROM votos v JOIN municipios m ON v.amb = m.amb
        WHERE v.corporacion = 'CA' AND v.amb IN ({AMB_FILTER})
        GROUP BY v.amb ORDER BY total DESC
    """).fetchall()
    data["comparativo"] = [{"municipio": r["nombre"], "amb": r["amb"], "votos_ca": r["total"]} for r in rows]

    # 2. Por Municipio: top 10 candidatos CA + partido lider SE
    data["por_municipio"] = {}
    for amb in AMBS:
        nombre = con.execute("SELECT nombre FROM municipios WHERE amb = ?", (amb,)).fetchone()["nombre"]

        # Top 10 candidatos CA
        candidatos = con.execute("""
            SELECT c.nomcan || ' ' || c.apecan AS candidato,
                   COALESCE(p.nombre, 'Partido ' || v.codpar) AS partido,
                   COALESCE(p.color, '#888888') AS color,
                   SUM(v.votos) AS total
            FROM votos v
            JOIN candidatos c ON v.codcan=c.codcan AND v.amb=c.amb AND v.codpar=c.codpar AND v.corporacion=c.corporacion
            LEFT JOIN partidos p ON v.codpar=p.codpar AND v.corporacion=p.corporacion
            WHERE v.corporacion='CA' AND v.amb=? AND v.codcan!='0'
            GROUP BY c.codcan, c.codpar ORDER BY total DESC LIMIT 10
        """, (amb,)).fetchall()

        # Partido lider SE (top 1)
        lider_se = con.execute("""
            SELECT COALESCE(p.nombre, 'Partido ' || v.codpar) AS partido,
                   COALESCE(p.color, '#888888') AS color,
                   SUM(v.votos) AS total
            FROM votos v
            LEFT JOIN partidos p ON v.codpar=p.codpar AND v.corporacion=p.corporacion
            WHERE v.corporacion='SE' AND v.amb=?
            GROUP BY v.codpar ORDER BY total DESC LIMIT 1
        """, (amb,)).fetchone()

        # Top 5 partidos SE para mostrar contexto
        partidos_se = con.execute("""
            SELECT COALESCE(p.nombre, 'Partido ' || v.codpar) AS partido,
                   COALESCE(p.color, '#888888') AS color,
                   SUM(v.votos) AS total
            FROM votos v
            LEFT JOIN partidos p ON v.codpar=p.codpar AND v.corporacion=p.corporacion
            WHERE v.corporacion='SE' AND v.amb=?
            GROUP BY v.codpar ORDER BY total DESC LIMIT 5
        """, (amb,)).fetchall()

        data["por_municipio"][nombre] = {
            "amb": amb,
            "top10_ca": [{"candidato": r["candidato"], "partido": r["partido"],
                          "color": r["color"], "votos": r["total"]} for r in candidatos],
            "lider_se": {"partido": lider_se["partido"], "color": lider_se["color"],
                         "votos": lider_se["total"]},
            "top5_partidos_se": [{"partido": r["partido"], "color": r["color"],
                                  "votos": r["total"]} for r in partidos_se],
        }

    # 3. Arrastre Verde por zona
    rows = con.execute(f"""
        SELECT m.nombre AS municipio, ca.zona,
               ca.votos_ca, se.votos_se,
               ROUND(CAST(se.votos_se AS REAL) / ca.votos_ca, 3) AS ratio
        FROM (SELECT amb, zona, SUM(votos) AS votos_ca FROM votos
              WHERE corporacion='CA' AND codpar='5' GROUP BY amb, zona) ca
        JOIN (SELECT amb, zona, SUM(votos) AS votos_se FROM votos
              WHERE corporacion='SE' AND codpar='57' GROUP BY amb, zona) se
            ON ca.zona=se.zona AND ca.amb=se.amb
        JOIN municipios m ON ca.amb=m.amb
        WHERE ca.votos_ca > 0
        ORDER BY m.nombre, ca.zona
    """).fetchall()
    data["arrastre"] = [{"municipio": r["municipio"], "zona": r["zona"],
                         "votos_ca": r["votos_ca"], "votos_se": r["votos_se"],
                         "ratio": r["ratio"]} for r in rows]

    # Colores de partidos conocidos (para referencia del dashboard)
    data["colores_partidos"] = {
        "Alianza Verde": "#007C34",
        "Pacto Histórico": "#7B2D8B",
        "Centro Democrático": "#1E477D",
        "Conservador": "#E07B00",
    }

    # 4. Mapagan: partido ganador por municipio (123 municipios, CA y SE)
    data["mapagan"] = {}
    for corp in ["CA", "SE"]:
        cam_target = "1" if corp == "CA" else "0"
        dept = requests.get(f"{BASE_URL}/{corp}/0700.json", timeout=30).json()
        for cam in dept["camaras"]:
            if cam["cam"] == cam_target:
                entries = []
                for m in cam["mapagan"]:
                    codpar = m["codpar"]
                    entries.append({
                        "amb": m["amb"],
                        "nombre": m["nombre"].strip(),
                        "codpar": codpar,
                        "partido": NOMBRES_CODPAR.get(codpar, f"Partido {codpar}"),
                        "color": COLORES_CODPAR.get(codpar, "#AAAAAA"),
                        "vot": int(m["vot"]),
                        "votant": int(m["votant"]),
                        "mesesc": int(m["mesesc"]),
                        "pmesesc": m["pmesesc"],
                    })
                data["mapagan"][corp] = entries
                break

    # 5. GeoJSON simplificado de Boyacá (para mapa coroplético)
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)

    # Crear índice por nombre normalizado para el join
    geo_by_name = {}
    for feat in geojson["features"]:
        name = feat["properties"]["name"]
        geo_by_name[normalizar(name)] = name

    # Verificar cobertura del join
    mapagan_ca = data["mapagan"]["CA"]
    matched = 0
    unmatched = []
    for m in mapagan_ca:
        nombre_map = m["nombre"]
        # Aplicar alias
        nombre_buscar = ALIAS_NOMBRE.get(nombre_map, nombre_map)
        norm = normalizar(nombre_buscar)
        if norm in geo_by_name:
            matched += 1
        else:
            unmatched.append(nombre_map)

    print(f"  Join GeoJSON: {matched}/123 municipios casados")
    if unmatched:
        print(f"  Sin casar: {unmatched}")

    data["geojson"] = geojson
    data["alias_nombre"] = ALIAS_NOMBRE

    con.close()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"data.json generado: {OUTPUT_PATH}")
    print(f"  Comparativo: {len(data['comparativo'])} municipios")
    print(f"  Por municipio: {len(data['por_municipio'])} entradas")
    print(f"  Arrastre: {len(data['arrastre'])} zonas")
    print(f"  Mapagan CA: {len(data['mapagan']['CA'])} municipios")
    print(f"  Mapagan SE: {len(data['mapagan']['SE'])} municipios")


if __name__ == "__main__":
    export()
