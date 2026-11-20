// Median of 50 runs of twirl_preprocess (10 tasks x 4, n=20, circuits with measure_all, so the
// remove_final_measurements path runs) and twirl_postprocess (40 results x 50 keys).
// Same sizes as probe/bench_rfm.py.
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
#include <qiskit.h>
#include "../twirl.h"

#define RUNS 50

static double ms(struct timespec a, struct timespec b) {
    return (b.tv_sec - a.tv_sec) * 1e3 + (b.tv_nsec - a.tv_nsec) / 1e6;
}
static int cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

int main(void) {
    const uint32_t n = 20;
    const int64_t T = 10, k = 4, R = T * k, K = 50;
    TwirlTask tasks[10], out[40];
    for (int64_t t = 0; t < T; t++) {
        QkCircuit *qc = qk_circuit_new(n, n);
        uint32_t q0 = 0;
        qk_circuit_gate(qc, QkGate_H, &q0, NULL);
        for (uint32_t q = 1; q < n; q++) {
            uint32_t qs[2] = {q - 1, q};
            qk_circuit_gate(qc, QkGate_CX, qs, NULL);
        }
        qk_circuit_barrier(qc, NULL, 0);
        for (uint32_t q = 0; q < n; q++) qk_circuit_measure(qc, q, q);
        tasks[t].circuit = qc;
        tasks[t].shots = 4000;
    }
    uint8_t flips[4 * 20];
    int64_t bits[2000], counts[2000], offsets[41], out_bits[2000], out_offsets[11];
    double out_probs[2000], pre[RUNS], post[RUNS];
    srand(1);
    for (int64_t r = 0; r < R; r++) {
        offsets[r] = r * K;
        for (int64_t i = 0; i < K; i++) { bits[r * K + i] = rand() % (1 << n); counts[r * K + i] = 20; }
    }
    offsets[R] = R * K;
    struct timespec a, b;
    for (int run = 0; run < RUNS; run++) {
        clock_gettime(CLOCK_MONOTONIC, &a);
        int64_t rc = twirl_preprocess(tasks, T, k, 0, out, flips);
        clock_gettime(CLOCK_MONOTONIC, &b);
        if (rc != TWIRL_OK) { printf("preprocess rc=%lld\n", (long long)rc); return 1; }
        pre[run] = ms(a, b);
        for (int64_t i = 0; i < R; i++) qk_circuit_free(out[i].circuit);
        clock_gettime(CLOCK_MONOTONIC, &a);
        rc = twirl_postprocess(bits, counts, offsets, T, flips, k, n, out_bits, out_probs, out_offsets);
        clock_gettime(CLOCK_MONOTONIC, &b);
        if (rc != TWIRL_OK) { printf("postprocess rc=%lld\n", (long long)rc); return 1; }
        post[run] = ms(a, b);
    }
    qsort(pre, RUNS, sizeof(double), cmp);
    qsort(post, RUNS, sizeof(double), cmp);
    printf("codon: preprocess median %.3f ms (min %.3f); postprocess median %.3f ms (min %.3f)\n",
           pre[RUNS / 2], pre[0], post[RUNS / 2], post[0]);
    for (int64_t t = 0; t < T; t++) qk_circuit_free(tasks[t].circuit);
    return 0;
}
