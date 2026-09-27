# Detección de Heavy Hitters y Variación de Tráfico en Ventanas Deslizantes con Sketches

Este proyecto corresponde a la **Tarea 1 del curso Tópicos en Grandes Volúmenes de Datos (10mo semestre)**. Implementa y evalúa algoritmos probabilísticos de streaming (**Count-Min Sketch** y **Count-Sketch**) sobre un esquema de **ventana de tiempo deslizante**, aplicados al análisis de tráfico de red a alta velocidad (backbone real y ataques inyectados) con memoria constante acotada.

---

## Tabla de Contenidos

1. [Descripción General](#descripción-general)
2. [Arquitectura del Sistema y Flujo de Datos](#arquitectura-del-sistema-y-flujo-de-datos)
3. [Estructuras de Datos y Algoritmos](#estructuras-de-datos-y-algoritmos)
   - [Formato de Registro Binario (24 Bytes)](#formato-de-registro-binario-24-bytes)
   - [Count-Min Sketch (CMS)](#count-min-sketch-cms)
   - [Count-Sketch (CS)](#count-sketch-cs)
   - [Esquema de Ventana Deslizante (Anillo de Subventanas)](#esquema-de-ventana-deslizante-anillo-de-subventanas)
   - [Estimación del Cambio de Frecuencia ($\Delta f$)](#estimación-del-cambio-de-frecuencia-\delta-f)
4. [Estructura del Repositorio](#estructura-del-repositorio)
5. [Requisitos y Compilación](#requisitos-y-compilación)
6. [Guía de Uso](#guía-de-uso)
   - [1. Obtención de Trazas de Red](#1-obtención-de-trazas-de-red)
   - [2. Conversión de PCAP a Binario (`pcap2bin`)](#2-conversión-de-pcap-a-binario-pcap2bin)
   - [3. Ground Truth y Caracterización Exacta (`exact_hh`)](#3-ground-truth-y-caracterización-exacta-exact_hh)
   - [4. Ejecución de Sketches en Ventana Deslizante (`main_ventana`)](#4-ejecución-de-sketches-en-ventana-deslizante-main_ventana)
   - [5. Inyección de Ataques Sintéticos (`inject_attack.py`)](#5-inyección-de-ataques-sintéticos-inject_attackpy)
   - [6. Generación de Traza Artificial de Prueba (`make_art_trace.py`)](#6-generación-de-traza-artificial-de-prueba-make_art_tracepy)
7. [Validación y Resultados Experimentales](#validación-y-resultados-experimentales)

---

## Descripción General

En enlaces de red troncales (backbone), el volumen de paquetes supera fácilmente los millones por minuto. Mantener contadores exactos para cada dirección IP activa mediante tablas hash tradicionales resulta inviable por restricciones de memoria y velocidad de acceso en hardware/switches.

Este proyecto resuelve dos problemas críticos sobre flujos continuos:
1. **Identificación de Heavy Hitters (Flujos Elefante):** Detectar en cada ventana de tiempo $W$ qué claves (IP origen o destino) representan al menos una fracción $\phi$ del tráfico total de la ventana ($f(x) \ge \lceil \phi \cdot N_j \rceil$).
2. **Estimación de Variación de Frecuencia ($\Delta f$):** Determinar en tiempo real si el flujo de una clave está acelerando o disminuyendo entre ventanas consecutivas ($\Delta f_j = f_j - f_{j-1}$), permitiendo detectar ataques en curso (DDoS, escaneos de puertos) o ráfagas anómalas.

---

## Arquitectura del Sistema y Flujo de Datos

El pipeline del proyecto procesa trazas reales desde archivos de captura pcap hasta la validación estadística contra el ground truth:

```
[Traza PCAP (ej. MAWI)]
         │
         ▼ (pcap2bin.cpp)
[Traza Binaria de 24 B/registro] ──────► [inject_attack.py] ──► [Traza con DDoS/Scan]
         │
         ├───► [exact_hh.cpp] ──────────────────► [Ground Truth: exact_src_5keys.csv]
         │        (Hash Map exacto + Min-Heap)                   │
         │                                                       │
         └───► [main_ventana.cpp] ──────────────► [Estimaciones: cms/cs csv]
                  (Count-Min / Count-Sketch                      │
                   + Anillo de subventanas)                      │
                                                                 ▼
                                                  [scripts/comparar_delta.py]
                                                  [scripts/validar_sketches.py]
                                                                 │
                                                                 ▼
                                                    [Métricas: MAE, MRE, Signo]
```

---

## Estructuras de Datos y Algoritmos

### Formato de Registro Binario (24 Bytes)

Para eliminar el sobrecosto de parsear paquetes pcap durante las simulaciones, todos los módulos operan sobre una representación binaria plana mapeada en memoria (`mmap`) de **24 bytes exactos por paquete** (sin padding, Little-Endian):

| Offset | Tipo | Campo | Descripción |
| :--- | :--- | :--- | :--- |
| `0` | `uint64_t` | `ts_us` | Timestamp en microsegundos desde la época UNIX |
| `8` | `uint32_t` | `src` | IPv4 origen (orden de host little-endian) |
| `12` | `uint32_t` | `dst` | IPv4 destino (orden de host little-endian) |
| `16` | `uint16_t` | `sport` | Puerto TCP/UDP origen (0 si no aplica) |
| `18` | `uint16_t` | `dport` | Puerto TCP/UDP destino (0 si no aplica) |
| `20` | `uint16_t` | `len` | Longitud del paquete en el cable (bytes) |
| `22` | `uint8_t` | `proto` | Protocolo IP (6: TCP, 17: UDP, 1: ICMP) |
| `23` | `uint8_t` | `flags` | Bit 0: SYN, Bit 1: ACK, Bit 2: FIN, Bit 3: RST, Bit 4: Sintético (`0x10`), Bit 5: IPv6 (`0x20`) |

### Count-Min Sketch (CMS)

* **Estructura:** Matriz de contadores de $d$ filas y $w$ columnas.
* **Hashes:** $d$ funciones hash independientes derivadas de `MurmurHash3_x86_32` con distintas semillas: $h_j(x) = \text{hash}_j(x) \pmod w$.
* **Actualización:** Al procesar un elemento $x$ con peso $c$:
  $$C[j][h_j(x)] \leftarrow C[j][h_j(x)] + c, \quad \forall j \in \{0, \dots, d-1\}$$
* **Estimación de Frecuencia:**
  $$\hat{f}(x) = \min_{0 \le j < d} C[j][h_j(x)]$$
  *Garantía teórica:* $\hat{f}(x) \ge f(x)$ siempre (sin subestimaciones). El error por colisiones es $\le \frac{e}{w} \|a\|_1$ con probabilidad $\ge 1 - e^{-d}$.
* **Operaciones Lineales:** Soporta `sumar()` y `restar()` celda a celda entre instancias con idénticos $(d, w, \text{seed})$.

### Count-Sketch (CS)

* **Estructura:** Matriz de contadores de $d$ filas y $w$ columnas.
* **Hashes:** Dos familias de funciones hash:
  1. Posición: $h_j(x) \in \{0, \dots, w-1\}$
  2. Signo: $s_j(x) \in \{-1, +1\}$ (a partir del bit menos significativo de un hash independiente)
* **Actualización:**
  $$C[j][h_j(x)] \leftarrow C[j][h_j(x)] + s_j(x) \cdot c, \quad \forall j \in \{0, \dots, d-1\}$$
* **Estimación de Frecuencia:**
  $$\hat{f}(x) = \max\left(0, \operatorname{mediana}_{0 \le j < d} \left( s_j(x) \cdot C[j][h_j(x)] \right)\right)$$
  *Garantía teórica:* Estimador insesgado ($\mathbb{E}[\hat{f}(x)] = f(x)$). La varianza del ruido depende de la norma $\ell_2$.

### Esquema de Ventana Deslizante (Anillo de Subventanas)

La clase plantilla `VentanaDeslizante<Sketch>` implementa la ventana de tiempo deslizante sin necesidad de almacenar paquetes individuales:
* **Parámetros:**
  - $W$: Tamaño de la ventana activa en segundos (ej. 60 s).
  - $\Delta = p$: Paso de evaluación / ancho de subventana en segundos (ej. 10 s).
  - $m = W / p$: Cantidad de subventanas que componen una ventana activa (ej. $m = 6$).
* **Estructura Interna:**
  - Un búfer circular (anillo) de $m$ sketches: cada uno acumula los paquetes de una subventana temporal $S_q$.
  - Un sketch acumulador global $A$ que representa la suma de las $m$ subventanas activas ($A = \sum_{k=1}^m S_{q-m+k}$).
  - Un anillo paralelo de contadores escalares $N_{\text{ring}}$ para el recuento exacto de paquetes $N_j$ en la ventana.
* **Mantenimiento en Tiempo $O(1)$ por paquete y $O(d \cdot w)$ por evaluación:**
  - Inserción de paquete: Se mapea el timestamp a su ranura $( ( \lceil(ts - t_0)/p\rceil - 1 ) \pmod m )$ y se inserta tanto en el sketch de la subventana como en el agregado $A$.
  - Desplazamiento de ventana (cada $\Delta$ segundos):
    1. Se resta la subventana que expira del sketch agregado: $A \leftarrow A - S_{\text{sale}}$.
    2. Se limpia el sketch de la ranura saliente ($S_{\text{sale}} \leftarrow 0$) para reutilizarlo como la nueva subventana entrante ($S_{\text{entra}}$).

### Estimación del Cambio de Frecuencia ($\Delta f$)

Para evaluar si una clave aumentó o disminuyó su frecuencia entre la ventana $j-1$ y la ventana $j$, se calcula la diferencia sobre el sketch diferencial:
$$\Delta A = S_{\text{entra}} - S_{\text{sale}}$$

Dado que $A_j - A_{j-1} = S_{\text{entra}} - S_{\text{sale}}$, $\Delta A$ concentra exactamente la variación neta de todas las claves entre ventanas.
- **En Count-Sketch:** Se aplica la proyección de signos y la mediana:
  $$\widehat{\Delta f}(x) = \operatorname{mediana}_{j} \left( s_j(x) \cdot \Delta A[j][h_j(x)] \right)$$
- **En Count-Min Sketch:** Como los contadores de $\Delta A$ pueden ser positivos o negativos (debido a las restas de paquetes salientes), se utiliza el estimador experimental de **CMS-mediana** (`estimar_delta`):
  $$\widehat{\Delta f}(x) = \operatorname{mediana}_{j} \left( \Delta A[j][h_j(x)] \right)$$
  (evitando el estimador de mínimo, que sesgaría negativamente las caídas de tráfico).

---

## Estructura del Repositorio

```text
Tarea_1_Topicos/
├── Makefile                     # Reglas de compilación en C++ (-O2, C++17)
├── traza.hpp                    # Definición de Record (24 B), mmap_trace(), parse_ipv4()
├── MurmurHash3.h / .cpp         # Implementación de MurmurHash3_x86_32
├── count_min.hpp                # Implementación de CountMin (insertar, estimar, estimar_delta)
├── count_sketch.hpp             # Implementación de CountSketch (hashes pos/signo, estimadores)
├── ventana_deslizante.hpp       # Template VentanaDeslizante<Sketch> con anillo de m subventanas
├── main_ventana.cpp             # Programa principal para ejecutar CMS/CS sobre trazas
├── exact_hh.cpp                 # Ground truth exacto: stats globales, sliding window y perfilado
├── pcap2bin.cpp                 # Conversor de PCAP a registros binarios planos de 24 B
├── inject_attack.py             # Inyector de ataques sintéticos (DDoS y Scan) en trazas binarias
├── make_art_trace.py            # Generador de traza artificial de juguete para pruebas de borde
├── infotrazas.txt               # Enlaces e instrucciones de descarga de trazas del WIDE/MAWI
├── requirements.txt             # Dependencias Python (numpy>=1.20)
│
├── scripts/
│   ├── validar_sketches.py      # Compara salida de un sketch vs exact_src_5keys.csv por clave
│   └── comparar_delta.py        # Genera tabla comparativa de MAE, MRE, Max Error y Signo
│
└── validation/
    ├── README.md                # Documentación de los experimentos de validación
    ├── exact/
    │   └── exact_src_5keys.csv  # Ground truth exacto para 5 claves en 84 ventanas
    ├── count_min/               # Resultados CSV de CMS para w=256, 1024, 4096
    ├── count_sketch/            # Resultados CSV de CS para w=256, 1024, 4096
    └── summaries/               # Informes de validación individual y tabla comparativa conjunta
```

---

## Requisitos y Compilación

### Requisitos del Sistema

* **C++:** Compilador compatible con C++17 (`g++` 9+ o `clang++` 10+), con soporte para POSIX (`mmap`, `unistd.h`).
* **Python:** Python 3.8+ con `numpy` (instalar con `pip install -r requirements.txt`).
* **Sistema Operativo:** Linux / macOS o entorno WSL (Windows Subsystem for Linux) para la compilación nativa de C++ con `mmap`.

### Compilación

El proyecto incluye un `Makefile` optimizado con `-O2 -march=native -std=c++17 -Wall -Wextra`:

```bash
make
```

Esto generará en la carpeta `bin/`:
* `bin/pcap2bin`
* `bin/exact_hh`
* `bin/main_ventana`

Para limpiar los ejecutables compilados:
```bash
make clean
```

---

## Guía de Uso

### 1. Obtención de Trazas de Red

Se utilizan capturas reales de backbone del repositorio **MAWI** (Measurement and Analysis on the WIDE Internet, punto de captura transpacífico `samplepoint-F`):

```bash
# Descargar traza de referencia (15 minutos de tráfico, sin payload)
curl -L -C - -O https://mawi.wide.ad.jp/mawi/samplepoint-F/2018/201812031400.pcap.gz
```

### 2. Conversión de PCAP a Binario (`pcap2bin`)

Convierte la traza `.pcap` comprimida a registros binarios compactos de 24 B:

```bash
# Descomprimir al vuelo y convertir
zcat 201812031400.pcap.gz | ./bin/pcap2bin > traza.bin

# O bien directamente desde archivo pcap:
./bin/pcap2bin -i traza.pcap -o traza.bin
```

### 3. Ground Truth y Caracterización Exacta (`exact_hh`)

`exact_hh.cpp` es la herramienta de referencia exacta. Ofrece tres modos:

#### Modo 1: Caracterización Global (`--stats`)
Calcula estadísticas globales, número de claves únicas, fracción en el top-10/top-100 y curva rango-frecuencia:
```bash
./bin/exact_hh traza.bin --stats --key src --out-rank rank_src.csv
```

#### Modo 2: Ground Truth en Ventana Deslizante
Calcula las frecuencias exactas, los Heavy Hitters y la variación $\Delta f$:
```bash
./bin/exact_hh traza.bin --key src -W 60 --delta 10 --phi 0.01 \
    --query 202.12.82.146 --query 31.141.14.54 \
    --out-windows win_exact.csv --out-query exact_src_5keys.csv
```

#### Modo 3: Perfil Conductual de Emisores (`--profile`)
Determina la naturaleza de un host (servidor, escáner, botnet, transferencia masiva) a través de su comportamiento (tasa, puertos, ratio SYN sin ACK, CV temporal):
```bash
./bin/exact_hh traza.bin --profile auto
./bin/exact_hh traza.bin --profile 202.12.82.146
```

### 4. Ejecución de Sketches en Ventana Deslizante (`main_ventana`)

Ejecuta el pipeline de streaming con **Count-Min Sketch** o **Count-Sketch**:

```bash
# Ejemplo con Count-Min Sketch (CMS):
./bin/main_ventana traza.bin --sketch cms --key src \
    --d 5 --w 1024 -W 60 --delta 10 --phi 0.01 \
    --query 202.12.82.146 --query 31.141.14.54 \
    --out-query out_cms.csv --out-windows win_cms.csv

# Ejemplo con Count-Sketch (CS):
./bin/main_ventana traza.bin --sketch cs --key src \
    --d 5 --w 1024 -W 60 --delta 10 --phi 0.01 \
    --query 202.12.82.146 --query 31.141.14.54 \
    --out-query out_cs.csv --out-windows win_cs.csv
```

### 5. Inyección de Ataques Sintéticos (`inject_attack.py`)

Permite superponer ataques de red sintéticos sobre una traza binaria base y generar un JSON de ground truth para medir la latencia y precisión de detección de los sketches:

```bash
# Inyección de ataque DDoS (múltiples IPs falsas hacia una víctima fija):
python3 inject_attack.py ddos --base traza.bin --out traza_ddos.bin \
    --gt gt_ddos.json --start 300 --duration 30 --pps 50000 --sources 4000

# Inyección de ataque de escaneo horizontal (un atacante barre miles de destinos):
python3 inject_attack.py scan --base traza.bin --out traza_scan.bin \
    --gt gt_scan.json --start 300 --duration 30 --pps 8000 --dst-count 60000
```

### 6. Generación de Traza Artificial de Prueba (`make_art_trace.py`)

Genera un archivo `.bin` miniatura y determinístico (`toy.bin`) con cantidades de paquetes conocidas por subventana y pruebas de casos de borde (paquetes exactamente en el límite de la subventana y ruido aleatorio para forzar colisiones hash):

```bash
python3 make_art_trace.py toy.bin
```

---

## Validación y Resultados Experimentales

La carpeta `validation/` contiene las pruebas realizadas sobre la traza MAWI limpia `201812031400.bin` con los siguientes parámetros experimentales:
* **Ventana:** $W = 60\text{ s}$
* **Subventana:** $\Delta = 10\text{ s}$ ($m = 6$ subventanas en el anillo)
* **Profundidad de sketches:** $d = 5$
* **Anchos evaluados:** $w \in \{256, 1024, 4096\}$
* **Umbral Heavy Hitter:** $\phi = 0.01$ (1% del tráfico de la ventana)
* **Claves validadas:** 5 direcciones IP elefantes persistentes:
  `202.12.82.146`, `31.141.14.54`, `203.83.101.148`, `203.83.101.14`, `203.83.117.211`.
* **Total de ventanas evaluadas:** 84 ventanas $\to$ **415 valores de $\Delta f$** por sketch.

### Scripts de Evaluación

* **Validación por clave:**
  ```bash
  python3 scripts/validar_sketches.py validation/count_min/cms_5keys_w1024.csv
  ```
* **Comparación multi-ancho:**
  ```bash
  python3 scripts/comparar_delta.py
  ```

### Resultados de la Comparación de $\Delta f$

Resumen de `validation/summaries/comparacion_delta.txt`:

| Sketch | $w$ (columnas) | Memoria ($m+1 \times d \times w$) | MAE $\Delta f$ | Max \|error\| | MRE $\Delta f$ | Signo Correcto |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **CMS** | 256 | ~70 KB | 562.723 | 11545 | 90.17% | 387 / 415 (93.3%) |
| **CMS** | 1024 | ~280 KB | 72.935 | 1450 | 9.80% | 409 / 415 (98.6%) |
| **CMS** | 4096 | ~1.12 MB | **7.964** | **72** | **1.20%** | **415 / 415 (100%)** |
| **CS** | 256 | ~70 KB | 534.431 | 7103 | 56.49% | 402 / 415 (96.9%) |
| **CS** | 1024 | ~280 KB | 96.159 | 2190 | 8.61% | 412 / 415 (99.3%) |
| **CS** | 4096 | ~1.12 MB | **7.472** | **79** | **0.83%** | **415 / 415 (100%)** |

### Conclusiones Principales del Análisis

1. **Convergencia con el ancho $w$:** Tanto CMS como CS reducen drásticamente su error relativo medio (MRE) al pasar de $w=256$ a $w=4096$, cayendo por debajo del 1.2% en ambos sketches.
2. **Acierto en la tendencia (Signo de $\Delta f$):** Para $w=4096$, ambos algoritmos alcanzan un **100% de acierto (415/415)** en determinar si el tráfico sube o baja. Para $w$ pequeño ($w=256$), **Count-Sketch exhibe mejor consistencia de signo (96.9% vs 93.3%)**, ya que su ruido simétrico de media cero introduce menos sesgo direccional que la interferencia constructiva de CMS.
3. **Eficiencia de la Ventana en Anillo:** El esquema de anillo de subventanas y sketch agregado permite deslizar la ventana en tiempo $O(d \cdot w)$ cada $\Delta$ segundos e insertar paquetes en $O(d)$, procesando millones de paquetes en pocos segundos sin desbordar memoria.

---

## Actividad 2: Detección de Ataques Sintéticos (DDoS y Scan)

Se implementó el flujo completo de evaluación de ataques en ventana deslizante:
1. **Generación de trazas:**
   - **DDoS:** Inundación SYN de 4.000 fuentes spoofeadas hacia víctima `163.210.30.13` a 10.000 pps entre $t=300$ s y $t=330$ s (300.000 paquetes inyectados). Clave observada: IP destino (`dst`).
   - **Scan:** Escaneo horizontal de puerto 80 por el atacante `198.18.0.7` hacia 60.000 destinos a 8.000 pps entre $t=300$ s y $t=330$ s (240.000 paquetes inyectados). Clave observada: IP origen (`src`).
2. **Evaluación de Ground Truth y Sketches:** Ejecución de `exact_hh` y `main_ventana` para $w \in \{256, 1024, 4096\}$.
3. **Métricas en conjunto $J$:** 8 ventanas activas afectadas por el ataque ($\tau_j \in [310, 380]$ s).

### Tabla Resumen: Detección, Error y Memoria (Sección 6.2)

| Ataque | Sketch | $w$ (cols) | Memoria | MRE en $J$ | MAE en $J$ | Ventana Det. ($\tau$) | Latencia | Diagnóstico |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **DDoS** | **CMS** | 256 | 70.0 KB | 3.96% | 7232.4 | win=25 (310 s) | 10.0 s | Exacta |
| **DDoS** | **CMS** | 1024 | 280.0 KB | 0.83% | 1537.1 | win=25 (310 s) | 10.0 s | Exacta |
| **DDoS** | **CMS** | 4096 | 1.12 MB | 0.19% | 350.4 | win=25 (310 s) | 10.0 s | Exacta |
| **DDoS** | **CS** | 256 | 70.0 KB | **0.16%** | **232.9** | win=25 (310 s) | 10.0 s | Exacta |
| **DDoS** | **CS** | 1024 | 280.0 KB | **0.04%** | **95.6** | win=25 (310 s) | 10.0 s | Exacta |
| **DDoS** | **CS** | 4096 | 1.12 MB | **0.006%** | **12.1** | win=25 (310 s) | 10.0 s | Exacta |
| **SCAN** | **CMS** | 256 | 70.0 KB | 5.71% | 8382.1 | **win=25 (310 s)** | **10.0 s** | **Falso Positivo Temprano** |
| **SCAN** | **CMS** | 1024 | 280.0 KB | 0.66% | 978.5 | win=26 (320 s) | 20.0 s | Exacta |
| **SCAN** | **CMS** | 4096 | 1.12 MB | 0.07% | 101.2 | win=26 (320 s) | 20.0 s | Exacta |
| **SCAN** | **CS** | 256 | 70.0 KB | 11.86% | 14327.4 | win=26 (320 s) | 20.0 s | Exacta |
| **SCAN** | **CS** | 1024 | 280.0 KB | 0.81% | 1031.2 | win=26 (320 s) | 20.0 s | Exacta |
| **SCAN** | **CS** | 4096 | 1.12 MB | **0.01%** | **18.5** | win=26 (320 s) | 20.0 s | Exacta |

* **Referencia Exacta DDoS:** Detectado en $\text{win}=25$ ($\tau=310$ s), Latencia = $10.0$ s.
* **Referencia Exacta Scan:** Detectado en $\text{win}=26$ ($\tau=320$ s), Latencia = $20.0$ s (en $\tau=310$ s, $f=80.000 < T=82.149$).
* **Falso Positivo Temprano en CMS ($w=256$):** Debido a la sobreestimación por colisiones hash, CMS estimó $\hat{f}=86.515 \ge 82.149$ en la ventana 25, alertando el ataque 10 segundos antes que el conteo exacto (comportamiento documentado y esperado por diseño en la pauta).

### Figuras Generadas

Las figuras de alta resolución (300 dpi) se encuentran almacenadas en `attacks/figures/`:
* **`figura1_ddos_frecuencias.png`**: Curvas superpuestas de frecuencia exacta, umbral $T_j$ y estimaciones de CMS y CS ($w \in \{256, 1024, 4096\}$) para el ataque DDoS.
* **`figura2_scan_frecuencias.png`**: Curvas superpuestas para el ataque Scan con detalle de la transición en el umbral.
* **`figura3_delta_f.png`**: Variación $\Delta f_j(x)$ para ambos ataques, comparando el cálculo exacto contra CountSketch y CMS-mediana.