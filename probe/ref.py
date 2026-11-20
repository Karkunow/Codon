import sys
sys.path.insert(0, "/Users/slava.karkunov/Projects/Codon")
from qiskit import QuantumCircuit
from original import preprocess, postprocess, State, Task
n, k = 5, 4
qc = QuantumCircuit(n); qc.h(0)
for q in range(1, n): qc.cx(q - 1, q)
qc.measure_all()
tw, st, ctx = preprocess([Task(qc, 4000)], State(num_instances=k, seed=0), {})
for j, t in enumerate(tw):
    print(f"flip[{j}] = {' '.join(map(str, ctx['flips'][j]))}  shots={t.shots} ops: {dict(t.circuit.count_ops())}  clbits={t.circuit.num_clbits}")
results = [{format(j, f"0{n}b"): 70, format(31, f"0{n}b"): 30} for j in range(k)]
merged, st, ctx = postprocess(results, st, ctx)
print("entries", len(merged[0]))
for b, p in sorted(merged[0].items()): print(f"  {b} -> {p:.4f}")
