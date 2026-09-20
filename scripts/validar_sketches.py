import csv
import sys
from pathlib import Path
from collections import defaultdict

if len(sys.argv) != 2:
    print("Uso: python3 validar_sketches.py ARCHIVO_SKETCH.csv")
    sys.exit(1)

archivo_sketch = sys.argv[1]

archivo_exact = "validation/exact/exact_src_5keys.csv"

with open(archivo_exact, newline="") as f:
    exactos = list(csv.DictReader(f))

with open(archivo_sketch, newline="") as f:
    estimados = list(csv.DictReader(f))

# Agrupar las filas por clave
exactos_por_clave = defaultdict(list)
estimados_por_clave = defaultdict(list)

for fila in exactos:
    exactos_por_clave[fila["key"]].append(fila)

for fila in estimados:
    estimados_por_clave[fila["key"]].append(fila)

claves = sorted(exactos_por_clave.keys())

for clave in claves:
    if clave not in estimados_por_clave:
        raise ValueError(
            f"La clave {clave} está en el archivo exacto "
            f"pero no en el archivo del sketch."
        )

    if len(exactos_por_clave[clave]) != len(estimados_por_clave[clave]):
        raise ValueError(
            f"La clave {clave} tiene distinta cantidad de ventanas: "
            f"{len(exactos_por_clave[clave])} vs "
            f"{len(estimados_por_clave[clave])}"
        )

    for exacto, estimado in zip(
        exactos_por_clave[clave],
        estimados_por_clave[clave]
    ):
        if exacto["win"] != estimado["win"]:
            raise ValueError(
                f"La clave {clave} tiene ventanas desalineadas: "
                f"exacto={exacto['win']} vs estimado={estimado['win']}"
            )

resultado = []

for clave in claves:
    exactos_clave = exactos_por_clave[clave]
    estimados_clave = estimados_por_clave[clave]

    errores_f = []
    errores_relativos_f = []
    frecuencias_exactas = []
    frecuencias_estimadas = []

    errores_delta = []
    errores_relativos_delta = []
    deltas_exactos = []
    deltas_estimados = []

    signo_correcto = 0
    signo_total = 0
    errores_signo = []

    for exacto, estimado in zip(exactos_clave, estimados_clave):
        win = int(exacto["win"])
        exact_f = int(exacto["exact_f"])
        est_f = int(estimado["est_f"])

        error_f = est_f - exact_f
        errores_f.append(abs(error_f))

        frecuencias_exactas.append(exact_f)
        frecuencias_estimadas.append(est_f)

        if exact_f != 0:
            errores_relativos_f.append(
                abs(error_f) / abs(exact_f)
            )

        if exacto["exact_delta"] != "":
            exact_delta = int(exacto["exact_delta"])
            est_delta = int(estimado["est_delta"])

            error_delta = est_delta - exact_delta
            errores_delta.append(abs(error_delta))

            deltas_exactos.append(exact_delta)
            deltas_estimados.append(est_delta)

            if exact_delta != 0:
                errores_relativos_delta.append(
                    abs(error_delta) / abs(exact_delta)
                )

            mismo_signo = (
                (exact_delta > 0 and est_delta > 0)
                or (exact_delta < 0 and est_delta < 0)
                or (exact_delta == 0 and est_delta == 0)
            )

            if mismo_signo:
                signo_correcto += 1
            else:
                errores_signo.append(
                    (win, exact_delta, est_delta)
                )

            signo_total += 1

    resultado.append(f"=== Clave: {clave} ===")
    resultado.append(f"Ventanas comparadas: {len(exactos_clave)}")

    resultado.append("")
    resultado.append("--- Frecuencia f ---")
    resultado.append(
        f"Frecuencia exacta media: "
        f"{sum(frecuencias_exactas) / len(frecuencias_exactas):.2f}"
    )
    resultado.append(
        f"Frecuencia estimada media: "
        f"{sum(frecuencias_estimadas) / len(frecuencias_estimadas):.2f}"
    )
    resultado.append(
        f"Error absoluto medio: "
        f"{sum(errores_f) / len(errores_f):.2f}"
    )
    resultado.append(
        f"Error absoluto máximo: "
        f"{max(errores_f)}"
    )
    resultado.append(
        f"MRE: "
        f"{sum(errores_relativos_f) / len(errores_relativos_f):.6f}"
    )

    resultado.append("")
    resultado.append("--- Delta f ---")
    resultado.append(
        f"Media de |delta exacto|: "
        f"{sum(abs(x) for x in deltas_exactos) / len(deltas_exactos):.2f}"
    )
    resultado.append(
        f"Media de |delta estimado|: "
        f"{sum(abs(x) for x in deltas_estimados) / len(deltas_estimados):.2f}"
    )
    resultado.append(
        f"Error absoluto medio: "
        f"{sum(errores_delta) / len(errores_delta):.2f}"
    )
    resultado.append(
        f"Error absoluto máximo: "
        f"{max(errores_delta)}"
    )
    resultado.append(
        f"MRE: "
        f"{sum(errores_relativos_delta) / len(errores_relativos_delta):.6f}"
    )
    resultado.append(
        f"Signo correcto: {signo_correcto}/{signo_total}"
    )

    resultado.append("")
    resultado.append("--- Deltas con signo incorrecto ---")

    if errores_signo:
        for win, exact_delta, est_delta in errores_signo:
            resultado.append(
                f"ventana {win}: "
                f"exact_delta={exact_delta}, "
                f"est_delta={est_delta}"
            )
    else:
        resultado.append("No hubo errores de signo.")

    resultado.append("")


texto = "\n".join(resultado)

carpeta_resultados = Path("validation/summaries")
carpeta_resultados.mkdir(parents=True, exist_ok=True)

nombre_sketch = Path(archivo_sketch).stem
archivo_salida = Path("validation/summaries") / f"{nombre_sketch}_validation.txt"

archivo_salida.write_text(texto)

print(texto)
print(f"\nValidación guardada en: {archivo_salida}")