"""Replays tests/cases.json through libtwirl.dylib and compares with original.py's outputs.

Needs no qiskit: circuits are built with the Qiskit C API (libqiskit) through ctypes.
Run: python3 -I tests/check_codon.py   (exit code 0 iff every case matches)
TWIRL_FAST_PATH=0|1|2 selects twirl_set_fast_path's mode (off / on, the default / verify).
"""
import ctypes as C
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QISKIT_C = ROOT / "qiskit" / "dist" / "c"
TOL = 1e-12

ERRORS = {"args": 1, "shots": 2, "qubits_mismatch": 3, "unsupported_op": 4, "too_many_qubits": 5,
          "empty_result": 6, "symbolic_param": 7, "qiskit_version": 8}


def gate_values(qk):
    """Gate name -> QkGate, read back from libqiskit (independently of libtwirl's own table)."""
    text = (QISKIT_C / "include" / "qiskit" / "types.h").read_text()
    num_gates = max(int(v) for v in re.findall(r"QkGate_\w+ = (\d+)", text)) + 1
    names = {}
    for g in range(num_gates):
        nq, npar = qk.qk_gate_num_qubits(g), qk.qk_gate_num_params(g)
        c = qk.qk_circuit_new(nq, 0)
        qk.qk_circuit_gate(c, g, u32s(range(nq)), (C.c_double * max(1, npar))())
        if qk.qk_circuit_num_instructions(c) == 1:
            inst = Instruction()
            qk.qk_circuit_get_instruction(c, 0, C.byref(inst))
            names[inst.name.decode()] = g
            qk.qk_circuit_instruction_clear(C.byref(inst))
        qk.qk_circuit_free(c)
    return names


class Instruction(C.Structure):  # QkCircuitInstruction
    _fields_ = [("name", C.c_char_p), ("qubits", C.POINTER(C.c_uint32)),
                ("clbits", C.POINTER(C.c_uint32)), ("params", C.POINTER(C.c_void_p)),
                ("num_qubits", C.c_uint32), ("num_clbits", C.c_uint32), ("num_params", C.c_uint32)]


class TwirlTask(C.Structure):
    _fields_ = [("circuit", C.c_void_p), ("shots", C.c_int64)]


def load():
    qk = C.CDLL(str(QISKIT_C / "lib" / "libqiskit.dylib"))
    tw = C.CDLL(os.environ.get("TWIRL_LIB", str(ROOT / "libtwirl.dylib")))
    sig = {
        "qk_circuit_new": ([C.c_uint32, C.c_uint32], C.c_void_p),
        "qk_circuit_free": ([C.c_void_p], None),
        "qk_circuit_gate": ([C.c_void_p, C.c_uint8, C.POINTER(C.c_uint32), C.POINTER(C.c_double)], C.c_uint32),
        "qk_circuit_measure": ([C.c_void_p, C.c_uint32, C.c_uint32], C.c_uint32),
        "qk_circuit_barrier": ([C.c_void_p, C.POINTER(C.c_uint32), C.c_uint32], C.c_uint32),
        "qk_circuit_reset": ([C.c_void_p, C.c_uint32], C.c_uint32),
        "qk_param_from_double": ([C.c_double], C.c_void_p),
        "qk_param_as_real": ([C.c_void_p], C.c_double),
        "qk_param_free": ([C.c_void_p], None),
        "qk_circuit_set_global_phase": ([C.c_void_p, C.c_void_p], C.c_uint32),
        "qk_circuit_global_phase": ([C.c_void_p], C.c_void_p),
        "qk_circuit_num_clbits": ([C.c_void_p], C.c_uint32),
        "qk_circuit_num_instructions": ([C.c_void_p], C.c_size_t),
        "qk_circuit_get_instruction": ([C.c_void_p, C.c_size_t, C.POINTER(Instruction)], None),
        "qk_circuit_instruction_clear": ([C.POINTER(Instruction)], None),
        "qk_gate_num_qubits": ([C.c_uint8], C.c_uint32),
        "qk_gate_num_params": ([C.c_uint8], C.c_uint32),
        "qk_param_new_symbol": ([C.c_char_p], C.c_void_p),
        "qk_circuit_parameterized_gate": ([C.c_void_p, C.c_uint8, C.POINTER(C.c_uint32), C.POINTER(C.c_void_p)],
                                          C.c_uint32),
    }
    for name, (args, ret) in sig.items():
        f = getattr(qk, name)
        f.argtypes, f.restype = args, ret
    i64, p64 = C.c_int64, C.POINTER(C.c_int64)
    tw.twirl_preprocess.argtypes = [C.POINTER(TwirlTask), i64, i64, i64, C.POINTER(TwirlTask), C.POINTER(C.c_uint8)]
    tw.twirl_preprocess.restype = i64
    tw.twirl_postprocess.argtypes = [p64, p64, p64, i64, C.POINTER(C.c_uint8), i64, i64, p64,
                                     C.POINTER(C.c_double), p64]
    tw.twirl_postprocess.restype = i64
    tw.twirl_set_fast_path.argtypes = [i64]
    for name in ("twirl_set_fast_path", "twirl_fast_path_hits", "twirl_fast_path_mismatches"):
        getattr(tw, name).restype = i64
    return qk, tw


