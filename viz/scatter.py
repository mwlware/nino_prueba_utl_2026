"""
Scatter: votos CA vs SE por zona, color por municipio, recta OLS, r de Pearson.
NOTA: el grano más fino disponible en la API es ZONA (no mesa).
      Cada punto representa una zona. Se documenta esta limitación.
Imprime: r=X.XXX | pendiente=X.XXX | n_mesas=NNN
(n_mesas se reporta como n_zonas dado el grano disponible)
"""

import os
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "db", "puestos_2026.db")
OUTPUT = os.path.join(PROJECT_ROOT, "viz", "scatter_ca_se.png")

MUNICIPIOS = {
    "0700001": ("TUNJA", "#1E477D"),
    "0700079": ("DUITAMA", "#007C34"),
    "0700277": ("SOGAMOSO", "#E07B00"),
    "0700181": ("PAIPA", "#7B2D8B"),
}


def main():
    con = sqlite3.connect(DB_PATH)

    # Votos totales por zona, por corporación
    rows = con.execute("""
        SELECT ca.amb, ca.zona, ca.votos_ca, se.votos_se
        FROM (
            SELECT amb, zona, SUM(votos) AS votos_ca
            FROM votos WHERE corporacion='CA'
            GROUP BY amb, zona
        ) ca
        JOIN (
            SELECT amb, zona, SUM(votos) AS votos_se
            FROM votos WHERE corporacion='SE'
            GROUP BY amb, zona
        ) se ON ca.zona = se.zona AND ca.amb = se.amb
        WHERE ca.amb IN ('0700001','0700079','0700277','0700181')
        ORDER BY ca.amb, ca.zona
    """).fetchall()

    con.close()

    # Separar por municipio
    data_by_muni = {}
    all_ca, all_se = [], []
    for amb, zona, vca, vse in rows:
        data_by_muni.setdefault(amb, ([], []))
        data_by_muni[amb][0].append(vca)
        data_by_muni[amb][1].append(vse)
        all_ca.append(vca)
        all_se.append(vse)

    all_ca = np.array(all_ca)
    all_se = np.array(all_se)

    # OLS y Pearson
    slope, intercept, r_value, p_value, std_err = stats.linregress(all_ca, all_se)
    n_zonas = len(all_ca)

    # Imprimir en formato requerido
    print(f"r={r_value:.3f} | pendiente={slope:.3f} | n_mesas={n_zonas}")

    # Graficar
    fig, ax = plt.subplots(figsize=(8, 6))

    for amb, (nombre, color) in MUNICIPIOS.items():
        if amb in data_by_muni:
            ca_arr, se_arr = data_by_muni[amb]
            ax.scatter(ca_arr, se_arr, c=color, label=nombre, s=60, alpha=0.8, edgecolors="white", linewidth=0.5, zorder=3)

    # Recta OLS
    x_line = np.linspace(all_ca.min(), all_ca.max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, color="red", linewidth=1.5, linestyle="--", label=f"OLS (r={r_value:.3f})", zorder=2)

    # Anotación r de Pearson
    ax.annotate(
        f"r = {r_value:.3f}\npendiente = {slope:.3f}\nn = {n_zonas} zonas",
        xy=(0.05, 0.92), xycoords="axes fraction",
        fontsize=10, verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="gray", alpha=0.9),
    )

    ax.set_xlabel("Votos CA (por zona)", fontsize=11)
    ax.set_ylabel("Votos SE (por zona)", fontsize=11)
    ax.set_title("Scatter CA vs SE por zona — 4 municipios de Boyacá", fontsize=13, pad=10)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT, dpi=150)
    plt.close()
    print(f"Scatter guardado: {OUTPUT}")


if __name__ == "__main__":
    main()
