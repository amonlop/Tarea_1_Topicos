import csv
from pathlib import Path
from collections import defaultdict

EXACT_FILE = Path("validation/exact/exact_src_5keys.csv")

SKETCH_FILES = [
    ("cms", 256, Path("validation/count_min/cms_5keys_w256.csv")),
    ("cms", 1024, Path("validation/count_min/cms_5keys_w1024.csv")),
    ("cms", 4096, Path("validation/count_min/cms_5keys_w4096.csv")),
    ("cs", 256, Path("validation/count_sketch/cs_5keys_w256.csv")),
    ("cs", 1024, Path("validation/count_sketch/cs_5keys_w1024.csv")),
    ("cs", 4096, Path("validation/count_sketch/cs_5keys_w4096.csv")),
]

OUT_CSV = Path("validation/summaries/comparacion_delta.csv")
OUT_TXT = Path("validation/summaries/comparacion_delta.txt")


def cargar_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


exact_rows = cargar_csv(EXACT_FILE)

exact = {}
for row in exact_rows:
    key = (row["key"], int(row["win"]))

    if row["exact_delta"] == "":
        continue

    exact[key] = int(row["exact_delta"])


resultados = []

for sketch, width, path in SKETCH_FILES:
    rows = cargar_csv(path)

    errores = []
    errores_relativos = []
    signos_correctos = 0
    total = 0

    for row in rows:
        key = (row["key"], int(row["win"]))

        # win=0 no tiene delta porque no existe una ventana anterior.
        if row["win"] == "0":
            continue

        if key not in exact:
            raise ValueError(
                f"No existe valor exacto para {row['key']} "
                f"en ventana {row['win']}"
            )

        exact_delta = exact[key]
        estimated_delta = int(row["est_delta"])

        error = abs(estimated_delta - exact_delta)
        errores.append(error)

        if exact_delta != 0:
            errores_relativos.append(error / abs(exact_delta))

        if (
            (estimated_delta > 0 and exact_delta > 0)
            or (estimated_delta < 0 and exact_delta < 0)
            or (estimated_delta == 0 and exact_delta == 0)
        ):
            signos_correctos += 1

        total += 1

    mae = sum(errores) / len(errores)
    max_error = max(errores)

    mre = (
        sum(errores_relativos) / len(errores_relativos)
        if errores_relativos
        else 0.0
    )

    resultados.append({
        "sketch": sketch,
        "width": width,
        "mae_delta": mae,
        "max_abs_delta": max_error,
        "mre_delta": mre,
        "sign_correct": signos_correctos,
        "sign_total": total,
    })


# CSV
with open(OUT_CSV, "w", newline="") as f:
    writer = csv.writer(f)

    writer.writerow([
        "sketch",
        "width",
        "mae_delta",
        "max_abs_delta",
        "mre_delta",
        "sign_correct",
        "sign_total",
    ])

    for r in resultados:
        writer.writerow([
            r["sketch"],
            r["width"],
            f"{r['mae_delta']:.6f}",
            r["max_abs_delta"],
            f"{r['mre_delta']:.6f}",
            r["sign_correct"],
            r["sign_total"],
        ])


# TXT legible
with open(OUT_TXT, "w") as f:
    f.write("COMPARACION DE Δf - CLEAN TRACE\n")
    f.write("=" * 70 + "\n\n")

    f.write(
        f"{'Sketch':<10}"
        f"{'w':<8}"
        f"{'MAE Δf':<15}"
        f"{'Max |error|':<15}"
        f"{'MRE Δf':<15}"
        f"{'Signo':<10}\n"
    )

    f.write("-" * 70 + "\n")

    for r in resultados:
        f.write(
            f"{r['sketch']:<10}"
            f"{r['width']:<8}"
            f"{r['mae_delta']:<15.3f}"
            f"{r['max_abs_delta']:<15}"
            f"{r['mre_delta']:<15.6f}"
            f"{r['sign_correct']}/{r['sign_total']:<10}\n"
        )

print(f"Generado: {OUT_CSV}")
print(f"Generado: {OUT_TXT}")