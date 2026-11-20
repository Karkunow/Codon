// Times twirl_preprocess (10 tasks x 4 instances, n=20) and twirl_postprocess
// (40 results x 50 keys), the same sizes as probe/bench_py.py.
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
#include <qiskit.h>
#include "../twirl.h"

static double ms(struct timespec a, struct timespec b) {
    return (b.tv_sec - a.tv_sec) * 1e3 + (b.tv_nsec - a.tv_nsec) / 1e6;
}

int main(void) {
    const uint32_t n = 20;
    const int64_t T = 10, k = 4;
    TwirlTask tasks[10];
    for (int64_t t = 0; t < T; t++) {
        QkCircuit *qc = qk_circuit_new(n, 0);
        uint32_t q0 = 0;
        qk_circuit_gate(qc, QkGate_H, &q0, NULL);
        for (uint32_t q = 1; q < n; q++) {
            uint32_t qs[2] = {q - 1, q};
            qk_circuit_gate(qc, QkGate_CX, qs, NULL);
        }
        tasks[t].circuit = qc;
        tasks[t].shots = 4000;
    }
    TwirlTask out[40];
    uint8_t flips[4 * 20];
    struct timespec a, b;
    clock_gettime(CLOCK_MONOTONIC, &a);
    int64_t rc = twirl_preprocess(tasks, T, k, 0, out, flips);
    clock_gettime(CLOCK_MONOTONIC, &b);
    printf("preprocess rc=%lld: %.3f ms\n", (long long)rc, ms(a, b));

    const int64_t R = T * k, K = 50;
    int64_t bits[2000], counts[2000], offsets[41];
    srand(1);
    for (int64_t r = 0; r < R; r++) {
        offsets[r] = r * K;
        for (int64_t i = 0; i < K; i++) { bits[r * K + i] = rand() % (1 << n); counts[r * K + i] = 20; }
    }
    offsets[R] = R * K;
    int64_t out_bits[2000], out_offsets[11];
    double out_probs[2000];
    clock_gettime(CLOCK_MONOTONIC, &a);
    rc = twirl_postprocess(bits, counts, offsets, T, flips, k, n, out_bits, out_probs, out_offsets);
    clock_gettime(CLOCK_MONOTONIC, &b);
    double sum = 0;
    for (int64_t i = out_offsets[0]; i < out_offsets[1]; i++) sum += out_probs[i];
    printf("postprocess rc=%lld: %.3f ms; task0 entries=%lld sum=%.6f\n", (long long)rc, ms(a, b),
           (long long)(out_offsets[1] - out_offsets[0]), sum);
    for (int64_t i = 0; i < R; i++) qk_circuit_free(out[i].circuit);
    for (int64_t t = 0; t < T; t++) qk_circuit_free(tasks[t].circuit);
    return 0;
}