def u32s(xs):
    return (C.c_uint32 * max(1, len(xs)))(*xs)


def build(qk, gates, spec):
    c = qk.qk_circuit_new(spec["n"], spec["num_clbits"])
    phase = qk.qk_param_from_double(spec["phase"])
    qk.qk_circuit_set_global_phase(c, phase)
    qk.qk_param_free(phase)
    for o in spec["ops"]:
        if o["op"] == "measure":
            qk.qk_circuit_measure(c, o["q"][0], o["c"][0])
        elif o["op"] == "barrier":
            qk.qk_circuit_barrier(c, u32s(o["q"]), len(o["q"]))
        elif o["op"] == "reset":
            qk.qk_circuit_reset(c, o["q"][0])
        elif any(isinstance(x, str) for x in o["p"]):
            # A string param is an unbound symbol of that name.
            params = [qk.qk_param_new_symbol(x.encode()) if isinstance(x, str) else qk.qk_param_from_double(x)
                      for x in o["p"]]
            qk.qk_circuit_parameterized_gate(c, gates[o["op"]], u32s(o["q"]), (C.c_void_p * len(params))(*params))
            for x in params:
                qk.qk_param_free(x)
        else:
            params = (C.c_double * max(1, len(o["p"])))(*o["p"])
            qk.qk_circuit_gate(c, gates[o["op"]], u32s(o["q"]), params)
    return c


def dump(qk, c):
    phase = qk.qk_circuit_global_phase(c)
    out = {"num_clbits": qk.qk_circuit_num_clbits(c), "phase": qk.qk_param_as_real(phase), "ops": []}
    qk.qk_param_free(phase)
    for i in range(qk.qk_circuit_num_instructions(c)):
        inst = Instruction()
        qk.qk_circuit_get_instruction(c, i, C.byref(inst))
        out["ops"].append({
            "op": inst.name.decode(),
            "q": [inst.qubits[j] for j in range(inst.num_qubits)],
            "c": [inst.clbits[j] for j in range(inst.num_clbits)],
            "p": [qk.qk_param_as_real(inst.params[j]) for j in range(inst.num_params)],
        })
        qk.qk_circuit_instruction_clear(C.byref(inst))
    return out


def close(a, b):
    return len(a) == len(b) and all(abs(x - y) <= TOL for x, y in zip(a, b))


def diff_circuit(want, got):
    for key in ("num_clbits", "shots"):
        if want[key] != got[key]:
            return f"{key} {got[key]} != {want[key]}"
    if abs(want["phase"] - got["phase"]) > TOL:
        return f"phase {got['phase']} != {want['phase']}"
    if len(want["ops"]) != len(got["ops"]):
        return f"{len(got['ops'])} ops != {len(want['ops'])}"
    for i, (w, g) in enumerate(zip(want["ops"], got["ops"])):
        if (w["op"], w["q"], w["c"]) != (g["op"], g["q"], g["c"]) or not close(w["p"], g["p"]):
            return f"op {i}: {g} != {w}"
    return None


def rc_name(rc):
    names = {v: k for k, v in ERRORS.items()}
    return f"{rc} ({names.get(rc, 'ok' if rc == 0 else 'unknown')})"


def diff_merged(want, got):
    if [b for b, _ in got] != [b for b, _ in want]:
        missing = sorted(set(b for b, _ in want) - set(b for b, _ in got))
        extra = sorted(set(b for b, _ in got) - set(b for b, _ in want))
        return f"bitstrings differ: {len(got)} vs {len(want)} entries, missing {missing[:5]}, extra {extra[:5]}"
    for (b, pw), (_, pg) in zip(want, got):
        if abs(pw - pg) > TOL:
            return f"prob of {b:#x}: {pg} != {pw}"
    return None


