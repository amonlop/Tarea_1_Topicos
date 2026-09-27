#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graficar_experimento_auxiliar.py
Analiza y grafica el experimento auxiliar de baja intensidad (--pps 1500)
con anchos w in {128, 256, 1024} para forzar una separación visual indiscutible.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

AUX_DIR = Path("attacks/auxiliary")
FIG_OUT = Path("attacks/figures/figura_auxiliar_separacion_clara.png")


def cargar_datos():
    exact = pd.read_csv(AUX_DIR / "exact_ddos_lowpps.csv")
    
    sketches = {}
    for sk in ["cms", "cs"]:
        for w in [128, 256, 1024]:
            p = AUX_DIR / f"{sk}_ddos_w{w}.csv"
            if p.exists():
                sketches[(sk, w)] = pd.read_csv(p)
    return exact, sketches


def graficar(exact, sketches):
    FIG_OUT.parent.mkdir(parents=True, exist_ok=True)
    
    t_min, t_max = 260.0, 400.0
    ex_sub = exact[(exact["t_rel_s"] >= t_min) & (exact["t_rel_s"] <= t_max)].copy()
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.5), sharex=True)
    plt.subplots_adjust(top=0.88, bottom=0.08, left=0.10, right=0.96, hspace=0.25)
    
    # ---------------- Panel 1: Frecuencias f_j(x) ----------------
    ax1.axvspan(300, 330, color="#ffebee", alpha=0.7, label="Ataque activo [300s, 330s]")
    
    # Exacto
    ax1.plot(ex_sub["t_rel_s"], ex_sub["exact_f"], color="black", linewidth=2.5,
             marker="o", markersize=5, label=r"Exacto $f_j(x)$", zorder=10)
    
    # CMS w=128 (fuerte sobreestimación)
    if ("cms", 128) in sketches:
        df = sketches[("cms", 128)]
        s = df[(df["t_rel_s"] >= t_min) & (df["t_rel_s"] <= t_max)]
        ax1.plot(s["t_rel_s"], s["est_f"], color="#d84315", linestyle="-.",
                 marker="^", markersize=5, linewidth=1.8,
                 label=r"CMS ($w=128$) — Fuerte sobreestimación", zorder=8)

    # CS w=128 (fluctuación simétrica)
    if ("cs", 128) in sketches:
        df = sketches[("cs", 128)]
        s = df[(df["t_rel_s"] >= t_min) & (df["t_rel_s"] <= t_max)]
        ax1.plot(s["t_rel_s"], s["est_f"], color="#1565c0", linestyle="--",
                 marker="s", markersize=4.5, linewidth=1.8,
                 label=r"CS ($w=128$) — Insesgado centrado en cero", zorder=9)

    # Referencia w=1024 (convergencia)
    if ("cms", 1024) in sketches:
        df = sketches[("cms", 1024)]
        s = df[(df["t_rel_s"] >= t_min) & (df["t_rel_s"] <= t_max)]
        ax1.plot(s["t_rel_s"], s["est_f"], color="#ff8f00", linestyle=":",
                 linewidth=1.4, label=r"CMS ($w=1024$)", zorder=6)

    if ("cs", 1024) in sketches:
        df = sketches[("cs", 1024)]
        s = df[(df["t_rel_s"] >= t_min) & (df["t_rel_s"] <= t_max)]
        ax1.plot(s["t_rel_s"], s["est_f"], color="#42a5f5", linestyle=":",
                 linewidth=1.4, label=r"CS ($w=1024$)", zorder=7)

    # Umbral
    ax1.plot(ex_sub["t_rel_s"], ex_sub["threshold"], color="#c62828", linestyle=":",
             linewidth=1.5, label=r"Umbral $T = \phi N$ ($\phi=0.001$)", zorder=5)

    ax1.set_ylabel("Frecuencia estimada $\hat{f}(x)$ (paquetes)", fontsize=10)
    ax1.set_title(r"(a) Frecuencia de la Víctima (DDoS $\mathrm{pps}=1500$, salto $+15\mathrm{k}$ por subventana)", fontsize=11, pad=8)
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend(loc="upper left", fontsize=8.5, framealpha=0.92)

    # ---------------- Panel 2: Variación Delta f_j(x) ----------------
    ax2.axhline(0, color="gray", linestyle="--", linewidth=1.0, alpha=0.7)
    ax2.axvspan(300, 330, color="#ffebee", alpha=0.7, label="Ataque activo [300s, 330s]")

    # Exacto Delta
    ax2.plot(ex_sub["t_rel_s"], ex_sub["exact_delta"], color="black", linewidth=2.5,
             marker="o", markersize=5, label=r"Exacto $\Delta f_j$", zorder=10)

    # CMS w=128
    if ("cms", 128) in sketches:
        df = sketches[("cms", 128)]
        s = df[(df["t_rel_s"] >= t_min) & (df["t_rel_s"] <= t_max)]
        ax2.plot(s["t_rel_s"], s["est_delta"], color="#d84315", linestyle="-.",
                 marker="^", markersize=5, linewidth=1.8,
                 label=r"$\widehat{\Delta f}^{\mathrm{CMS\text{-}med}}$ ($w=128$)", zorder=8)

    # CS w=128
    if ("cs", 128) in sketches:
        df = sketches[("cs", 128)]
        s = df[(df["t_rel_s"] >= t_min) & (df["t_rel_s"] <= t_max)]
        ax2.plot(s["t_rel_s"], s["est_delta"], color="#1565c0", linestyle="--",
                 marker="s", markersize=4.5, linewidth=1.8,
                 label=r"$\widehat{\Delta f}^{\mathrm{CS}}$ ($w=128$)", zorder=9)

    # Referencia w=1024
    if ("cms", 1024) in sketches:
        df = sketches[("cms", 1024)]
        s = df[(df["t_rel_s"] >= t_min) & (df["t_rel_s"] <= t_max)]
        ax2.plot(s["t_rel_s"], s["est_delta"], color="#ff8f00", linestyle=":",
                 linewidth=1.4, label=r"$\widehat{\Delta f}^{\mathrm{CMS\text{-}med}}$ ($w=1024$)", zorder=6)

    if ("cs", 1024) in sketches:
        df = sketches[("cs", 1024)]
        s = df[(df["t_rel_s"] >= t_min) & (df["t_rel_s"] <= t_max)]
        ax2.plot(s["t_rel_s"], s["est_delta"], color="#42a5f5", linestyle=":",
                 linewidth=1.4, label=r"$\widehat{\Delta f}^{\mathrm{CS}}$ ($w=1024$)", zorder=7)

    ax2.set_xlabel("Tiempo relativo de evaluación $\\tau_j$ (segundos)", fontsize=10)
    ax2.set_ylabel(r"Variación $\Delta f_j(x)$ (paquetes)", fontsize=10)
    ax2.set_title(r"(b) Estimación del Cambio $\Delta f_j(x) = f_j(x) - f_{j-1}(x)$", fontsize=11, pad=8)
    ax2.grid(True, linestyle="--", alpha=0.6)
    ax2.legend(loc="upper right", fontsize=8.5, framealpha=0.92)

    fig.suptitle(
        r"Experimento Auxiliar: Separación Clara de Estimadores forzando Colisiones ($w=128$, $\mathrm{pps}=1500$)",
        fontsize=12, fontweight="bold", y=0.95
    )

    plt.savefig(FIG_OUT, dpi=300)
    plt.close()
    print(f"[OK] Gráfico auxiliar generado con éxito: {FIG_OUT}")


def main():
    exact, sketches = cargar_datos()
    graficar(exact, sketches)


if __name__ == "__main__":
    main()
