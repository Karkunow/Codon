# codon_twirl — стан проєкту (для наступних сесій)

Записано 2026-11-20. Репозиторій: https://github.com/Karkunow/codon_twirl (публічний; перейменовано з `Karkunow/Codon`). Локальна тека: `~/Projects/Codon`.

## Що це і навіщо

`original.py` — measurement twirling на Python + Qiskit (`preprocess`: k копій схеми з випадковими X перед вимірюванням; `postprocess`: перевернути біти назад і злити в ймовірності). Мета Слави: мати це як нативний машинний код (бібліотеку) без інтерпретатора Python і довести, що результат ідентичний. Проєкт показували Юрі (імейл відправлено 2026-11-20).

Важливо (перевірено дослідженням, `docs/research.md` розділ 3): pre/postprocess виконуються на хості до відправки й після результатів, а не у вікні когерентності; на декогеренцію прискорення не впливає. Слава попросив не писати це в TL;DR.

## Поточний стан

- `twirl.codon` → `libtwirl.dylib` (Codon 0.20.7, `~/.codon`), C-інтерфейс у `twirl.h`: `twirl_preprocess`, `twirl_postprocess`, `twirl_set_fast_path`, `twirl_fast_path_hits`, `twirl_fast_path_mismatches`. Схеми — `QkCircuit*` з Qiskit C API (`libqiskit`, зібраний з клону `qiskit/`, коміт 30577bf, версія 2.7.0-dev).
- Тести: `tests/gen_cases.py` (venv: qiskit 2.6.2, numpy 2.5.5) пише `tests/cases.json` (234 випадки) з виходів `original.py`; `tests/check_codon.py` (без qiskit, через ctypes) порівнює. Останній прогін: 234/234 у всіх трьох режимах швидкого шляху (0/1/2). Кожен захист перевірено мутантами (`tests/mutants/`, у git не йде; таблиця в `docs/tests.md`).
- Швидкість (`README.md`, таблиця на задачу): `preprocess` у 15–31 раз швидший за Python, `postprocess` ~17×; швидкий шлях ~2× відносно першої версії.
- Документи: `docs/research.md`, `docs/performance.md`, `docs/alternatives.md`, `docs/tests.md`; README має TL;DR.

## Ключові рішення

- **Codon, а не інші компілятори:** Cython/mypyc/Nuitka/Numba тощо потребують CPython у рантаймі; Codon дає `.dylib` без інтерпретатора, `from C import` до libqiskit і побітовий паритет `np.random.default_rng` (перевірено на 29 seed'ах). Єдина серйозна альтернатива — Rust поверх ядра Qiskit (або C/C++ через `qiskit.h`), `docs/alternatives.md`.
- **`from python import qiskit` відкинуто:** Qiskit тоді працює в CPython, прискорення немає.
- **`remove_final_measurements`** у C API немає → порт `calc_final_ops` на DAG-функціях + **швидкий шлях** без DAG для схем «гейти/reset, потім лише measure/barrier». Перемикач `twirl_set_fast_path(0 off | 1 on, типово | 2 verify)`.
- Захисти швидкого шляху (рішення Слави: «мітигуй всі ризики B»): таблиця «назва → QkGate» будується з завантаженої libqiskit; `qk_api_version()` звіряється з версією заголовка (`qk_build.codon`, генерує `build.sh`) → код 8; непідставлені параметри відсікаються до обох шляхів → код 7; операції без кубітів (global_phase) → DAG.
- Свідомі розбіжності з `original.py`: вимірювання посеред схеми → код 4; непідставлений параметр (кут гейта — змінна `Parameter("θ")`) → код 7; k < 1, різна ширина задач, n > 63, порожній результат → коди 1/3/5/6.
- Межа `@export`: лише скаляри й вказівники; списки → вказівник + довжина; `context` → масив `flips`; винятки замінено кодами (виняток в `@export` аварійно завершує процес).

## Відкрите / наступні кроки

- Чому в Codon час на задачу при 100 задачах вищий, ніж при 10 (40 проти 33 мкс) — не перевірено.
- Перенесення на іншу машину: `build.sh` прописує libqiskit через `@rpath`, але `libtwirl` ще залежить від `libcodonrt`/`libomp` з Codon, а `libqiskit` — від libpython 3.12 (`otool -L`; Qiskit планує прибрати у 2.7). На чужому Mac треба перезбирати.
- venv-qiskit (2.6.2) і libqiskit (2.7.0-dev) — різні версії; тести проходять, але після оновлення Qiskit перегенерувати `cases.json` тією ж версією й прогнати `build.sh`.
- Можливий план Б: прототип на Rust (`docs/alternatives.md`, ~1 день, потрібен порт PCG64 + SeedSequence + Lemire).

## Як запускати

```bash
./build.sh                       # клон Qiskit + make c (~5 хв, Rust ≥ 1.91) + libtwirl.dylib + тести у 3 режимах
SKIP_QISKIT=1 ./build.sh         # без перезбірки libqiskit
python3 -m venv .venv && .venv/bin/pip install qiskit numpy
.venv/bin/python -I tests/gen_cases.py                  # еталон з original.py
TWIRL_FAST_PATH=2 python3 -I tests/check_codon.py       # 0/1/2; TWIRL_LIB=<dylib> — інша бібліотека; аргументи — id кейсів
L=$PWD/qiskit/dist/c; cc -O2 perf/bench.c -I$L/include -L$L/lib -lqiskit -Wl,-rpath,$L/lib -o perf/bench
./perf/bench $PWD/libtwirl.dylib 20 10 4 1 50 50       # абсолютний шлях до dylib; n T k depth K RUNS
.venv/bin/python -I probe/bench_rfm.py 20 10            # Python-бенчмарк: n T
```

У zsh розмір передавати окремими аргументами (`${=size}`), інакше він стає одним аргументом. Мутант збирається поруч із копією `qk_build.codon`.

Не в git: `qiskit/` (1,3 ГБ), `.venv/`, `*.dylib`, `qk_build.codon`, скомпільовані проби, `tests/mutants/`, `dl/` (інсталятор Codon). Секретів у проєкті немає.
