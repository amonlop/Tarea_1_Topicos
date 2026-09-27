#!/usr/bin/env bash
set -e

# Asegurarse de estar en el directorio raíz del proyecto
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

TRAZA_DDOS="/mnt/d/Universidad/10mo semestre/Topicos/traza_ddos.bin"
TRAZA_SCAN="/mnt/d/Universidad/10mo semestre/Topicos/traza_scan.bin"
VICTIM="163.210.30.13"
ATTACKER="198.18.0.7"

OUT_DIR="attacks/results"
mkdir -p "$OUT_DIR"

echo "=== 1. Ground Truth para DDoS (exact_hh) ==="
./bin/exact_hh "$TRAZA_DDOS" --key dst -W 60 --delta 10 --phi 0.01 \
    --query "$VICTIM" --out-query "$OUT_DIR/exact_ddos.csv" --out-windows "$OUT_DIR/win_exact_ddos.csv"

echo "=== 2. Sketches para DDoS (Count-Min y Count-Sketch) ==="
for w in 256 1024 4096; do
    echo "  -> CMS w=$w"
    ./bin/main_ventana "$TRAZA_DDOS" --sketch cms --key dst --d 5 --w $w -W 60 --delta 10 --phi 0.01 \
        --query "$VICTIM" --out-query "$OUT_DIR/cms_ddos_w${w}.csv"
    echo "  -> CS w=$w"
    ./bin/main_ventana "$TRAZA_DDOS" --sketch cs --key dst --d 5 --w $w -W 60 --delta 10 --phi 0.01 \
        --query "$VICTIM" --out-query "$OUT_DIR/cs_ddos_w${w}.csv"
done

echo "=== 3. Ground Truth para Scan (exact_hh) ==="
./bin/exact_hh "$TRAZA_SCAN" --key src -W 60 --delta 10 --phi 0.01 \
    --query "$ATTACKER" --out-query "$OUT_DIR/exact_scan.csv" --out-windows "$OUT_DIR/win_exact_scan.csv"

echo "=== 4. Sketches para Scan (Count-Min y Count-Sketch) ==="
for w in 256 1024 4096; do
    echo "  -> CMS w=$w"
    ./bin/main_ventana "$TRAZA_SCAN" --sketch cms --key src --d 5 --w $w -W 60 --delta 10 --phi 0.01 \
        --query "$ATTACKER" --out-query "$OUT_DIR/cms_scan_w${w}.csv"
    echo "  -> CS w=$w"
    ./bin/main_ventana "$TRAZA_SCAN" --sketch cs --key src --d 5 --w $w -W 60 --delta 10 --phi 0.01 \
        --query "$ATTACKER" --out-query "$OUT_DIR/cs_scan_w${w}.csv"
done

echo "=== ¡Todas las simulaciones se completaron con éxito! ==="