def run_case(qk, tw, gates, case):
    """Returns None if libtwirl matches the expectation, else "field: what differs"."""
    want = case["expected"]
    k = case["num_instances"]
    n = case["tasks"][0]["circuit"]["n"] if case["tasks"] else 0
    inputs = [build(qk, gates, t["circuit"]) for t in case["tasks"]]
    T = len(inputs)
    tasks = (TwirlTask * T)(*[TwirlTask(c, t["shots"]) for c, t in zip(inputs, case["tasks"])])
    out = (TwirlTask * max(0, T * k))()
    flips = (C.c_uint8 * max(0, k * n))()
    rc = None
    try:
        rc = tw.twirl_preprocess(tasks, T, k, case["seed"], out, flips)
        if "error" in want:
            return None if rc == ERRORS[want["error"]] else f"preprocess rc {rc_name(rc)}, expected {want['error']}"
        if rc != 0:
            return f"preprocess rc {rc_name(rc)}, expected ok"
        got_flips = [[flips[j * n + q] for q in range(n)] for j in range(k)]
        if got_flips != want["flips"]:
            rows = [j for j, (g, w) in enumerate(zip(got_flips, want["flips"])) if g != w]
            return f"flips: rows {rows[:5]} differ, e.g. row {rows[0]}: {got_flips[rows[0]]} != {want['flips'][rows[0]]}"
        for i in range(T * k):
            problem = diff_circuit(want["twirled"][i], dict(dump(qk, out[i].circuit), shots=out[i].shots))
            if problem:
                return f"twirled[{i}] (task {i // k}, instance {i % k}): {problem}"
    finally:
        for c in inputs:
            qk.qk_circuit_free(c)
        for i in range(T * k if rc == 0 else 0):
            qk.qk_circuit_free(out[i].circuit)

    entries = [e for r in case["results"] for e in r]
    offsets = [0]
    for r in case["results"]:
        offsets.append(offsets[-1] + len(r))
    E = len(entries)
    out_bits, out_probs, out_offsets = (C.c_int64 * E)(), (C.c_double * E)(), (C.c_int64 * (T + 1))()
    rc = tw.twirl_postprocess((C.c_int64 * E)(*[b for b, _ in entries]), (C.c_int64 * E)(*[c for _, c in entries]),
                              (C.c_int64 * (T * k + 1))(*offsets), T, flips, k, n, out_bits, out_probs, out_offsets)
    if "postprocess_error" in want:
        expect = want["postprocess_error"]
        return None if rc == ERRORS[expect] else f"postprocess rc {rc_name(rc)}, expected {expect}"
    if rc != 0:
        return f"postprocess rc {rc_name(rc)}, expected ok"
    for t in range(T):
        got = sorted([out_bits[i], out_probs[i]] for i in range(out_offsets[t], out_offsets[t + 1]))
        problem = diff_merged(want["merged"][t], got)
        if problem:
            return f"merged[{t}]: {problem}"
    return None


def main():
    qk, tw = load()
    gates = gate_values(qk)
    mode = int(os.environ.get("TWIRL_FAST_PATH", "1"))
    if tw.twirl_set_fast_path(mode) < 0:
        sys.exit(f"bad TWIRL_FAST_PATH {mode}")
    cases = json.loads(Path(__file__).with_name("cases.json").read_text())
    only = set(int(x) for x in sys.argv[1:])  # optional case ids to run
    failures = 0
    for case in cases:
        if only and case["id"] not in only:
            continue
        problem = run_case(qk, tw, gates, case)
        if problem:
            failures += 1
            endings = ",".join(t["ending"] for t in case["tasks"]) or "no tasks"
            n = case["tasks"][0]["circuit"]["n"] if case["tasks"] else 0
            print(f"FAIL case {case['id']} (n={n}, k={case['num_instances']}, {endings}): {problem}")
    total = len(only) if only else len(cases)
    mismatches = tw.twirl_fast_path_mismatches()
    print(f"{total - failures}/{total} cases match original.py ({os.environ.get('TWIRL_LIB', 'libtwirl.dylib')}, "
          f"fast path mode {mode}: {tw.twirl_fast_path_hits()} circuits via fast path, {mismatches} mismatches)")
    sys.exit(1 if failures or mismatches else 0)


if __name__ == "__main__":
    main()
