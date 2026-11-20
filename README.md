# Codon twirl

Measurement twirling (`original.py`, Python + Qiskit) переписаний на [Codon](https://github.com/exaloop/codon) і зібраний у нативну бібліотеку `libtwirl.dylib`. Схеми будуються через Qiskit C API (`libqiskit`).

- `original.py` — еталонна Python-версія.
- `twirl.codon` — порт; `twirl.h` — C-інтерфейс бібліотеки.
- `build.sh` — клонує Qiskit, збирає `libqiskit` (`make c`, Rust ≥ 1.91) і `libtwirl.dylib` (потрібен Codon у `~/.codon`).
- `research.md` — дослідження: чи можна, якими шляхами, швидкість, обмеження.
- `probe/` — драйвери й бенчмарки.

Обмеження порту: некінцеві вимірювання та операції, крім gate/barrier/reset, повертають код помилки 4; символьні параметри гейтів не підтримуються.
