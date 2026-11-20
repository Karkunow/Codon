import sys, time
sys.path.insert(0, "/Users/slava.karkunov/Projects/Codon")
import numpy as np
from qiskit import QuantumCircuit
from original import preprocess, postprocess, State, Task

def build(n):
    qc = QuantumCircuit(n); qc.h(0)
    for q in range(1, n): qc.cx(q - 1, q)
    qc.measure_all(); return qc

t0 = time.perf_counter()
qc = build(5); bare = qc.remove_final_measurements(inplace=False); c = bare.copy(); c.x(2); c.measure_all()
print("cpython build+copy ms", (time.perf_counter() - t0) * 1000)

n, T = 20, 10
tasks = [Task(build(n), 4000) for _ in range(T)]
st = State(num_instances=4, seed=0)
t0 = time.perf_counter()
tw, st, ctx = preprocess(tasks, st, {})
t1 = time.perf_counter()
rng = np.random.default_rng(1)
results = []
for task in tw:
    keys = rng.integers(0, 1 << n, size=50)
    results.append({format(int(k), f"0{n}b"): 20 for k in keys})
t2 = time.perf_counter()
merged, st, ctx = postprocess(results, st, ctx)
t3 = time.perf_counter()
print(f"preprocess {T} tasks x4, n={n}: {(t1-t0)*1000:.1f} ms; postprocess {len(results)} results x50 keys: {(t3-t2)*1000:.1f} ms")
print("flips[0]", ctx["flips"][0].tolist(), "merged[0] size", len(merged[0]), "sum", round(sum(merged[0].values()), 6))
