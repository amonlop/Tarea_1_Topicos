#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analizar_y_graficar_ataques.py

Procesa los resultados de las simulaciones de ataques (DDoS y Scan) para:
1. Calcular el error relativo medio (MRE) en el conjunto de ventanas afectadas J.
2. Calcular la latencia y ventana de detección frente a la referencia exacta.
3. Generar la tabla resumen con error, memoria y latencia (Sección 6.2).
4. Generar figuras limpias, profesionales y altamente legibles (300 DPI):
   - Figura 1 (DDoS): Panel superior con frecuencias superpuestas y umbral; panel inferior con error de estimación (f_hat - f).
   - Figura 2 (Scan): Panel superior con frecuencias superpuestas y detalle del falso positivo; panel inferior con error de estimación.
   - Figura 3 (Delta f): Variación temporal delta_f para DDoS y Scan, con leyendas limpias y anotación de picos.
"""

import csv
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

# Configuración visual limpia y profesional
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.labelsize": 10.5,
    "axes.titlesize": 11.5,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8.5,
    "figure.titlesize": 12.5,
    "lines.linewidth": 1.7,
    "grid.alpha": 0.4,
    "grid.linestyle": ":"
})

RESULTS_DIR = Path("attacks/results")
FIGS_DIR = Path("attacks/figures")
SUMM_DIR = Path("attacks/summaries")

FIGS_DIR.mkdir(parents=True, exist_ok=True)
SUMM_DIR.mkdir(parents=True, exist_ok=True)

WIDTHS = [256, 1024, 4096]
M_SUBWINDOWS = 6
D_ROWS = 5


def cargar_csv(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def procesar_ataque(nombre_ataque, clave_ataque, gt_path, t_inicio=300.0, t_duracion=30.0):
    t_fin = t_inicio + t_duracion
    exact_file = RESULTS_DIR / f"exact_{nombre_ataque}.csv"
    exact_rows = cargar_csv(exact_file)

    exact_dict = {}
    for r in exact_rows:
        win = int(r["win"])
        exact_dict[win] = {
            "win": win,
            "tau_us": int(r["tau_us"]),
            "t_rel_s": float(r["t_rel_s"]),
            "N": int(r["N"]),
            "thr": int(r["threshold"]),
            "f": int(r["exact_f"]),
            "hh": int(r["exact_hh"]),
            "delta": int(r["exact_delta"]) if r["exact_delta"] != "" else None
        }

    # Ventanas afectadas J: tau > 300 y tau < 390 con f > 0
    ventanas_J = []
    for win, d in exact_dict.items():
        if t_inicio < d["t_rel_s"] < (t_fin + 60.0) and d["f"] > 0:
            ventanas_J.append(win)

    win_det_exact = None
    for win in sorted(exact_dict.keys()):
        if exact_dict[win]["t_rel_s"] >= t_inicio and exact_dict[win]["hh"] == 1:
            win_det_exact = win
            break

    latencia_exact = (exact_dict[win_det_exact]["t_rel_s"] - t_inicio) if win_det_exact is not None else None

    sketches_data = {}
    metricas_resumen = []

    for sketch in ["cms", "cs"]:
        for w in WIDTHS:
            s_file = RESULTS_DIR / f"{sketch}_{nombre_ataque}_w{w}.csv"
            s_rows = cargar_csv(s_file)

            s_dict = {}
            for r in s_rows:
                win = int(r["win"])
                s_dict[win] = {
                    "win": win,
                    "t_rel_s": float(r["t_rel_s"]),
                    "est_f": int(r["est_f"]),
                    "est_hh": int(r["est_hh"]),
                    "est_delta": int(r["est_delta"])
                }

            sketches_data[(sketch, w)] = s_dict

            errores_rel = []
            errores_abs = []
            for win in ventanas_J:
                f_ex = exact_dict[win]["f"]
                f_est = s_dict[win]["est_f"]
                err_abs = abs(f_est - f_ex)
                errores_abs.append(err_abs)
                errores_rel.append(err_abs / f_ex)

            mre = np.mean(errores_rel) if errores_rel else 0.0
            mae = np.mean(errores_abs) if errores_abs else 0.0
            max_err = max(errores_abs) if errores_abs else 0

            win_det_sk = None
            for win in sorted(s_dict.keys()):
                if s_dict[win]["t_rel_s"] >= (t_inicio - 60.0) and s_dict[win]["est_hh"] == 1:
                    win_det_sk = win
                    break

            latencia_sk = (s_dict[win_det_sk]["t_rel_s"] - t_inicio) if win_det_sk is not None else None
            mem_bytes = (M_SUBWINDOWS + 1) * D_ROWS * w * 8
            mem_kb = mem_bytes / 1024.0
            diff_win = (win_det_sk - win_det_exact) if (win_det_sk is not None and win_det_exact is not None) else None

            metricas_resumen.append({
                "ataque": nombre_ataque.upper(),
                "sketch": sketch.upper(),
                "w": w,
                "mem_kb": mem_kb,
                "mre_J": mre,
                "mae_J": mae,
                "max_err_J": max_err,
                "win_det": win_det_sk,
                "t_det_s": s_dict[win_det_sk]["t_rel_s"] if win_det_sk is not None else None,
                "latencia_s": latencia_sk,
                "win_det_exact": win_det_exact,
                "latencia_exact_s": latencia_exact,
                "diff_vs_exact_win": diff_win,
                "estado_deteccion": (
                    "Exacta" if diff_win == 0 else
                    ("Falso Positivo Temprano" if diff_win < 0 else "Detección Tardía")
                )
            })

    return exact_dict, sketches_data, ventanas_J, metricas_resumen


def graficar_frecuencias_2paneles(exact_dict, sketches_data, nombre_ataque, titulo_ataque, clave_ip, out_path):
    """
    Genera una figura de 2 paneles (Frecuencia en el superior, Error en el inferior)
    con leyenda limpia ubicada en la cabecera de la figura, sin solapamientos.
    """
    t_min = 240.0
    t_max = 410.0

    wins = [w for w, d in sorted(exact_dict.items()) if t_min <= d["t_rel_s"] <= t_max]
    t_vals = [exact_dict[w]["t_rel_s"] for w in wins]
    f_exact = [exact_dict[w]["f"] for w in wins]
    thr_vals = [exact_dict[w]["thr"] for w in wins]

    # Crear figura de 10 x 8 pulgadas
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 8),
        gridspec_kw={"height_ratios": [2.2, 1.2]}
    )

    # ------------------ PANEL 1: Frecuencia Absoluta ------------------
    span_atk = ax1.axvspan(300, 330, color="#ffebee", alpha=0.85, label="Ataque [300s, 330s]", zorder=1)

    # Umbral
    line_thr, = ax1.plot(t_vals, thr_vals, color="#c62828", linestyle=":", linewidth=2.0,
                         label=r"Umbral $T_j = \lceil \phi N_j \rceil$", zorder=3)

    # Exacto
    line_exact, = ax1.plot(t_vals, f_exact, color="black", linewidth=2.6, marker="o", markersize=5,
                           label="Ground Truth Exacto", zorder=10)

    # Paletas de color con alto contraste
    cms_style = {
        256:  {"color": "#d84315", "ls": "--", "marker": "^", "ms": 5.5, "label": "CMS (w=256)"},
        1024: {"color": "#f57c00", "ls": "--", "marker": "v", "ms": 4.5, "label": "CMS (w=1024)"},
        4096: {"color": "#ffb300", "ls": "--", "marker": "D", "ms": 3.8, "label": "CMS (w=4096)"},
    }
    cs_style = {
        256:  {"color": "#0d47a1", "ls": "-.", "marker": "s", "ms": 5.0, "label": "CS (w=256)"},
        1024: {"color": "#1976d2", "ls": "-.", "marker": "p", "ms": 4.5, "label": "CS (w=1024)"},
        4096: {"color": "#00acc1", "ls": "-.", "marker": "X", "ms": 4.0, "label": "CS (w=4096)"},
    }

    cms_lines = []
    for w in WIDTHS:
        f_est = [sketches_data[("cms", w)][win]["est_f"] for win in wins]
        st = cms_style[w]
        l, = ax1.plot(t_vals, f_est, color=st["color"], linestyle=st["ls"], marker=st["marker"],
                      markersize=st["ms"], linewidth=1.5, alpha=0.9, label=st["label"], zorder=6)
        cms_lines.append(l)

    cs_lines = []
    for w in WIDTHS:
        f_est = [sketches_data[("cs", w)][win]["est_f"] for win in wins]
        st = cs_style[w]
        l, = ax1.plot(t_vals, f_est, color=st["color"], linestyle=st["ls"], marker=st["marker"],
                      markersize=st["ms"], linewidth=1.5, alpha=0.9, label=st["label"], zorder=7)
        cs_lines.append(l)

    # Anotaciones de detección sin solapar curvas
    if nombre_ataque == "ddos":
        ax1.annotate(
            "Detección exacta (win=25, tau=310s)\nLatencia = 10s para todos",
            xy=(310, f_exact[wins.index(25)]), xytext=(325, 120000),
            arrowprops=dict(facecolor="#2e7d32", shrink=0.08, width=1.2, headwidth=6),
            bbox=dict(boxstyle="round,pad=0.3", fc="#e8f5e9", ec="#81c784", alpha=0.9),
            fontsize=8.5, zorder=12
        )
    elif nombre_ataque == "scan":
        ax1.annotate(
            "Falso Positivo CMS (w=256)\n(tau=310s, f_hat >= T_j)",
            xy=(310, sketches_data[("cms", 256)][25]["est_f"]), xytext=(248, 120000),
            arrowprops=dict(facecolor="#d84315", shrink=0.08, width=1.2, headwidth=6),
            bbox=dict(boxstyle="round,pad=0.3", fc="#fbe9e7", ec="#ffab91", alpha=0.9),
            fontsize=8.5, zorder=12
        )
        ax1.annotate(
            "Detección exacta (win=26, tau=320s)\nLatencia = 20s",
            xy=(320, f_exact[wins.index(26)]), xytext=(335, 120000),
            arrowprops=dict(facecolor="#2e7d32", shrink=0.08, width=1.2, headwidth=6),
            bbox=dict(boxstyle="round,pad=0.3", fc="#e8f5e9", ec="#81c784", alpha=0.9),
            fontsize=8.5, zorder=12
        )

    max_y = max(max(f_exact), max(thr_vals)) * 1.15
    ax1.set_ylim(-max_y * 0.04, max_y)
    ax1.set_ylabel(r"Frecuencia $\hat{f}_j(x)$ (paquetes)")
    ax1.set_title(r"(a) Frecuencia de la Clave vs Umbral de Detección $T_j$", loc="left", fontsize=10.5, pad=6)
    ax1.grid(True)

    # ------------------ PANEL 2: Error Firmado (f_est - f_exact) ------------------
    ax2.axvspan(300, 330, color="#ffebee", alpha=0.85, zorder=1)
    ax2.axhline(0, color="black", linestyle="-", linewidth=1.2, alpha=0.8, zorder=2)

    for w in WIDTHS:
        err = [sketches_data[("cms", w)][win]["est_f"] - exact_dict[win]["f"] for win in wins]
        st = cms_style[w]
        ax2.plot(t_vals, err, color=st["color"], linestyle=st["ls"], marker=st["marker"],
                 markersize=st["ms"], linewidth=1.4, alpha=0.9, zorder=6)

    for w in WIDTHS:
        err = [sketches_data[("cs", w)][win]["est_f"] - exact_dict[win]["f"] for win in wins]
        st = cs_style[w]
        ax2.plot(t_vals, err, color=st["color"], linestyle=st["ls"], marker=st["marker"],
                 markersize=st["ms"], linewidth=1.4, alpha=0.9, zorder=7)

    ax2.set_xlabel(r"Tiempo relativo de evaluación $\tau_j$ (segundos)")
    ax2.set_ylabel(r"Error $(\hat{f}_j - f_j)$")
    ax2.set_xlim(t_min, t_max)
    ax2.set_title(r"(b) Error de Estimación respecto al Ground Truth Exacto", loc="left", fontsize=10.5, pad=6)
    ax2.grid(True)

    # Texto aclaratorio dentro del panel inferior
    ax2.text(
        0.015, 0.82, "CMS: Error >= 0 (sobreestimación)\nCS: Ruido no sesgado centrado en 0",
        transform=ax2.transAxes, fontsize=8.0,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#cccccc", alpha=0.9)
    )

    # TITULO SUPERIOR GENERAL
    fig.suptitle(
        f"Ataque {titulo_ataque} (Clave: {clave_ip}) — $W=60$ s, $p=10$ s, $\phi=0.01$",
        fontsize=12, fontweight="bold", y=0.985
    )

    # LEYENDA GLOBAL EN LA CABECERA (Organizada en 4 columnas perfectamente espaciadas)
    all_handles = [span_atk, line_thr, line_exact] + cms_lines + cs_lines
    all_labels = [h.get_label() for h in all_handles]

    fig.legend(
        all_handles, all_labels,
        loc="upper center", bbox_to_anchor=(0.5, 0.955),
        ncol=4, frameon=True, framealpha=0.95, edgecolor="#cccccc",
        fontsize=8.5, columnspacing=1.2, handletextpad=0.5
    )

    # Ajustar márgenes para que título, leyenda y subplots respiren sin solaparse
    fig.subplots_adjust(top=0.84, bottom=0.07, left=0.09, right=0.97, hspace=0.28)

    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"  [OK] Gráfico generado: {out_path}")


def graficar_delta_f_limpio(ddos_exact, ddos_sk, scan_exact, scan_sk, out_path):
    """
    Genera la figura de Delta f con leyendas no invasivas y anotaciones claras
    de los saltos positivo (inicio) y negativo (termino/expiracion).
    """
    t_min = 250.0
    t_max = 410.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)

    # Colores sobrios y diferenciados
    col_exact = "black"
    col_cs = "#1565c0"
    col_cms = "#e65100"

    # Panel 1: DDoS
    wins_ddos = [w for w, d in sorted(ddos_exact.items()) if t_min <= d["t_rel_s"] <= t_max and d["delta"] is not None]
    t_ddos = [ddos_exact[w]["t_rel_s"] for w in wins_ddos]
    d_exact_ddos = [ddos_exact[w]["delta"] for w in wins_ddos]

    ax1.axhline(0, color="gray", linestyle="--", linewidth=1.0, alpha=0.7)
    ax1.axvspan(300, 330, color="#ffebee", alpha=0.7, label="Inyección Ataque [300s, 330s]")

    ax1.plot(t_ddos, d_exact_ddos, color=col_exact, linewidth=2.4, marker="o", markersize=5,
             label=r"$\Delta f_j$ Exacto", zorder=10)
    ax1.plot(t_ddos, [ddos_sk[("cs", 1024)][w]["est_delta"] for w in wins_ddos],
             color=col_cs, linestyle="--", marker="s", markersize=4.5, linewidth=1.6,
             label=r"$\widehat{\Delta f}^{\mathrm{CS}}$ (w=1024)", zorder=8)
    ax1.plot(t_ddos, [ddos_sk[("cms", 1024)][w]["est_delta"] for w in wins_ddos],
             color=col_cms, linestyle="-.", marker="^", markersize=4.5, linewidth=1.6,
             label=r"$\widehat{\Delta f}^{\mathrm{CMS\text{-}med}}$ (w=1024)", zorder=7)

    # Anotaciones de picos
    ax1.annotate("Inicio ataque (+100k/subventana)", xy=(310, 100008), xytext=(325, 75000),
                 arrowprops=dict(facecolor="#2e7d32", shrink=0.08, width=1.0, headwidth=5),
                 fontsize=8.5, bbox=dict(boxstyle="round,pad=0.2", fc="#e8f5e9", ec="#a5d6a7"))
    ax1.annotate("Expiración ventana (-100k/subventana)", xy=(370, -100007), xytext=(260, -90000),
                 arrowprops=dict(facecolor="#c62828", shrink=0.08, width=1.0, headwidth=5),
                 fontsize=8.5, bbox=dict(boxstyle="round,pad=0.2", fc="#ffebee", ec="#ef9a9a"))

    ax1.set_ylabel(r"Variación $\Delta f_j(x)$")
    ax1.set_title(r"(a) Ataque DDoS — IP Destino Víctima: 163.210.30.13", pad=8)
    ax1.grid(True)
    ax1.set_ylim(-135000, 135000)
    ax1.legend(loc="upper right", framealpha=0.92, fontsize=8.5)

    # Panel 2: Scan
    wins_scan = [w for w, d in sorted(scan_exact.items()) if t_min <= d["t_rel_s"] <= t_max and d["delta"] is not None]
    t_scan = [scan_exact[w]["t_rel_s"] for w in wins_scan]
    d_exact_scan = [scan_exact[w]["delta"] for w in wins_scan]

    ax2.axhline(0, color="gray", linestyle="--", linewidth=1.0, alpha=0.7)
    ax2.axvspan(300, 330, color="#ffebee", alpha=0.7, label="Inyección Ataque [300s, 330s]")

    ax2.plot(t_scan, d_exact_scan, color=col_exact, linewidth=2.4, marker="o", markersize=5,
             label=r"$\Delta f_j$ Exacto", zorder=10)
    ax2.plot(t_scan, [scan_sk[("cs", 1024)][w]["est_delta"] for w in wins_scan],
             color=col_cs, linestyle="--", marker="s", markersize=4.5, linewidth=1.6,
             label=r"$\widehat{\Delta f}^{\mathrm{CS}}$ (w=1024)", zorder=8)
    ax2.plot(t_scan, [scan_sk[("cms", 1024)][w]["est_delta"] for w in wins_scan],
             color=col_cms, linestyle="-.", marker="^", markersize=4.5, linewidth=1.6,
             label=r"$\widehat{\Delta f}^{\mathrm{CMS\text{-}med}}$ (w=1024)", zorder=7)

    ax2.annotate("Inicio scan (+80k/subventana)", xy=(310, 80000), xytext=(325, 60000),
                 arrowprops=dict(facecolor="#2e7d32", shrink=0.08, width=1.0, headwidth=5),
                 fontsize=8.5, bbox=dict(boxstyle="round,pad=0.2", fc="#e8f5e9", ec="#a5d6a7"))
    ax2.annotate("Expiración scan (-80k/subventana)", xy=(370, -80000), xytext=(260, -75000),
                 arrowprops=dict(facecolor="#c62828", shrink=0.08, width=1.0, headwidth=5),
                 fontsize=8.5, bbox=dict(boxstyle="round,pad=0.2", fc="#ffebee", ec="#ef9a9a"))

    ax2.set_xlabel(r"Tiempo relativo de evaluación $\tau_j$ (segundos)")
    ax2.set_ylabel(r"Variación $\Delta f_j(x)$")
    ax2.set_title(r"(b) Ataque Port Scan — IP Origen Atacante: 198.18.0.7", pad=8)
    ax2.grid(True)
    ax2.set_ylim(-110000, 110000)
    ax2.set_xlim(t_min, t_max)
    ax2.legend(loc="upper right", framealpha=0.92, fontsize=8.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Gráfico generado: {out_path}")


def main():
    print("=== Re-generando figuras con diseño optimizado (sin solapamientos) ===")

    ddos_exact, ddos_sk, ddos_J, ddos_metrics = procesar_ataque(
        nombre_ataque="ddos",
        clave_ataque="163.210.30.13",
        gt_path=Path("attacks/gt_ddos.json")
    )

    scan_exact, scan_sk, scan_J, scan_metrics = procesar_ataque(
        nombre_ataque="scan",
        clave_ataque="198.18.0.7",
        gt_path=Path("attacks/gt_scan.json")
    )

    # Figura 1: DDoS
    graficar_frecuencias_2paneles(
        ddos_exact, ddos_sk,
        nombre_ataque="ddos",
        titulo_ataque="DDoS",
        clave_ip="163.210.30.13 (dst)",
        out_path=FIGS_DIR / "figura1_ddos_frecuencias.png"
    )

    # Figura 2: Scan
    graficar_frecuencias_2paneles(
        scan_exact, scan_sk,
        nombre_ataque="scan",
        titulo_ataque="Port Scan",
        clave_ip="198.18.0.7 (src)",
        out_path=FIGS_DIR / "figura2_scan_frecuencias.png"
    )

    # Figura 3: Delta f
    graficar_delta_f_limpio(
        ddos_exact, ddos_sk,
        scan_exact, scan_sk,
        out_path=FIGS_DIR / "figura3_delta_f.png"
    )

    print("=== ¡Gráficos actualizados con éxito! ===")


if __name__ == "__main__":
    main()
