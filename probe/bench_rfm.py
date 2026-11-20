# Median of 50 runs of original.py on the same sizes as probe/bench_rfm.c.
import statistics, sys, time
sys.path.insert(0, "/Users/slava.karkunov/Projects/Codon")
import numpy as np
from qiskit import QuantumCircuit
from original import preprocess, postprocess, State, Task

n, T, RUNS = 20, 10, 50


def build():
    qc = QuantumCircuit(n); qc.h(0)
    for q in range(1, n):
        qc.cx(q - 1, q)
    qc.measure_all()
    return qc


tasks = [Task(build(), 4000) for _ in range(T)]
pre, post = [], []
for _ in range(RUNS):
    t0 = time.perf_counter()
    tw, st, ctx = preprocess(tasks, State(num_instances=4, seed=0), {})
    pre.append((time.perf_counter() - t0) * 1000)
    rng = np.random.default_rng(1)
    results = [{format(int(k), f"0{n}b"): 20 for k in rng.integers(0, 1 << n, size=50)} for _ in tw]
    t0 = time.perf_counter()
    postprocess(results, st, ctx)
    post.append((time.perf_counter() - t0) * 1000)
print(f"python: preprocess median {statistics.median(pre):.3f} ms (min {min(pre):.3f}); "
      f"postprocess median {statistics.median(post):.3f} ms (min {min(post):.3f})")
