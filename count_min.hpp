// count_min.hpp


//
//      La clave es uint32_t (la IP como entero), y la traza
//      llega como binario mmap-eado (ver traza.hpp), así que
//      la IP YA es un entero de 32 bits

//      El constructor recibe un `seed` para poder compartir el mismo hash entre 
//      subventanas


#pragma once

#include <algorithm>
#include <cstdint>
#include <limits>
#include <random>
#include <stdexcept>
#include <vector>

#include "MurmurHash3.h"

class CountMin {
public:
    // d: filas (funciones hash), w: columnas, seed: semilla del generador

    CountMin(int d, int w, uint32_t seed = 12345) : d_(d), w_(w), seed_(seed) {
        if (d_ <= 0 || w_ <= 0) {
            throw std::invalid_argument("d y w deben ser positivos");
        }
        C_.assign(d_, std::vector<long long>(w_, 0));

        semillas_.resize(d_);
        std::mt19937_64 rng(seed_);
        std::uniform_int_distribution<uint32_t> dist(0, std::numeric_limits<uint32_t>::max());
        for (int i = 0; i < d_; i++) semillas_[i] = dist(rng);
    }

    // insertar(x, c): incrementa los d contadores mapeados por x.
    void insertar(uint32_t x, long long c = 1) {
        for (int j = 0; j < d_; j++) {
            uint32_t pos = posicion(x, j);
            C_[j][pos] += c;
        }
    }

    // estimar(x): mínimo de los d contadores mapeados por x (sección 5.1).
    long long estimar(uint32_t x) const {
        long long freq_est = std::numeric_limits<long long>::max();
        for (int j = 0; j < d_; j++) {
            uint32_t pos = posicion(x, j);
            freq_est = std::min(freq_est, C_[j][pos]);
        }
        return freq_est;
    }

    // Pone todos los contadores en 0, usado para reciclar la ranura del anillo saliente
    void limpiar() {
        for (auto &fila : C_) std::fill(fila.begin(), fila.end(), 0);
    }

    void sumar(const CountMin &otro) {
        verificar_compatible(otro);
        for (int j = 0; j < d_; j++)
            for (int k = 0; k < w_; k++)
                C_[j][k] += otro.C_[j][k];
    }

    void restar(const CountMin &otro) {
        verificar_compatible(otro);
        for (int j = 0; j < d_; j++)
            for (int k = 0; k < w_; k++)
                C_[j][k] -= otro.C_[j][k];
    }

    int filas() const { return d_; }
    int columnas() const { return w_; }
    uint32_t semilla() const { return seed_; }
    size_t memoria_bytes() const { return (size_t)d_ * w_ * sizeof(long long); }

private:
    int d_, w_;
    uint32_t seed_;
    std::vector<std::vector<long long>> C_;
    std::vector<uint32_t> semillas_;

    uint32_t posicion(uint32_t x, int j) const {
        uint32_t h;
        MurmurHash3_x86_32(&x, sizeof(x), semillas_[j], &h);
        return h % (uint32_t)w_;
    }

    void verificar_compatible(const CountMin &otro) const {
        if (d_ != otro.d_ || w_ != otro.w_ || seed_ != otro.seed_)
            throw std::invalid_argument(
                "sumar/restar entre CountMin con distinto (d,w,seed): "
                "el hash no coincide");
    }
};
