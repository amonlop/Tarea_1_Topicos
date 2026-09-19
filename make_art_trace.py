#!/usr/bin/env python3


# codigo para generar traza artificial y poder verificar correctitud de los sketches


"""Genera una traza .bin diminuta y determinística para probar a mano el
anillo de subventanas (sin depender de la traza MAWI real ni de C).

Uso: ./make_art_trace.py salida.bin

Formato: igual al de pcap2bin (24 B/registro, little-endian):
    ts_us:u64, src:u32, dst:u32, sport:u16, dport:u16, len:u16, proto:u8, flags:u8
"""
import sys
import numpy as np

REC = np.dtype([
    ("ts", "<u8"), ("src", "<u4"), ("dst", "<u4"),
    ("sport", "<u2"), ("dport", "<u2"), ("len", "<u2"),
    ("proto", "u1"), ("flags", "u1"),
])
assert REC.itemsize == 24

T0 = 1_700_000_000_000_000  # t0 arbitrario, en microsegundos
P = 10_000_000              # p = 10 s, en microsegundos

# Construyo a mano una traza de 3 minutos (18 subventanas de 10 s) con un
# número de paquetes DISTINTO y conocido por subventana, para poder calcular
# a mano cuál debería ser N_j en cada evaluación y comparar.
#
# paquetes_por_subventana[q-1] = cuántos paquetes caen en S_q (q = 1..18)
paquetes_por_subventana = [5, 7, 3, 9, 4, 6,   # S1..S6  (primera ventana W0)
                            8, 2, 5, 5, 5, 5,   # S7..S12 (ventanas siguientes)
                            1, 10, 4, 4, 4, 4]  # S13..S18

rows = []
victim_dst = 0xC0A80001  # 192.168.0.1 -- clave de prueba para --query !!!!!!!!

for q, cnt in enumerate(paquetes_por_subventana, start=1):
    lo = T0 + (q - 1) * P + 1     # dentro de (t0+(q-1)p, t0+q p]
    hi = T0 + q * P               # último paquete EXACTO en el borde,
    # para forzar a propósito el caso límite "paquete justo en el borde"
    if cnt == 1:
        ts_list = [hi]
    else:
        # cnt-1 paquetes distribuidos dentro del intervalo + 1 exactamente
        # en el borde superior (caso límite obligatorio a probar)
        ts_list = list(np.linspace(lo, hi - 1, cnt - 1, dtype=np.uint64)) + [hi]
    for ts in ts_list:
        rows.append((int(ts), 0x0A000001, victim_dst, 12345, 80, 64, 6, 0))

# Ruido: paquetes hacia OTRAS IPs destino, para que w chico produzca
# colisiones reales contra la clave de prueba y se pueda verificar la
# propiedad de sobreestimación de CMS (f_hat >= f_exacta siempre).
rng = np.random.default_rng(7)
noise_dsts = (0xC0A80100 + rng.integers(0, 4000, size=4000)).astype(np.uint32)
noise_ts = rng.integers(T0 + 1, T0 + 180_000_000, size=4000).astype(np.uint64)
for ts, dst in zip(noise_ts, noise_dsts):
    rows.append((int(ts), 0x0A000002, int(dst), 22222, 80, 64, 6, 0))

rows.sort(key=lambda r: r[0])
arr = np.array(rows, dtype=REC)

out = sys.argv[1] if len(sys.argv) > 1 else "toy.bin"
arr.tofile(out)
print(f"escrito {out}: {len(arr)} registros, t0={T0}, "
      f"duración={(int(arr['ts'][-1]) - T0)/1e6:.1f} s")
print("N_j esperado por ventana (suma de 6 subventanas consecutivas):")
for j in range(len(paquetes_por_subventana) - 6 + 1):
    print(f"  ventana {j}: subventanas S{j+1}..S{j+6} -> "
          f"N = {sum(paquetes_por_subventana[j:j+6])}")
