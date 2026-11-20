// Twirls circuits that still have measurements (remove_final_measurements path) and prints
// every copy's instructions; probe/rfm_ref.py prints the same from original.py for a diff.
#include <stdio.h>
#include <stdint.h>
#include <qiskit.h>
#include "../twirl.h"

static void gate(QkCircuit *c, QkGate g, uint32_t a, int64_t b, const double *p) {
    uint32_t qs[2] = {a, (uint32_t)b};
    qk_circuit_gate(c, g, qs, p);
}

static QkCircuit *build(int variant) {
    QkCircuit *c = qk_circuit_new(3, 3);
    QkParam *ph = qk_param_from_double(0.5);
    qk_circuit_set_global_phase(c, ph);
    qk_param_free(ph);
    if (variant == 2) qk_circuit_reset(c, 2);
    double rz[1] = {0.3};
    gate(c, QkGate_H, 0, 0, NULL);
    gate(c, QkGate_CX, 0, 1, NULL);
    gate(c, QkGate_RZ, 2, 0, rz);
    qk_circuit_barrier(c, NULL, 0);
    gate(c, QkGate_CX, 1, 2, NULL);
    qk_circuit_measure(c, 0, 0);
    if (variant == 1) gate(c, QkGate_H, 0, 0, NULL);  // makes measure 0 non-final
    uint32_t b01[2] = {0, 1};
    qk_circuit_barrier(c, b01, 2);
    qk_circuit_measure(c, 1, 1);
    qk_circuit_measure(c, 2, 2);
    return c;
}

static void dump(const QkCircuit *c) {
    QkParam *ph = qk_circuit_global_phase(c);
    printf("  phase=%.3f clbits=%u\n", qk_param_as_real(ph), qk_circuit_num_clbits(c));
    qk_param_free(ph);
    for (size_t i = 0; i < qk_circuit_num_instructions(c); i++) {
        QkCircuitInstruction in;
        qk_circuit_get_instruction(c, i, &in);
        printf("  %s q=", in.name);
        for (uint32_t j = 0; j < in.num_qubits; j++) printf("%u,", in.qubits[j]);
        printf(" c=");
        for (uint32_t j = 0; j < in.num_clbits; j++) printf("%u,", in.clbits[j]);
        printf(" p=");
        for (uint32_t j = 0; j < in.num_params; j++) printf("%.3f,", qk_param_as_real(in.params[j]));
        printf("\n");
        qk_circuit_instruction_clear(&in);
    }
}

int main(void) {
    for (int variant = 0; variant < 3; variant++) {
        QkCircuit *qc = build(variant);
        TwirlTask tasks[1] = {{qc, 4000}}, out[4];
        uint8_t flips[4 * 3];
        int64_t rc = twirl_preprocess(tasks, 1, 4, 0, out, flips);
        printf("variant %d rc=%lld\n", variant, (long long)rc);
        if (rc == TWIRL_OK) {
            for (int j = 0; j < 4; j++) {
                printf(" copy %d shots=%lld\n", j, (long long)out[j].shots);
                dump(out[j].circuit);
                qk_circuit_free(out[j].circuit);
            }
        }
        qk_circuit_free(qc);
    }
    return 0;
}
