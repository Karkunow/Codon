#!/bin/bash
# Builds libqiskit (Qiskit C API) and libtwirl.dylib. Needs Rust >= 1.91 and Codon.
set -euo pipefail
cd "$(dirname "$0")"

QISKIT=${QISKIT:-$PWD/qiskit}
[ -d "$QISKIT" ] || git clone --depth 1 https://github.com/Qiskit/qiskit.git "$QISKIT"
make -C "$QISKIT" c  # -> dist/c/include/qiskit.h, dist/c/lib/libqiskit.dylib

LIB=$QISKIT/dist/c/lib
codon build -release --relocation-model=pic --lib -o libtwirl.dylib \
    --linker-flags="-L$LIB -lqiskit -Wl,-rpath,$LIB" \
    twirl.codon

# C++ caller: c++ main.cpp -I. -I$QISKIT/dist/c/include -L. -ltwirl -L$LIB -lqiskit -Wl,-rpath,$PWD -Wl,-rpath,$LIB
