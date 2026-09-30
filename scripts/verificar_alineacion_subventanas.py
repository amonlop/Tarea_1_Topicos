#!/usr/bin/env python3
"""

Comprueba que el N_j que produce el anillo de contadores de main_ventana 
(columna N de los CSV de los sketches) coincide  con el N_j que produce 
exact_hh (columna N del CSV exacto).

Compara tres columnas: win, tau_us y N. Si una sola ventana difiere, el anillo
está desalineado y todos los resultados posteriores son inválidos.

Uso (desde la raíz del proyecto):
    python3 scripts/verificar_N.py
    python3 scripts/verificar_N.py --out validation/summaries/verificacion_N.txt

Código de salida: 0 si todo coincide, 1 si hay alguna diferencia.
"""
import argparse
import csv
import glob
import sys

# (CSV exacto de referencia, patrón de CSV de sketches a comparar, columnas extra)
PARES = [
    ("attacks/results/exact_ddos.csv", "attacks/results/c*_ddos_w*.csv", ()),
    ("attacks/results/exact_scan.csv", "attacks/results/c*_scan_w*.csv", ()),
    ("validation/exact/exact_src_5keys.csv", "validation/count_min/*.csv", ("key",)),
    ("validation/exact/exact_src_5keys.csv", "validation/count_sketch/*.csv", ("key",)),
]
COLUMNAS = ("win", "tau_us", "N")


def leer(ruta):
    with open(ruta, newline="") as f:
        return list(csv.DictReader(f))


def comparar(ruta_exacto, ruta_sketch, extra):
    cols = COLUMNAS + extra
    ex, sk = leer(ruta_exacto), leer(ruta_sketch)
    if len(ex) != len(sk):
        return [f"distinta cantidad de filas: exacto={len(ex)} sketch={len(sk)}"]
    errores = []
    for a, b in zip(ex, sk):
        if tuple(a[c] for c in cols) != tuple(b[c] for c in cols):
            errores.append(
                f"win={a['win']}: N exacto={a['N']} vs N anillo={b['N']} "
                f"(tau exacto={a['tau_us']} vs tau sketch={b['tau_us']})"
            )
    return errores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="guardar el resultado también en este archivo de texto")
    args = ap.parse_args()

    lineas, fallos, total = [], 0, 0
    for ruta_exacto, patron, extra in PARES:
        archivos = sorted(glob.glob(patron))
        if not archivos:
            lineas.append(f"[AVISO] no hay archivos para {patron}")
            continue
        for ruta in archivos:
            total += 1
            errores = comparar(ruta_exacto, ruta, extra)
            n = len(leer(ruta))
            if errores:
                fallos += 1
                lineas.append(f"[FALLA] {ruta}: {len(errores)} filas distintas")
                lineas += [f"         {e}" for e in errores[:5]]
            else:
                lineas.append(f"[OK]    {ruta}: {n} filas, N_j idéntico al de exact_hh")

    lineas.append("")
    if total == 0:
        lineas.append("No se encontró ningún archivo: ¿estás en la raíz del proyecto?")
        fallos = 1
    elif fallos:
        lineas.append(f"RESULTADO: {fallos} de {total} archivos NO coinciden -> anillo desalineado.")
    else:
        lineas.append(f"RESULTADO: {total} de {total} archivos coinciden ventana por ventana "
                      ", por ende, subventanas correctamente alineadas.")

    texto = "\n".join(lineas)
    print(texto)
    if args.out:
        with open(args.out, "w") as f:
            f.write(texto + "\n")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()