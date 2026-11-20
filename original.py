from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit


@dataclass(frozen=True)
class State:
    num_instances: int = 4
    seed: int = 0


@dataclass(frozen=True)
class Task:
    circuit: QuantumCircuit
    shots: int


def preprocess(tasks: list[Task], state: State, context: dict) -> tuple[list[Task], State, dict]:
    n = tasks[0].circuit.num_qubits
    # flips[j, q] == 1 puts an X on qubit q right before measurement in copy j.
    flips = np.random.default_rng(state.seed).integers(0, 2, size=(state.num_instances, n))
    twirled = []
    for task in tasks:
        if task.shots < state.num_instances:
            raise ValueError(f"{task.shots} shots cannot be split over {state.num_instances} instances")
        bare = task.circuit.remove_final_measurements(inplace=False)
        for flip in flips:
            circuit = bare.copy()
            for q in np.flatnonzero(flip):
                circuit.x(int(q))
            circuit.measure_all()
            twirled.append(Task(circuit, task.shots // state.num_instances))
    context["flips"] = flips
    context["num_tasks"] = len(tasks)
    return twirled, state, context


def postprocess(results: list[dict[str, int]], state: State, context: dict) -> tuple[list[dict[str, float]], State, dict]:
    flips = context["flips"]
    k, n = flips.shape
    # Qiskit bitstrings are little-endian: qubit q is bit q of int(bits, 2).
    masks = flips @ (1 << np.arange(n))
    merged = []
    for t in range(context["num_tasks"]):
        probs: dict[str, float] = {}
        for counts, mask in zip(results[t * k:(t + 1) * k], masks):
            shots = sum(counts.values())
            for bits, c in counts.items():
                unflipped = format(int(bits, 2) ^ int(mask), f"0{n}b")
                probs[unflipped] = probs.get(unflipped, 0.0) + c / shots / k
        merged.append(probs)
    return merged, state, context
