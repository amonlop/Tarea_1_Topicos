// ventana_deslizante.hpp
//
// contiene el anillo de m subventanas + el sketch agregado A + el anillo paralelo de
// contadores escalares para N_j exacto
//
 // requisito: se debe usar la misma
// estructura de ventana para CMS y CS; solo deben cambiar las operaciones
// propias del estimador

// Uso típico (ver main_windowed_sketch.cpp):
//   VentanaDeslizante<CountMin> vd(d, w, seed, t0, p_us, m);
//   vd.procesar_paquete(ts, clave);   // uno por paquete, precarga o normal
//   vd.expirar_paso(j);               // una vez por evaluación, j >= 1, ANTES
//                                      // de procesar los paquetes de esa evaluación
//   vd.N();                           // N_j exacto de la ventana activa
//   vd.agregado().estimar(clave);     // f_hat(clave) sobre la ventana activa

#pragma once

#include <cstdint>
#include <stdexcept>
#include <vector>

template <class Sketch>
class VentanaDeslizante {
public:
    // t0: timestamp del primer paquete de la traza (en us)
    // p_us: ancho de subventana (--delta, en us)
    // m: número de subventanas en el anillo (W/p)
    VentanaDeslizante(int d, int w, uint32_t seed, uint64_t t0, uint64_t p_us, size_t m)
        : t0_(t0), p_us_(p_us), m_(m), Nagg_(0), agregado_(d, w, seed) {
        if (m_ == 0) throw std::invalid_argument("m debe ser positivo");
        anillo_.reserve(m_);
        for (size_t i = 0; i < m_; i++) anillo_.emplace_back(d, w, seed);
        Nring_.assign(m_, 0);
    }

    // Subventana 1-indexada a la que pertenece ts, bajo la convención t0 + (q-1)*p, t0 + q*p].
    // necesario: ts > t0_
    uint64_t subventana_de(uint64_t ts) const {
        uint64_t delta = ts - t0_;              // se asume ts > t0_
        return (delta + p_us_ - 1) / p_us_;      // techo(delta / p)
    }

    // Agrega un paquete (ts, clave) tanto a su subventana como al agregado.
    // Sirve igual para la precarga inicial y para la carga normal al rotar.
    void procesar_paquete(uint64_t ts, uint32_t clave) {
        if (ts <= t0_) return;
        size_t slot = ranura(ts);
        anillo_[slot].insertar(clave);
        agregado_.insertar(clave);
        Nring_[slot]++;
        Nagg_++;
    }

    // Expira la subventana correspondiente al paso de evaluación j (j >= 1),
    // es decir S_j, antes de cargar los paquetes de la subventana nueva
    void expirar_paso(size_t j) {
        if (j == 0) throw std::invalid_argument("no hay nada que expirar en j=0 (precarga)");
        size_t slot = (j - 1) % m_;
        Nagg_ -= Nring_[slot];
        agregado_.restar(anillo_[slot]);
        anillo_[slot].limpiar();
        Nring_[slot] = 0;
    }

    // por hacer: calcular el cambio de frecuencia entre ventanas

    const Sketch &ranura_sketch(size_t j) const { return anillo_[(j - 1) % m_]; }

    uint64_t N() const { return Nagg_; }
    const Sketch &agregado() const { return agregado_; }
    size_t m() const { return m_; }

private:
    uint64_t t0_, p_us_;
    size_t m_;
    std::vector<Sketch> anillo_;
    std::vector<uint64_t> Nring_;
    uint64_t Nagg_;
    Sketch agregado_;

    size_t ranura(uint64_t ts) const { return (size_t)((subventana_de(ts) - 1) % m_); }
};
