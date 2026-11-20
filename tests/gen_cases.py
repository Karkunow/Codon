"""Generates tests/cases.json: random inputs plus original.py's outputs on them.

Run with the venv that has qiskit: .venv/bin/python -I tests/gen_cases.py
tests/check_codon.py replays the same inputs through libtwirl.dylib and compares.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from original import State, Task, postprocess, preprocess  # noqa: E402

NUM_CASES = 150
MASTER_SEED = 20261120

# Python gate name -> (num_qubits, num_params). check_codon.py maps the names to QkGate.
GATES = {
    "h": (1, 0), "x": (1, 0), "y": (1, 0), "z": (1, 0), "s": (1, 0), "sdg": (1, 0),
    "t": (1, 0), "tdg": (1, 0), "sx": (1, 0), "p": (1, 1), "rx": (1, 1), "ry": (1, 1),
    "rz": (1, 1), "u": (1, 3), "cx": (2, 0), "cz": (2, 0), "swap": (2, 0), "cp": (2, 1),
    "crx": (2, 1), "rzz": (2, 1), "ccx": (3, 0),
}
# How each case's circuit ends. All of them leave every clbit idle after
# remove_final_measurements, the only shape twirl.codon accepts.
ENDINGS = ["measure_all", "permuted", "subset", "none", "barrier_only", "interleaved", "trailing_barrier"]


def random_body(rng, n):
    ops = []
    for _ in range(int(rng.integers(0, 41))):
        r = rng.random()
        if r < 0.08:
            k = int(rng.integers(1, n + 1))
            ops.append({"op": "barrier", "q": sorted(rng.choice(n, k, replace=False).tolist()), "c": [], "p": []})
        elif r < 0.12:
            ops.append({"op": "reset", "q": [int(rng.integers(n))], "c": [], "p": []})
        else:
            names = [g for g, (a, _) in GATES.items() if a <= n]
            name = names[int(rng.integers(len(names)))]
            arity, nparams = GATES[name]
            ops.append({
                "op": name,
                "q": rng.choice(n, arity, replace=False).tolist(),
                "c": [],
                "p": rng.uniform(-math.pi, math.pi, nparams).tolist(),
            })
    return ops


def measure(q, c):
    return {"op": "measure", "q": [q], "c": [c], "p": []}


def barrier(qs):
    return {"op": "barrier", "q": list(qs), "c": [], "p": []}


def random_circuit(rng, n, ending):
    ops = random_body(rng, n)
    num_clbits = 0
    if ending == "measure_all":
        num_clbits = n
        ops += [barrier(range(n))] + [measure(q, q) for q in range(n)]
    elif ending == "permuted":
        num_clbits = n
        perm = rng.permutation(n).tolist()
        ops += [measure(q, perm[q]) for q in range(n)]
    elif ending == "subset":
        num_clbits = n + int(rng.integers(0, 3))
        qs = rng.choice(n, int(rng.integers(1, n + 1)), replace=False).tolist()
        ops += [measure(q, i) for i, q in enumerate(qs)]
    elif ending == "barrier_only":
        ops += [barrier(range(n))]
    elif ending == "interleaved":
        num_clbits = n
        for q in range(n):
            ops.append(measure(q, q))
            if q + 1 < n and rng.random() < 0.5:
                ops.append(barrier(range(q, n)))
    elif ending == "trailing_barrier":
        num_clbits = n
        ops += [measure(q, q) for q in range(n)] + [barrier(range(n))]
    return {"n": n, "num_clbits": num_clbits, "phase": float(rng.uniform(-math.pi, math.pi)), "ops": ops}


def build(spec):
    qc = QuantumCircuit(spec["n"], spec["num_clbits"], global_phase=spec["phase"])
    for o in spec["ops"]:
        if o["op"] == "measure":
            qc.measure(o["q"][0], o["c"][0])
        elif o["op"] == "barrier":
            qc.barrier(*o["q"])
        elif o["op"] == "reset":
            qc.reset(o["q"][0])
        else:
            getattr(qc, o["op"])(*o["p"], *o["q"])
    return qc


def dump(qc):
    return {
        "num_clbits": qc.num_clbits,
        "phase": float(qc.global_phase),
        "ops": [{
            "op": inst.operation.name,
            "q": [qc.find_bit(b).index for b in inst.qubits],
            "c": [qc.find_bit(b).index for b in inst.clbits],
            "p": [float(x) for x in inst.operation.params],
        } for inst in qc.data],
    }


def random_counts(rng, n):
    keys = rng.choice(1 << n, int(rng.integers(1, min(30, 1 << n) + 1)), replace=False)
    return [[int(b), int(rng.integers(1, 101))] for b in keys]


def make_case(rng, i):
    n = int(rng.choice([1, 2, 3, 5, 8, 12, 20]))
    k = int(rng.choice([1, 2, 3, 4, 7]))
    seed = int(rng.integers(0, 2**31))
    num_tasks = int(rng.integers(1, 4))
    case = {"id": i, "num_instances": k, "seed": seed, "tasks": []}
    for _ in range(num_tasks):
        ending = ENDINGS[int(rng.integers(len(ENDINGS)))]
        case["tasks"].append({"circuit": random_circuit(rng, n, ending), "ending": ending,
                              "shots": int(rng.integers(k, 10001))})
    case["results"] = [random_counts(rng, n) for _ in range(num_tasks * k)]
    return case


def expected(case, error=None, postprocess_error=None):
    """original.py's outputs on the case.

    error / postprocess_error name the libtwirl error code check_codon.py must see from
    twirl_preprocess / twirl_postprocess. "original" records what original.py did on the same
    input, so a divergence is visible in cases.json instead of hidden behind the expected error.
    """
    out = {}
    try:
        tasks = [Task(build(t["circuit"]), t["shots"]) for t in case["tasks"]]
        state = State(num_instances=case["num_instances"], seed=case["seed"])
        twirled, state, ctx = preprocess(tasks, state, {})
        out["flips"] = ctx["flips"].astype(int).tolist()
        out["twirled"] = [dict(dump(t.circuit), shots=t.shots) for t in twirled]
        n = tasks[0].circuit.num_qubits
        results = [{format(b, f"0{n}b"): c for b, c in r} for r in case["results"]]
        merged, _, _ = postprocess(results, state, ctx)
        out["merged"] = [sorted([int(b, 2), p] for b, p in m.items()) for m in merged]
        original = "accepts"
    except Exception as e:  # noqa: BLE001 - every exception type is informative here
        original = f"raises {type(e).__name__}: {e}"
    if error:
        return {"error": error, "original": original}
    if postprocess_error:
        assert "twirled" in out, original
        return {"flips": out["flips"], "twirled": out["twirled"],
                "postprocess_error": postprocess_error, "original": original}
    assert "merged" in out, original
    return out


def op(name, *q, p=()):
    return {"op": name, "q": list(q), "c": [], "p": list(p)}


def circuit(n, num_clbits, ops, phase=0.0):
    return {"n": n, "num_clbits": num_clbits, "phase": phase, "ops": ops}


def task(spec, ending, shots=1000):
    return {"circuit": spec, "ending": ending, "shots": shots}


def case_of(ident, tasks, k=2, seed=7, results=None, **expected_kw):
    n = tasks[0]["circuit"]["n"] if tasks else 0
    if results is None:
        rng = np.random.default_rng(seed)
        results = [random_counts(rng, n) for _ in range(len(tasks) * k)]
    case = {"id": ident, "num_instances": k, "seed": seed, "tasks": tasks, "results": results}
    case["expected"] = expected(case, **expected_kw)
    return case


def shared_clbit_circuit(rng, n):
    """A barrier that is NOT final, followed by measures that share clbits.

    Qubit n-1 gets a gate after the barrier, so the barrier must stay. The measures on
    qubits 0..n-2 reuse clbits, so a final measure has an earlier measure as a predecessor
    over a clbit wire. Visiting that predecessor again (the `_shares_qubit` mutation) counts
    the barrier one more time than it has successors and wrongly removes it.
    """
    m = int(rng.integers(1, n - 1))  # number of clbits, fewer than measured qubits
    ops = random_body(rng, n) + [barrier(range(n))]
    order = rng.permutation(n - 1).tolist()
    ops += [measure(q, q % m) for q in order]
    ops.append(op("x", n - 1))
    return circuit(n, m, ops, phase=float(rng.uniform(-math.pi, math.pi)))


def random_bits(rng, n):
    return int("".join(str(b) for b in rng.integers(0, 2, size=n)), 2) if n else 0


def wide_counts(rng, n, entries):
    return [[random_bits(rng, n), int(rng.integers(1, 101))] for _ in range(entries)]


def extra_cases(first_id):
    rng = np.random.default_rng(MASTER_SEED + 1)
    cases = []
    ident = first_id

    def add(tasks, **kw):
        nonlocal ident
        cases.append(case_of(ident, tasks, **kw))
        ident += 1

    # --- clbit predecessors (kills the `_shares_qubit` mutation) ---
    add([task(circuit(3, 1, [barrier([0, 1, 2]), measure(0, 0), measure(1, 0), op("x", 2)]),
              "shared_clbit")])
    for _ in range(12):
        n = int(rng.choice([3, 4, 5, 8]))
        add([task(shared_clbit_circuit(rng, n), "shared_clbit", shots=int(rng.integers(3, 5000)))
             for _ in range(int(rng.integers(1, 3)))], k=int(rng.choice([1, 2, 3])),
            seed=int(rng.integers(0, 2**31)))
    # Two measures into one clbit that are all final: accepted by both sides.
    add([task(circuit(2, 1, [op("h", 0), measure(0, 0), measure(1, 0)]), "shared_clbit_final")])
    # A non-final measure reached only over a clbit wire: twirl.codon rejects it, original.py keeps it.
    add([task(circuit(2, 1, [measure(0, 0), op("x", 0), measure(1, 0)]), "non_final_measure")],
        results=[], error="unsupported_op")

    # --- error codes 1, 3, 5, 6 ---
    add([], k=2, results=[], error="args")                                        # no tasks
    add([task(circuit(2, 0, [op("h", 0)]), "none")], k=0, results=[], error="args")
    add([task(circuit(2, 0, [op("h", 0)]), "none")], k=-1, results=[], error="args")
    add([task(circuit(2, 0, [op("h", 0)]), "none"), task(circuit(3, 0, []), "none")],
        results=[], error="qubits_mismatch")                                     # second wider
    add([task(circuit(3, 0, [op("h", 0)]), "none"), task(circuit(2, 0, []), "none")],
        results=[], error="qubits_mismatch")                                     # second narrower
    add([task(circuit(64, 64, [op("h", 63)] + [measure(q, q) for q in range(64)]), "permuted")],
        results=[], error="too_many_qubits")
    add([task(circuit(2, 0, [op("h", 0)]), "none")], k=2,
        results=[[[0, 3], [1, 5]], []], postprocess_error="empty_result")        # no entries
    add([task(circuit(2, 0, [op("h", 0)]), "none")], k=2,
        results=[[[0, 3], [1, 5]], [[2, 0]]], postprocess_error="empty_result")  # zero counts
    add([task(circuit(2, 0, []), "none"), task(circuit(2, 0, []), "none")], k=1,
        results=[[[0, 3]], [[1, 0], [2, 0]]], postprocess_error="empty_result")  # in task 2

    # --- 63 qubits: postprocess masks and bit packing up to bit 62 ---
    for k in (1, 2, 5):
        n = 63
        spec = circuit(n, n, [op("h", q) for q in range(n)] + [measure(q, q) for q in range(n)])
        add([task(spec, "permuted")], k=k, seed=int(rng.integers(0, 2**31)),
            results=[wide_counts(rng, n, int(rng.integers(1, 6))) for _ in range(k)])
    # n = 62, 33, 32, 31 too: masks around the int32 boundary and the top usable bit
    for n in (62, 33, 32, 31):
        spec = circuit(n, 0, [op("x", n - 1)])
        add([task(spec, "none")], k=3, seed=int(rng.integers(0, 2**31)),
            results=[wide_counts(rng, n, 4) for _ in range(3)])

    # --- num_instances = 1 and large ---
    add([task(circuit(4, 4, [op("h", 0), op("cx", 0, 1)] + [barrier(range(4))] + [measure(q, q) for q in range(4)]),
              "measure_all", shots=1)], k=1)
    add([task(circuit(3, 3, [op("h", 1)] + [measure(q, q) for q in range(3)]), "permuted", shots=70)], k=64)
    add([task(circuit(2, 0, [op("h", 1)]), "none", shots=129)], k=129,
        results=[[[int(rng.integers(4)), 1]] for _ in range(129)])

    # --- RNG parity of default_rng(seed).integers(0, 2, size=(k, n)) over seeds and shapes ---
    seeds = [0, 1, 2**31 - 1, 2**31, 2**32 - 1, 2**32, 2**40 + 3, 2**62, 2**63 - 1]
    seeds += [int(s) for s in rng.integers(0, 2**63 - 1, size=20, dtype=np.int64)]
    shapes = [(1, 1), (1, 63), (2, 32), (5, 33), (16, 7), (33, 9), (64, 2), (33, 31)]
    for i, seed in enumerate(seeds):
        k, n = shapes[i % len(shapes)]
        add([task(circuit(n, 0, []), "none", shots=k)], k=k, seed=seed,
            results=[[[0, 1]] for _ in range(k)])

    # --- endings mixed in one call, empty circuits, extreme params ---
    add([task(circuit(3, 3, [barrier(range(3))] + [measure(q, q) for q in range(3)]), "measure_all"),
         task(circuit(3, 0, []), "none"),
         task(circuit(3, 3, [measure(q, q) for q in range(3)] + [barrier(range(3))]), "trailing_barrier"),
         task(circuit(3, 1, [barrier(range(3)), measure(0, 0), measure(1, 0), op("x", 2)]), "shared_clbit"),
         task(circuit(3, 0, [barrier(range(3))]), "barrier_only")], k=3)
    add([task(circuit(1, 0, []), "none")], k=2)
    add([task(circuit(5, 0, []), "none"), task(circuit(5, 5, [measure(q, q) for q in range(5)]), "permuted")], k=1)
    add([task(circuit(1, 1, [measure(0, 0)]), "permuted")], k=1)
    add([task(circuit(2, 0, [op("rx", 0, p=[1e300]), op("p", 1, p=[-0.0]), op("u", 0, p=[1e-300, -1e300, 5e-324]),
                             op("rzz", 0, 1, p=[-1e-310]), op("cp", 1, 0, p=[6.283185307179586 * 1e15]),
                             op("ry", 1, p=[0.0])]), "none")], k=2)
    return cases


def main():
    rng = np.random.default_rng(MASTER_SEED)
    cases = []
    for i in range(NUM_CASES):
        case = make_case(rng, i)
        case["expected"] = expected(case)
        cases.append(case)
    # Error case: shots below num_instances (original.py raises ValueError).
    case = make_case(rng, NUM_CASES)
    case["num_instances"] = 4
    case["tasks"][0]["shots"] = 3
    case["results"] = []
    case["expected"] = expected(case, error="shots")
    cases.append(case)
    # Known divergence: a non-final measure. original.py keeps it; twirl.codon rejects it.
    spec = {"n": 2, "num_clbits": 2, "phase": 0.0,
            "ops": [{"op": "h", "q": [0], "c": [], "p": []}, measure(0, 0),
                    {"op": "x", "q": [0], "c": [], "p": []}, measure(1, 1)]}
    cases.append({"id": NUM_CASES + 1, "num_instances": 2, "seed": 1, "results": [],
                  "tasks": [{"circuit": spec, "ending": "non_final_measure", "shots": 100}],
                  "expected": {"error": "unsupported_op", "original": "accepts"}})
    cases += extra_cases(NUM_CASES + 2)
    out = Path(__file__).with_name("cases.json")
    out.write_text(json.dumps(cases, separators=(",", ":")))
    print(f"wrote {len(cases)} cases to {out}")


if __name__ == "__main__":
    main()
