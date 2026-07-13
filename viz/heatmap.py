"""
Heatmap: top 8 candidatos CA × 4 municipios.
Valor = % del total de votos CA por municipio, con anotaciones.
"""

import os
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "db", "puestos_2026.db")
OUTPUT = os.path.join(PROJECT_ROOT, "viz", "heatmap_municipios.png")

AMBS = ["0700001", "0700079", "0700277", "0700181"]


def main():
    con = sqlite3.connect(DB_PATH)

    # Total votos CA por municipio (para calcular %)
    totales = {}
    for amb in AMBS:
        row = con.execute(
            "SELECT SUM(votos) FROM votos WHERE corporacion='CA' AND amb=?", (amb,)
        ).fetchone()
        totales[amb] = row[0]

    # Top 8 candidatos CA globales (sumando los 4 municipios)
    top8 = con.execute("""
        SELECT c.nomcan || ' ' || c.apecan AS candidato, c.codcan, c.codpar,
               SUM(v.votos) AS total
        FROM votos v
        JOIN candidatos c ON v.codcan=c.codcan AND v.amb=c.amb
             AND v.codpar=c.codpar AND v.corporacion=c.corporacion
        WHERE v.corporacion='CA' AND v.codcan!='0'
          AND v.amb IN ('0700001','0700079','0700277','0700181')
        GROUP BY c.codcan, c.codpar
        ORDER BY total DESC LIMIT 8
    """).fetchall()

    nombres_cand = [r[0] for r in top8]
    claves_cand = [(r[1], r[2]) for r in top8]  # (codcan, codpar)

    # Nombres de municipio
    nombres_muni = []
    for amb in AMBS:
        n = con.execute("SELECT nombre FROM municipios WHERE amb=?", (amb,)).fetchone()[0]
        nombres_muni.append(n)

    # Construir matriz de porcentajes
    matriz = np.zeros((len(claves_cand), len(AMBS)))
    for i, (codcan, codpar) in enumerate(claves_cand):
        for j, amb in enumerate(AMBS):
            row = con.execute(
                "SELECT SUM(votos) FROM votos WHERE corporacion='CA' AND amb=? AND codcan=? AND codpar=?",
                (amb, codcan, codpar),
            ).fetchone()
            votos = row[0] or 0
            matriz[i, j] = round(votos / totales[amb] * 100, 2) if totales[amb] else 0

    con.close()

    # Graficar
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.heatmap(
        matriz,
        annot=True,
        fmt=".2f",
        cmap="YlOrRd",
        xticklabels=nombres_muni,
        yticklabels=nombres_cand,
        linewidths=0.5,
        cbar_kws={"label": "% del total CA del municipio"},
        ax=ax,
    )
    ax.set_title("Top 8 candidatos CA — % de votos por municipio", fontsize=13, pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    plt.savefig(OUTPUT, dpi=150)
    plt.close()
    print(f"Heatmap guardado: {OUTPUT}")


if __name__ == "__main__":
    main()
