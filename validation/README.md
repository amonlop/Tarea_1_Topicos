# Validation

Esta carpeta contiene los resultados de validación de **Count-Min Sketch (CMS)** y **CountSketch (CS)** sobre la traza limpia utilizada en la tarea.

## Estructura

```text
validation/
├── count_min/       # Resultados de CMS
├── count_sketch/    # Resultados de CountSketch
├── exact/           # Ground truth obtenido con exact_hh
└── summaries/       # Resúmenes de las validaciones
```

## Datos utilizados

La validación se realizó sobre:

```text
201812031400.bin
```

La traza contiene tráfico de red y fue procesada mediante `exact_hh` para obtener las frecuencias exactas.

Se utilizaron:

* Ventana: `W = 60 s`
* Subventana: `Δ = 10 s`
* `m = 6` subventanas
* `d = 5` filas
* `w ∈ {256, 1024, 4096}`
* `phi = 0.01`

## Selección de las 5 claves

Las 5 claves utilizadas para la validación fueron seleccionadas a partir de los resultados de `exact_hh`.

Primero se ejecutó `exact_hh` sobre la traza completa para obtener las estadísticas de frecuencia. A partir de los resultados se identificaron las claves con mayor frecuencia y se seleccionaron 5 claves que aparecen de forma consistente entre los heavy hitters de las ventanas.

Las claves seleccionadas fueron:

```text
202.12.82.146
31.141.14.54
203.83.101.148
203.83.101.14
203.83.117.211
```

La selección permite validar los sketches sobre claves que aparecen repetidamente en las ventanas, en lugar de utilizar claves que aparecen de manera aislada.

## `exact/`

`exact_src_5keys.csv` contiene el **ground truth** para las 5 claves.

Incluye, entre otros datos:

* frecuencia exacta (`exact_f`)
* heavy hitter exacto (`exact_hh`)
* cambio exacto de frecuencia (`exact_delta`)

Cada clave tiene 84 ventanas. `win=0` no tiene `Δf`, ya que no existe una ventana anterior, por lo que se obtienen:

```text
5 claves × 83 Δf = 415 valores de Δf
```

## `count_min/` y `count_sketch/`

Contienen los resultados de los sketches para:

```text
w = 256
w = 1024
w = 4096
```

El campo `est_delta` corresponde a la estimación de `Δf`.

* En **CountSketch**, se utiliza el estimador estándar basado en signo + mediana.
* En **CMS**, se utiliza el estimador experimental CMS-median.

## `summaries/`

Los archivos `*_validation.txt` contienen la validación **por cada una de las 5 claves**.

Por ejemplo:

```text
cs_5keys_w1024_validation.txt
```

contiene los resultados de CountSketch con `w=1024`, separados por clave.

`comparacion_delta.txt` y `comparacion_delta.csv` resumen conjuntamente las **415 estimaciones de Δf** de las 5 claves, permitiendo comparar CMS-median y CountSketch para los distintos valores de `w`.

Las métricas utilizadas son:

* MAE: error absoluto medio.
* MRE: error relativo medio.
* Max |error|: máximo error absoluto.
* Signo: cantidad de estimaciones con el mismo signo que el `Δf` exacto.

## Scripts utilizados

La validación individual se realizó con:

```text
scripts/validar_sketches.py
```

La comparación conjunta de `Δf` se generó con:

```text
scripts/comparar_delta.py
```
