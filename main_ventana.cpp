// main_ventana.cpp
//
// Compilación:
//   g++ -O2 -march=native -std=c++17 -Wall -Wextra
//       main_ventana.cpp MurmurHash3.cpp -o main_ventana
//
// --sketch cms|cs ----> cms: count min sketch, cs: count sketch
//   ejemplo de uso: ./main_ventana traza.bin --sketch cms --key dst --d 5 --w 1024
//                   -W 60 --delta 10 --phi 0.01 --query 203.0.113.9
//                   --out-query out_cms.csv --out-windows win_cms.csv

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cinttypes>
#include <stdexcept>
#include <string>
#include <vector>

#include "traza.hpp"
#include "count_min.hpp"
#include "count_sketch.hpp"
#include "ventana_deslizante.hpp"

struct Config {
    std::string sketch_name;
    KeyKind key = K_SRC;
    int d = 5, w = 1024;
    double W_s = 60.0, delta_s = 10.0, phi = 0.01;
    uint32_t seed = 1234;
    std::vector<std::string> query_text;
    const char *out_query = nullptr;
    const char *out_windows = nullptr;
};

static void usage(const char *p) {
    fprintf(stderr,
        "uso: %s TRAZA.bin --sketch cms|cs [opciones]\n"
        "  --key K            src | dst                  (def. src)\n"
        "  --d D              filas del sketch            (def. 5)\n"
        "  --w W              columnas del sketch         (def. 1024)\n"
        "  -W SEGUNDOS        ancho de ventana             (def. 60)\n"
        "  --delta SEGUNDOS   paso de evaluación           (def. 10)\n"
        "  --phi F            umbral de heavy hitter       (def. 0.01)\n"
        "  --seed N           semilla de las funciones hash (def. 1234)\n"
        "  --query IP         IP a consultar; puede repetirse\n"
        "  --out-query ARCH   CSV de salida por consulta\n"
        "  --out-windows ARCH CSV de salida por ventana (para verificar N_j)\n",
        p);
}

static Config parse_args(int argc, char **argv, const char **path_out) {
    if (argc < 2 || argv[1][0] == '-') { usage(argv[0]); exit(argc < 2 ? 2 : 0); }
    *path_out = argv[1];
    Config cfg;
    for (int i = 2; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&]() -> const char * {
            if (i + 1 >= argc) { fprintf(stderr, "falta valor para %s\n", a.c_str()); exit(2); }
            return argv[++i];
        };
        if (a == "--sketch") cfg.sketch_name = next();
        else if (a == "--key") {
            std::string k = next();
            if (k == "src") cfg.key = K_SRC;
            else if (k == "dst") cfg.key = K_DST;
            else { fprintf(stderr, "clave desconocida: %s (use src|dst)\n", k.c_str()); exit(2); }
        }
        else if (a == "--d") cfg.d = atoi(next());
        else if (a == "--w") cfg.w = atoi(next());
        else if (a == "-W") cfg.W_s = atof(next());
        else if (a == "--delta") cfg.delta_s = atof(next());
        else if (a == "--phi") cfg.phi = atof(next());
        else if (a == "--seed") cfg.seed = (uint32_t)atoll(next());
        else if (a == "--query") cfg.query_text.emplace_back(next());
        else if (a == "--out-query") cfg.out_query = next();
        else if (a == "--out-windows") cfg.out_windows = next();
        else if (a == "-h" || a == "--help") { usage(argv[0]); exit(0); }
        else { fprintf(stderr, "opción no reconocida: %s\n", argv[i]); exit(2); }
    }
    if (cfg.sketch_name != "cms" && cfg.sketch_name != "cs") {
        fprintf(stderr, "--sketch debe ser 'cms' o 'cs'\n"); exit(2);
    }
    if (cfg.d <= 0 || cfg.w <= 0) { fprintf(stderr, "--d y --w deben ser positivos\n"); exit(2); }
    return cfg;
}

