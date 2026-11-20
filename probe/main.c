// Driver for libtwirl: builds a bare 5-qubit GHZ-like circuit in the Qiskit C API,
// runs twirl_preprocess (4 instances, seed 0) and prints each copy's op counts,
// then runs twirl_postprocess on a synthetic result and prints the merged distribution.
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <qiskit.h>
#include "../twirl.h"

int main(void) {
    const uint32_t n = 5;
    QkCircuit *qc = qk_circuit_new(n, 0);
    uint32_t q0 = 0;
    qk_circuit_gate(qc, QkGate_H, &q0, NULL);
    for (uint32_t q = 1; q < n; q++) {
        uint32_t qs[2] = {q - 1, q};
        qk_circuit_gate(qc, QkGate_CX, qs, NULL);
    }
    TwirlTask tasks[1] = {{qc, 4000}};
    const int64_t k = 4;
    TwirlTask out[4];
    uint8_t flips[4 * 5];
    int64_t rc = twirl_preprocess(tasks, 1, k, 0, out, flips);
    printf("preprocess rc=%lld\n", (long long)rc);
    for (int64_t j = 0; j < k; j++) {
        printf("flip[%lld] =", (long long)j);
        for (uint32_t q = 0; q < n; q++) printf(" %d", flips[j * n + q]);
        printf("  shots=%lld ops:", (long long)out[j].shots);
        QkOpCounts oc = qk_circuit_count_ops(out[j].circuit);
        for (size_t i = 0; i < oc.len; i++) printf(" %s=%zu", oc.data[i].name, oc.data[i].count);
        qk_opcounts_clear(&oc);
        printf("  clbits=%u\n", qk_circuit_num_clbits(out[j].circuit));
    }
    // Synthetic results: instance j saw bitstring (j ^ mask_j) 70 times and 0b11111 30 times.
    int64_t bits[8], counts[8], offsets[5] = {0, 2, 4, 6, 8};
    for (int64_t j = 0; j < k; j++) {
        bits[2 * j] = j; counts[2 * j] = 70;
        bits[2 * j + 1] = 31; counts[2 * j + 1] = 30;
    }
    int64_t out_bits[8], out_offsets[2];
    double out_probs[8];
    rc = twirl_postprocess(bits, counts, offsets, 1, flips, k, n, out_bits, out_probs, out_offsets);
    printf("postprocess rc=%lld entries=%lld\n", (long long)rc, (long long)out_offsets[1]);
    for (int64_t i = 0; i < out_offsets[1]; i++)
        printf("  %05lld -> %.4f\n", (long long)out_bits[i], out_probs[i]);
    for (int64_t j = 0; j < k; j++) qk_circuit_free(out[j].circuit);
    qk_circuit_free(qc);
    return 0;
}
