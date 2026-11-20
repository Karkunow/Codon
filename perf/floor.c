// Theoretical floor: the same libqiskit calls twirl_preprocess makes, in plain C, with no
// Codon-side bookkeeping. Also times the pieces (to_dag, rebuild, copy+X+measure_all).
// Usage: floor [n T k depth RUNS]
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
#include <qiskit.h>

static double ms(struct timespec a, struct timespec b) {
    return (b.tv_sec - a.tv_sec) * 1e3 + (b.tv_nsec - a.tv_nsec) / 1e6;
}
static int cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}
#define NOW(v) clock_gettime(CLOCK_MONOTONIC, &v)

int main(int argc, char **argv) {
    const uint32_t n = argc > 1 ? atoi(argv[1]) : 20;
    const int T = argc > 2 ? atoi(argv[2]) : 10;
    const int k = argc > 3 ? atoi(argv[3]) : 4;
    const int depth = argc > 4 ? atoi(argv[4]) : 1;
    const int RUNS = argc > 5 ? atoi(argv[5]) : 50;
    QkCircuit **tasks = calloc(T, sizeof *tasks);
    for (int t = 0; t < T; t++) {
        QkCircuit *qc = qk_circuit_new(n, n);
        uint32_t q0 = 0;
        qk_circuit_gate(qc, QkGate_H, &q0, NULL);
        for (int d = 0; d < depth; d++)
            for (uint32_t q = 1; q < n; q++) { uint32_t qs[2] = {q - 1, q}; qk_circuit_gate(qc, QkGate_CX, qs, NULL); }
        qk_circuit_barrier(qc, NULL, 0);
        for (uint32_t q = 0; q < n; q++) qk_circuit_measure(qc, q, q);
        tasks[t] = qc;
    }
    double *tot = calloc(RUNS, 8), *dag = calloc(RUNS, 8), *rebuild = calloc(RUNS, 8), *copies = calloc(RUNS, 8);
    double *tail = calloc(RUNS, 8);
    struct timespec a, b, c, d, e;
    for (int run = 0; run < RUNS; run++) {
        double td = 0, tr = 0, tc = 0, tm = 0;
        NOW(a);
        for (int t = 0; t < T; t++) {
            NOW(b);
            QkDag *g = qk_circuit_to_dag(tasks[t]);
            NOW(c);
            size_t num = qk_dag_num_op_nodes(g);
            uint32_t *order = malloc(num * 4);
            qk_dag_topological_op_nodes(g, order);
            QkCircuit *bare = qk_circuit_new(n, 0);
            double params[4];
            for (size_t i = 0; i < num; i++) {
                uint32_t node = order[i];
                QkOperationKind kind = qk_dag_op_node_kind(g, node);
                if (kind != QkOperationKind_Gate) continue;  // final barrier + measures skipped
                QkGate gate = qk_dag_op_node_gate_op(g, node, params);
                qk_circuit_gate(bare, gate, (uint32_t *)qk_dag_op_node_qubits(g, node), params);
            }
            free(order);
            qk_dag_free(g);
            NOW(d);
            for (int j = 0; j < k; j++) {
                QkCircuit *cp = qk_circuit_copy(bare);
                for (uint32_t q = 0; q < n; q += 2) { uint32_t qq = q; qk_circuit_gate(cp, QkGate_X, &qq, NULL); }
                QkClassicalRegister *reg = qk_classical_register_new(n, "meas");
                qk_circuit_add_classical_register(cp, reg);
                qk_classical_register_free(reg);
                qk_circuit_barrier(cp, NULL, 0);
                for (uint32_t q = 0; q < n; q++) qk_circuit_measure(cp, q, q);
                qk_circuit_free(cp);
            }
            NOW(e);
            qk_circuit_free(bare);
            td += ms(b, c); tr += ms(c, d); tc += ms(d, e);
        }
        NOW(b);
        tot[run] = ms(a, b); dag[run] = td; rebuild[run] = tr; copies[run] = tc;
    }
    // Component: one measure_all tail on an n-qubit circuit (k*T times), to split copies.
    for (int run = 0; run < RUNS; run++) {
        double tm = 0;
        for (int t = 0; t < T; t++) for (int j = 0; j < k; j++) {
            QkCircuit *cp = qk_circuit_new(n, 0);
            NOW(a);
            QkClassicalRegister *reg = qk_classical_register_new(n, "meas");
            qk_circuit_add_classical_register(cp, reg);
            qk_classical_register_free(reg);
            qk_circuit_barrier(cp, NULL, 0);
            for (uint32_t q = 0; q < n; q++) qk_circuit_measure(cp, q, q);
            NOW(b);
            qk_circuit_free(cp);
            tm += ms(a, b);
        }
        tail[run] = tm;
    }
    qsort(tot, RUNS, 8, cmp); qsort(dag, RUNS, 8, cmp); qsort(rebuild, RUNS, 8, cmp); qsort(copies, RUNS, 8, cmp);
    qsort(tail, RUNS, 8, cmp);
    printf("floor(C) n=%u T=%d k=%d d=%d: total med %.3f min %.3f | to_dag %.3f | rebuild %.3f | copy+X+meas_all %.3f | meas_all tail alone %.3f\n",
           n, T, k, depth, tot[RUNS / 2], tot[0], dag[RUNS / 2], rebuild[RUNS / 2], copies[RUNS / 2], tail[RUNS / 2]);
    return 0;
}
