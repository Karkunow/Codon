// Benchmark driver: dlopens a libtwirl variant and times preprocess/postprocess.
// Usage: bench <dylib> [n T k depth K RUNS]   (defaults match probe/bench_rfm.c: 20 10 4 1 50 50)
// depth = how many CX chains the circuit has (1 == probe/bench_rfm.c). Prints median/min/p90.
#include <dlfcn.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
#include <qiskit.h>
#include "../twirl.h"

typedef int64_t (*pre_fn)(const TwirlTask *, int64_t, int64_t, int64_t, TwirlTask *, uint8_t *);
typedef int64_t (*post_fn)(const int64_t *, const int64_t *, const int64_t *, int64_t, const uint8_t *,
                           int64_t, int64_t, int64_t *, double *, int64_t *);

static double ms(struct timespec a, struct timespec b) {
    return (b.tv_sec - a.tv_sec) * 1e3 + (b.tv_nsec - a.tv_nsec) / 1e6;
}
static int cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: bench <dylib> [n T k depth K RUNS]\n"); return 2; }
    const uint32_t n = argc > 2 ? atoi(argv[2]) : 20;
    const int64_t T = argc > 3 ? atoi(argv[3]) : 10;
    const int64_t k = argc > 4 ? atoi(argv[4]) : 4;
    const int depth = argc > 5 ? atoi(argv[5]) : 1;
    const int64_t K = argc > 6 ? atoi(argv[6]) : 50;
    const int RUNS = argc > 7 ? atoi(argv[7]) : 50;
    const int64_t R = T * k;
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 2; }
    pre_fn pre_f = (pre_fn)dlsym(h, "twirl_preprocess");
    post_fn post_f = (post_fn)dlsym(h, "twirl_postprocess");
    if (!pre_f || !post_f) { fprintf(stderr, "dlsym failed\n"); return 2; }

    TwirlTask *tasks = calloc(T, sizeof *tasks), *out = calloc(R, sizeof *out);
    for (int64_t t = 0; t < T; t++) {
        QkCircuit *qc = qk_circuit_new(n, n);
        uint32_t q0 = 0;
        qk_circuit_gate(qc, QkGate_H, &q0, NULL);
        for (int d = 0; d < depth; d++)
            for (uint32_t q = 1; q < n; q++) {
                uint32_t qs[2] = {q - 1, q};
                qk_circuit_gate(qc, QkGate_CX, qs, NULL);
            }
        qk_circuit_barrier(qc, NULL, 0);
        for (uint32_t q = 0; q < n; q++) qk_circuit_measure(qc, q, q);
        tasks[t].circuit = qc;
        tasks[t].shots = 4000;
    }
    uint8_t *flips = calloc(k * n, 1);
    int64_t *bits = calloc(R * K, 8), *counts = calloc(R * K, 8), *offsets = calloc(R + 1, 8);
    int64_t *out_bits = calloc(R * K, 8), *out_offsets = calloc(T + 1, 8);
    double *out_probs = calloc(R * K, 8), *pre = calloc(RUNS, 8), *post = calloc(RUNS, 8);
    srand(1);
    for (int64_t r = 0; r < R; r++) {
        offsets[r] = r * K;
        for (int64_t i = 0; i < K; i++) { bits[r * K + i] = rand() % (1 << (n > 30 ? 30 : n)); counts[r * K + i] = 20; }
    }
    offsets[R] = R * K;
    struct timespec a, b;
    for (int run = 0; run < RUNS; run++) {
        clock_gettime(CLOCK_MONOTONIC, &a);
        int64_t rc = pre_f(tasks, T, k, 0, out, flips);
        clock_gettime(CLOCK_MONOTONIC, &b);
        if (rc != TWIRL_OK) { printf("preprocess rc=%lld\n", (long long)rc); return 1; }
        pre[run] = ms(a, b);
        for (int64_t i = 0; i < R; i++) qk_circuit_free(out[i].circuit);
        clock_gettime(CLOCK_MONOTONIC, &a);
        rc = post_f(bits, counts, offsets, T, flips, k, n, out_bits, out_probs, out_offsets);
        clock_gettime(CLOCK_MONOTONIC, &b);
        if (rc != TWIRL_OK) { printf("postprocess rc=%lld\n", (long long)rc); return 1; }
        post[run] = ms(a, b);
    }
    qsort(pre, RUNS, sizeof(double), cmp);
    qsort(post, RUNS, sizeof(double), cmp);
    printf("%-28s n=%u T=%lld k=%lld d=%d K=%lld: pre med %.3f min %.3f p90 %.3f | post med %.4f min %.4f p90 %.4f\n",
           argv[1], n, (long long)T, (long long)k, depth, (long long)K,
           pre[RUNS / 2], pre[0], pre[RUNS * 9 / 10], post[RUNS / 2], post[0], post[RUNS * 9 / 10]);
    for (int64_t t = 0; t < T; t++) qk_circuit_free(tasks[t].circuit);
    return 0;
}
