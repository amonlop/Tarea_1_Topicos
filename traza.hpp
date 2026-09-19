// traza.hpp -- lectura de la traza binaria y utilidades de claves.
//
// Idéntico en formato a exact_hh.cpp / pcap2bin.cpp (24 B/registro), para
// que la comparación entre programas sea válida byte a byte.

#pragma once

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#pragma pack(push, 1)
struct Record {
    uint64_t ts_us;
    uint32_t src, dst;
    uint16_t sport, dport, len;
    uint8_t proto, flags;
};
#pragma pack(pop)
static_assert(sizeof(Record) == 24, "el registro debe ocupar 24 bytes");

struct Trace {
    const Record *r = nullptr;
    size_t n = 0;
    void *addr = nullptr;
    size_t bytes = 0;

    ~Trace() { if (addr) munmap(addr, bytes); }
};

inline Trace map_trace(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open"); exit(1); }
    struct stat st;
    if (fstat(fd, &st) < 0) { perror("fstat"); exit(1); }
    if (st.st_size % (off_t)sizeof(Record)) {
        fprintf(stderr, "error: el tamaño no es múltiplo de 24 B\n");
        exit(1);
    }
    void *p = mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (p == MAP_FAILED) { perror("mmap"); exit(1); }
    close(fd);
    madvise(p, st.st_size, MADV_SEQUENTIAL);
    Trace t;
    t.addr = p; t.bytes = st.st_size;
    t.r = (const Record *)p;
    t.n = st.st_size / sizeof(Record);
    return t;
}

inline bool parse_ipv4(const char *s, uint32_t *out) {
    unsigned a, b, c, d;
    if (sscanf(s, "%u.%u.%u.%u", &a, &b, &c, &d) != 4) return false;
    if (a > 255 || b > 255 || c > 255 || d > 255) return false;
    *out = (a << 24) | (b << 16) | (c << 8) | d;
    return true;
}

// Solo src/dst (ddos -> dst, scan -> src).
enum KeyKind { K_SRC, K_DST };

inline uint32_t make_key(const Record &r, KeyKind k) {
    return k == K_SRC ? r.src : r.dst;
}
