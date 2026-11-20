# Same circuits as probe/rfm.c, twirled by original.py, printed in rfm.c's format.
import sys
sys.path.insert(0, "/Users/slava.karkunov/Projects/Codon")
from qiskit import QuantumCircuit
from original import preprocess, State, Task


def build(variant):
    c = QuantumCircuit(3, 3, global_phase=0.5)
    if variant == 2:
        c.reset(2)
    c.h(0); c.cx(0, 1); c.rz(0.3, 2); c.barrier(); c.cx(1, 2); c.measure(0, 0)
    if variant == 1:
        c.h(0)
    c.barrier(0, 1); c.measure(1, 1); c.measure(2, 2)
    return c


for variant in range(3):
    tw, _, _ = preprocess([Task(build(variant), 4000)], State(num_instances=4, seed=0), {})
    # original.py does not reject variant 1; it keeps the non-final measure and its clbit.
    print(f"variant {variant} rc=0")
    for j, t in enumerate(tw):
        c = t.circuit
        print(f" copy {j} shots={t.shots}")
        print(f"  phase={float(c.global_phase):.3f} clbits={c.num_clbits}")
        for inst in c.data:
            q = "".join(f"{c.find_bit(b).index}," for b in inst.qubits)
            cl = "".join(f"{c.find_bit(b).index}," for b in inst.clbits)
            p = "".join(f"{float(x):.3f}," for x in inst.operation.params)
            print(f"  {inst.operation.name} q={q} c={cl} p={p}")
