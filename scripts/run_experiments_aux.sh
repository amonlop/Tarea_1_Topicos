#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

TRAZA_LOWPPS="/mnt/d/Universidad/10mo semestre/Topicos/traza_ddos_lowpps.bin"
VICTIM="163.210.30.13"
OUT_DIR="attacks/auxiliary"

mkdir -p "$OUT_DIR"

echo "=== 1. Ground Truth Exacto (exact_hh) para DDoS Low-PPS ==="
./bin/exact_hh "$TRAZA_LOWPPS" --key dst -W 60 --delta 10 --phi 0.001 \
    --query "$VICTIM" --out-query "$OUT_DIR/exact_ddos_lowpps.csv" --out-windows "$OUT_DIR/win_exact.csv"

echo "=== 2. Simulaciones de Sketches (w=128, 256, 1024) ==="
for w in 128 256 1024; do
    echo "  -> CMS w=$w"
    ./bin/main_ventana "$TRAZA_LOWPPS" --sketch cms --key dst --d 5 --w $w -W 60 --delta 10 --phi 0.001 \
        --query "$VICTIM" --out-query "$OUT_DIR/cms_ddos_w${w}.csv"
    echo "  -> CS w=$w"
    ./bin/main_ventana "$TRAZA_LOWPPS" --sketch cs --key dst --d 5 --w $w -W 60 --delta 10 --phi 0.001 \
        --query "$VICTIM" --out-query "$OUT_DIR/cs_ddos_w${w}.csv"
done

echo "=== Experimento auxiliar completado con éxito ==="