// Todo el recorrido de la traza es genérico en el tipo de Sketch
template <class Sketch>
static void ejecutar(const Config &cfg, const Trace &t,
                      const std::vector<uint32_t> &query_ips) {
    const uint64_t t0 = t.r[0].ts_us;
    const uint64_t tend = t.r[t.n - 1].ts_us;
    const uint64_t W_us = (uint64_t)llround(cfg.W_s * 1e6);
    const uint64_t p_us = (uint64_t)llround(cfg.delta_s * 1e6);
    if (W_us == 0 || p_us == 0) { fprintf(stderr, "-W y --delta deben ser positivos\n"); exit(2); }
    if (W_us % p_us != 0) {
        fprintf(stderr, "error: W debe ser múltiplo de delta (la tarea usa W=60, delta=10)\n");
        exit(2);
    }
    const size_t m = (size_t)(W_us / p_us);

    VentanaDeslizante<Sketch> vd(cfg.d, cfg.w, cfg.seed, t0, p_us, m);

    // en la primera evaluación el anillo ya debe estar lleno con (t0, t0+W]". 
    //procesar_paquete() ya filtra ts<=t0.
    size_t hi = 0;
    while (hi < t.n && t.r[hi].ts_us <= t0 + W_us) {
        vd.procesar_paquete(t.r[hi].ts_us, make_key(t.r[hi], cfg.key));
        hi++;
    }

    FILE *fq = cfg.out_query ? fopen(cfg.out_query, "w") : nullptr;
    FILE *fw = cfg.out_windows ? fopen(cfg.out_windows, "w") : nullptr;
    if (cfg.out_query && !fq) { perror("fopen out-query"); exit(1); }
    if (cfg.out_windows && !fw) { perror("fopen out-windows"); exit(1); }
    if (fw) fprintf(fw, "win,tau_us,N,threshold\n");
    // Agrega la estimación del cambio de frecuencia al CSV.
    if (fq) fprintf(fq, "win,tau_us,t_rel_s,sketch,key,N,threshold,est_f,est_hh,est_delta\n");

    size_t win = 0;

    Sketch deltaA(cfg.d, cfg.w, cfg.seed);

    for (uint64_t tau = t0 + W_us; tau <= tend; tau += p_us, ++win) {
        if (win > 0) {
            // Guarda una copia de la subventana que va a salir para hacer la posterior comparativa.
            Sketch subventana_sale = vd.ranura_sketch(win);

            vd.expirar_paso(win);
            while (hi < t.n && t.r[hi].ts_us <= tau) {
                vd.procesar_paquete(t.r[hi].ts_us, make_key(t.r[hi], cfg.key));
                hi++;
            }

            // La ranura que se acaba de reutilizar contiene la subventana que entra
            Sketch subventana_entra = vd.ranura_sketch(win + m);

            // Delta A = subventana que entra - subventana que sale.
            deltaA = subventana_entra;
            deltaA.restar(subventana_sale);
        }

        uint64_t N = vd.N();
        uint64_t thr = (uint64_t)std::ceil(cfg.phi * (double)N);
        if (thr == 0) thr = 1;

        if (fw) fprintf(fw, "%zu,%" PRIu64 ",%" PRIu64 ",%" PRIu64 "\n", win, tau, N, thr);

        if (fq) {
            for (size_t z = 0; z < query_ips.size(); ++z) {
                long long est = vd.agregado().estimar(query_ips[z]);
                
                // Cálculo del delta (Estima el cambio de frecuencia entre la ventana actual y la anterior)
                long long est_delta = (win == 0)
                    ? 0
                    : vd.agregado().estimar_delta(deltaA, query_ips[z]);

                int hh = (est >= (long long)thr) ? 1 : 0;
                fprintf(fq, "%zu,%" PRIu64 ",%.6f,%s,%s,%" PRIu64 ",%" PRIu64 ",%lld,%d,%lld\n",
                        win, tau, (double)(tau - t0) / 1e6, cfg.sketch_name.c_str(),
                        cfg.query_text[z].c_str(), N, thr, est, hh, est_delta);
            }
        }
    }

    if (fq) fclose(fq);
    if (fw) fclose(fw);

    //7 arreglos¿
    size_t total_bytes = (m + 1) * vd.agregado().memoria_bytes();
    fprintf(stderr,
        "== main_ventana (%s) ==\n"
        "d=%d, w=%d, m=%zu subventanas, ventanas evaluadas=%zu\n"
        "memoria de contadores: %.3f MB  ((m+1) x d x w x 8 B = %zu bytes)\n",
        cfg.sketch_name.c_str(), cfg.d, cfg.w, m, win, total_bytes / 1e6, total_bytes);
}

int main(int argc, char **argv) {
    const char *path = nullptr;
    Config cfg = parse_args(argc, argv, &path);

    std::vector<uint32_t> query_ips;
    for (const auto &q : cfg.query_text) {
        uint32_t ip;
        if (!parse_ipv4(q.c_str(), &ip)) { fprintf(stderr, "IP inválida: %s\n", q.c_str()); return 2; }
        query_ips.push_back(ip);
    }

    Trace t = map_trace(path);
    if (t.n == 0) { fprintf(stderr, "error: traza vacía\n"); return 1; }

    if (cfg.sketch_name == "cms") ejecutar<CountMin>(cfg, t, query_ips);
    else {
        try {
            ejecutar<CountSketch>(cfg, t, query_ips);
        } catch (const std::exception &e) {

            
            fprintf(stderr, "\nerror: %s\n", e.what());
            return 3;
        }
    }

    return 0;
}
