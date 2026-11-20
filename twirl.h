// C/C++ interface of libtwirl (built from twirl.codon). Codon `int` is int64_t.
#pragma once
#include <stdint.h>
#include <qiskit.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    TWIRL_OK = 0,
    TWIRL_ERR_ARGS = 1,
    TWIRL_ERR_SHOTS = 2,
    TWIRL_ERR_QUBITS_MISMATCH = 3,
    TWIRL_ERR_UNSUPPORTED_OP = 4,  // non-final measure, or an op other than gate/barrier/reset
    TWIRL_ERR_TOO_MANY_QUBITS = 5,
    TWIRL_ERR_EMPTY_RESULT = 6,
    TWIRL_ERR_SYMBOLIC_PARAM = 7,  // a gate parameter is not a bound real number
    TWIRL_ERR_QISKIT_VERSION = 8,  // loaded libqiskit differs from the qiskit.h libtwirl was built with
};

// Fast path of remove_final_measurements (no DAG) for circuits that are gates/resets followed by a
// tail of measures/barriers; any other circuit takes the DAG port. Not thread-safe to switch.
enum {
    TWIRL_FAST_PATH_OFF = 0,     // always the DAG port
    TWIRL_FAST_PATH_ON = 1,      // default
    TWIRL_FAST_PATH_VERIFY = 2,  // run both, use the DAG result on a mismatch and count it
};
// Returns the previous mode, or -1 for an invalid one.
int64_t twirl_set_fast_path(int64_t mode);
// Counters since the library was loaded.
int64_t twirl_fast_path_hits(void);
int64_t twirl_fast_path_mismatches(void);

typedef struct {
    QkCircuit *circuit;
    int64_t shots;
} TwirlTask;

// out_tasks: num_tasks * num_instances; out_flips: num_instances * num_qubits.
// Final measurements and barriers are removed first. Free each out_tasks[i].circuit with qk_circuit_free.
int64_t twirl_preprocess(const TwirlTask *tasks, int64_t num_tasks, int64_t num_instances,
                         int64_t seed, TwirlTask *out_tasks, uint8_t *out_flips);

// Result r = t * num_instances + j holds entries [offsets[r], offsets[r + 1]).
// bits: qubit q is bit q. out_bits/out_probs: offsets[num_tasks * num_instances] slots;
// out_offsets: num_tasks + 1.
int64_t twirl_postprocess(const int64_t *bits, const int64_t *counts, const int64_t *offsets,
                          int64_t num_tasks, const uint8_t *flips, int64_t num_instances,
                          int64_t num_qubits, int64_t *out_bits, double *out_probs,
                          int64_t *out_offsets);

#ifdef __cplusplus
}
#endif
