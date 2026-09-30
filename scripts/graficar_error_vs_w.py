#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graficar_error_vs_w.py

Genera un gráfico comparativo de Media ± Desviación Estándar del Error Absoluto y Relativo
en función del tamaño del sketch (w = 256, 1024, 4096) para DDoS y Port Scan.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

RESULTS_DIR = Path("attacks/results")
FIGS_DIR = Path("attacks/figures")
FIGS_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "legend.fontsize": 9,
    "lines.linewidth": 1.8,
    "grid.alpha": 0.4,
    "grid.linestyle": ":"
})

widths = [256, 1024, 4096]
attacks = [("ddos", "Ataque DDoS (Victima dst: 163.210.30.13)"),
           ("scan", "Ataque Port Scan (Atacante src: 198.18.0.7)")]

fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)

for ax_idx, (atk, atk_title) in enumerate(attacks):
    ax = axes[ax_idx]
    exact = pd.read_csv(RESULTS_DIR / f"exact_{atk}.csv")
    j_wins = exact[(exact["t_rel_s"] >= 310) & (exact["t_rel_s"] <= 380)]["win"].values

    cms_means, cms_stds = [], []
    cs_means, cs_stds = [], []

    for w in widths:
        # CMS
        df_cms = pd.read_csv(RESULTS_DIR / f"cms_{atk}_w{w}.csv")
        m_cms = exact[exact["win"].isin(j_wins)].merge(df_cms[df_cms["win"].isin(j_wins)], on="win")
        err_cms = np.abs(m_cms["est_f"] - m_cms["exact_f"])
        cms_means.append(err_cms.mean())
        cms_stds.append(err_cms.std())

        # CS
        df_cs = pd.read_csv(RESULTS_DIR / f"cs_{atk}_w{w}.csv")
        m_cs = exact[exact["win"].isin(j_wins)].merge(df_cs[df_cs["win"].isin(j_wins)], on="win")
        err_cs = np.abs(m_cs["est_f"] - m_cs["exact_f"])
        cs_means.append(err_cs.mean())
        cs_stds.append(err_cs.std())

    # Plot con barras de error en escala log-log
    ax.errorbar(widths, cms_means, yerr=cms_stds, fmt='-s', color='#d95f02', capsize=5, 
                capthick=1.5, elinewidth=1.5, label='Count-Min (Media $\\pm$ 1 std)', markersize=7)
    ax.errorbar([w * 1.05 for w in widths], cs_means, yerr=cs_stds, fmt='-o', color='#1f78b4', capsize=5, 
                capthick=1.5, elinewidth=1.5, label='Count-Sketch (Media $\\pm$ 1 std)', markersize=7)

    # Anotaciones de valores
    for i, w in enumerate(widths):
        ax.annotate(f"{cms_means[i]:.0f}", (w, cms_means[i]), textcoords="offset points", 
                    xytext=(-15, 8), fontsize=8.5, color='#d95f02', weight='bold')
        ax.annotate(f"{cs_means[i]:.0f}", (w * 1.05, cs_means[i]), textcoords="offset points", 
                    xytext=(8, -12), fontsize=8.5, color='#1f78b4', weight='bold')

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(widths)
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.set_xlabel("Ancho del Sketch ($w$) [escala $\\log_2$]")
    ax.set_ylabel("Error Absoluto Medio (MAE en pkts) [escala $\\log_{10}$]")
    ax.set_title(f"{atk_title}")
    ax.grid(True, which="both")
    ax.legend(frameon=True, facecolor="white", framealpha=0.9)

plt.suptitle("Error Absoluto (Media $\\pm$ Desviación Estándar) vs. Ancho del Sketch $w$ (Ventanas $J$)", 
             fontsize=13, weight="bold", y=0.98)
plt.tight_layout()
out_fig = FIGS_DIR / "figura_error_vs_w.png"
plt.savefig(out_fig, dpi=300, bbox_inches="tight")
print(f"Gráfico guardado en: {out_fig}")
