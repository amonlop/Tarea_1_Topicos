// count_sketch.hpp
//
// reutiliza el mismo patrón de countmin, pero los estimadores no están implementados

#pragma once

#include <algorithm>
#include <cstdint>
#include <limits>
#include <random>
#include <stdexcept>
#include <vector>

#include "MurmurHash3.h"

class CountSketch {
public:
    // Dos familias de semillas independientes: una para la posición, otra
    // para el signo. Se generan de la MISMA rng, en secuencia (primero las
    // d de posición, luego las d de signo), así que dos CountSketch con el
    // mismo (d,w,seed) quedan garantizados con el mismo hash de posición Y
    // de signo
    CountSketch(int d, int w, uint32_t seed = 54321) : d_(d), w_(w), seed_(seed) {
        if (d_ <= 0 || w_ <= 0) {
            throw std::invalid_argument("d y w deben ser positivos");
        }
        C_.assign(d_, std::vector<long long>(w_, 0));

        semillas_pos_.resize(d_);
        semillas_sgn_.resize(d_);
        std::mt19937_64 rng(seed_);
        std::uniform_int_distribution<uint32_t> dist(0, std::numeric_limits<uint32_t>::max());
        for (int i = 0; i < d_; i++) semillas_pos_[i] = dist(rng); //de posicion
        for (int i = 0; i < d_; i++) semillas_sgn_[i] = dist(rng); //de signo
    }

    // c = 1 en el caso típico; c < 0 = borrado
    void insertar(uint32_t x, long long c = 1) {
        for (int j = 0; j < d_; j++) {
            uint32_t pos = posicion(x, j);
            int s = signo(x, j);
            C_[j][pos] += (long long)s * c;
        }
    }

    // Estimador CountSketch: mediana de los estimadores por fila.
    long long estimar(uint32_t x) const {
        std::vector<long long> estimaciones;
        estimaciones.reserve(d_);

        for (int j = 0; j < d_; j++) {
            uint32_t pos = posicion(x, j);
            int s = signo(x, j);
            long long z = (long long)s * C_[j][pos];
            estimaciones.push_back(z);
        }

        std::sort(estimaciones.begin(), estimaciones.end());

        long long mediana;
        if (d_ % 2 == 1) {
            mediana = estimaciones[d_ / 2];
        } else {
            mediana = (estimaciones[d_ / 2 - 1] + estimaciones[d_ / 2]) / 2;
        }

        return std::max(0LL, mediana);
    }

    // Estimador de delta para CountSketch.
    // Recibe el sketch deltaA = S_entra - S_sale.
    long long estimar_delta(const CountSketch &deltaA, uint32_t x) const {
        std::vector<long long> estimaciones;
        estimaciones.reserve(d_);

        for (int j = 0; j < d_; j++) {
            uint32_t pos = posicion(x, j);
            int s = signo(x, j);

            long long z = (long long)s * deltaA.C_[j][pos];
            estimaciones.push_back(z);
        }

        std::sort(estimaciones.begin(), estimaciones.end());

        long long mediana;
        if (d_ % 2 == 1) {
            mediana = estimaciones[d_ / 2];
        } else {
            mediana = (estimaciones[d_ / 2 - 1] + estimaciones[d_ / 2]) / 2;
        }

        return mediana;
    }

    void limpiar() {
        for (auto &fila : C_) std::fill(fila.begin(), fila.end(), 0);
    }

    void sumar(const CountSketch &otro) {
        verificar_compatible(otro);
        for (int j = 0; j < d_; j++)
            for (int k = 0; k < w_; k++)
                C_[j][k] += otro.C_[j][k];
    }

    void restar(const CountSketch &otro) {
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
    std::vector<uint32_t> semillas_pos_;
    std::vector<uint32_t> semillas_sgn_;

    uint32_t posicion(uint32_t x, int j) const {
        uint32_t h;
        MurmurHash3_x86_32(&x, sizeof(x), semillas_pos_[j], &h);
        return h % (uint32_t)w_;
    }

    // +1 / -1, a partir de un hash independiente del de posición.
    int signo(uint32_t x, int j) const {
        uint32_t h;
        MurmurHash3_x86_32(&x, sizeof(x), semillas_sgn_[j], &h);
        return (h & 1u) ? 1 : -1;
    }

    void verificar_compatible(const CountSketch &otro) const {
        if (d_ != otro.d_ || w_ != otro.w_ || seed_ != otro.seed_)
            throw std::invalid_argument(
                "sumar/restar entre CountSketch con distinto (d,w,seed): "
                "el hash no coincide");
    }
};
