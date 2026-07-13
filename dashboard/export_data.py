"""
Exporta datos desde puestos_2026.db a dashboard/data.json para el dashboard.
"""

import json
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "db", "puestos_2026.db")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "dashboard", "data.json")

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

    con.close()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"data.json generado: {OUTPUT_PATH}")
    print(f"  Comparativo: {len(data['comparativo'])} municipios")
    print(f"  Por municipio: {len(data['por_municipio'])} entradas")
    print(f"  Arrastre: {len(data['arrastre'])} zonas")


if __name__ == "__main__":
    export()
