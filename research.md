# Codon + Qiskit для measurement twirling: дослідження (2026-11-20, 17:04–17:15 WET)

## Вердикт

- Так, `twirl.codon` компілюється Codon 0.20.7 у нативну `libtwirl.dylib` і дає ті самі результати, що `original.py` (фліпи, лічильники гейтів, 7 злитих ймовірностей збігаються). Потрібна була одна правка: `@tupleclass` → `@tuple`.
- Qiskit справді має C API (crate `crates/cext`, 370 функцій у `funcs.h`), але він «експериментальний, може змінюватись між мінорними версіями» і не має `remove_final_measurements` / `measure_all`; `measure_all` відтворено вручну, видалення вимірів лишилось на стороні викликача.
- Швидкість: на 10 задач × 4 копії × 20 кубітів preprocess 0,5–2,1 мс (C) проти 7,6 мс (CPython); postprocess 0,08 мс проти 0,9 мс. Це мілісекунди в обох випадках.
- Мотивація «машинний код, щоб встигнути до декогеренції» не підтверджується: preprocess і postprocess виконуються на класичному хості до відправлення задачі та після повернення результатів, не у вікні когерентності. У вікні когерентності працює лише логіка, вшита в саму схему (dynamic circuits: `if`, латентність ≈600 нс) на контрольній електроніці IBM, і Codon на хості туди не потрапляє.

## 1. Чи має Qiskit C API, наскільки він повний і стабільний

Доказ (клон `github.com/Qiskit/qiskit`, коміт `30577bfddf0b…`, 2026-11-19, версія `2.7.0-dev` у `Cargo.toml:6`, у `/Users/slava.karkunov/Projects/Codon/qiskit`):

- Crate `crates/cext/` (`README.md`: «This crate contains the bindings for Qiskit's C API»). Файли: `src/circuit.rs`, `dag.rs`, `sparse_observable.rs`, `transpiler/`, `passmanager/`, `qpy.rs`, `py.rs`, `control_flow.rs`, `classical_expr.rs` тощо.
- Збірка: `make c` (Makefile:160 `c: cheader clib`; `cheader` = `cargo run -p qiskit-bindgen-cli -- install -c crates/cext -o dist/c/include`; `clib` = `cargo rustc -p qiskit-cext --crate-type cdylib --release` → `dist/c/lib/libqiskit.dylib`). Збірка на M1 Pro тривала ~5 хв (17:05→17:10), результат 10,8 МБ, `nm -gU` дає 351 символ `_qk_*`. Заголовок тепер розбитий: `dist/c/include/qiskit.h` підключає `qiskit/types.h`, `qiskit/funcs.h` (370 оголошень `qk_*`).
- Функції, що використав `twirl.codon`, є: `qk_circuit_copy` (circuit.rs:668), `qk_circuit_num_qubits` (:690), `qk_circuit_num_clbits` (:714), `qk_circuit_gate(circuit, StandardGate, *u32, *f64)` (:889), `qk_circuit_measure(circuit, qubit, clbit)` (:1053), `qk_circuit_barrier(circuit, *u32 або NULL, n)` (:1129, NULL = усі кубіти), `qk_classical_register_new(n, name)` (:284), `qk_circuit_add_classical_register` (:562), `qk_circuit_count_ops` (:1461), `qk_circuit_num_instructions` (:1499). `StandardGate::X = 3`, `#[repr(u8)]` (`crates/circuit/src/standard_gate/mod.rs:40,49`; у заголовку `QkGate_X = 3`, `types.h:160`).
- Чого немає: `grep -i 'remove_final\|measure_all' funcs.h` порожній. Python-версія `measure_all` (`qiskit/circuit/quantumcircuit.py:4760`) робить `_create_creg(num_qubits, "meas")`, `add_register`, `barrier()`, `measure(qubits, creg)`; `_measure_all` у `twirl.codon` повторює саме це, і лічильники гейтів/клбітів збіглись із Python.
- Python-міст: `qk_circuit_borrow_from_python` (circuit.rs:2217), `qk_circuit_to_python` (:2140) під `#[cfg(feature = "python_binding")]`. `make c` цю фічу не вмикає (Makefile передає лише `--features=global_mimalloc`), тож у зібраній `libqiskit.dylib` їх немає (`nm | grep -i python` → 0). Зате вони є в колесі: `.venv/.../qiskit/_accelerate.abi3.so` експортує 351 `_qk_*` разом із `_qk_circuit_borrow_from_python`, `_qk_circuit_to_python`, а заголовки лежать у `.venv/.../qiskit/capi/include/qiskit.h` (`crates/pyext/Cargo.toml:49` вмикає `python_binding`).
- Стабільність: `docs/cdoc/index.rst:21-22`: «As this interface is still new in Qiskit it should be considered experimental and the interface might change between minor version releases». Додатково функції з `*const CircuitData`/`panic` при NULL: `qk_circuit_num_qubits(NULL)` упав із `NullPointerError … panic in a function that cannot unwind` (перевірено випадково, див. п. 2).

Відкрите: чи плануються `remove_final_measurements`/`measure_all` у C API, не перевіряв (гіпотеза: ні; треба дивитись issues Qiskit).

## 2. Маршрути імпорту з Codon і що саме компілюється

Codon 0.20.7 встановлено в `~/.codon` (офіційний `install.sh` лише `curl … | tar` у `~/.codon`, прочитано перед запуском; виконав ці ж два кроки вручну, без правки профілю shell).

| Маршрут | Що перевірено | Що нативне | Що в CPython |
|---|---|---|---|
| `from python import qiskit` | `probe/pyqiskit.codon`: `CODON_PYTHON=…/libpython3.12.dylib`, `PYTHONPATH=.venv/...`; побудова 5-кубітної схеми, `remove_final_measurements`, `copy`, `x`, `measure_all` → `{'measure':5,'cx':4,'h':1,'x':1,'barrier':1}`, 2,4 мс | Лише цикли/арифметика Codon навколо викликів | Увесь Qiskit: за docs.exaloop.io/integrations/python/python-from-codon модуль «runs in an embedded CPython interpreter», Codon «do not compile the imported Python library into native Codon code»; значення лишаються `pyobj`, кожна операція іде через CPython C API |
| `from C import` проти `libqiskit` | `twirl.codon` → `libtwirl.dylib` (`codon build -release --relocation-model=pic --lib --linker-flags="-L… -lqiskit -Wl,-rpath,…"`), драйвер `probe/main.c`, результати збіглись з `probe/ref.py` | Усе: Codon-код + прямі виклики Rust-функцій без інтерпретатора | Нічого; але й `QuantumCircuit` немає, вхід/вихід — `QkCircuit*` і масиви |
| Змішаний | `probe/mixed.codon`: `from python import qiskit`, потім `from C import ACC.qk_circuit_borrow_from_python(cobj) -> cobj` з `_accelerate.abi3.so` (динамічний імпорт = `dlopen`/`dlsym` за docs.exaloop.io/integrations/cpp/cpp-from-codon). Треба передавати `qc._data.p` (RUST: `borrow_map_mut::<PyCircuitData,…>`, circuit.rs:2224), не `qc.p` (інакше NULL і panic). Копія, X на кубіт 2, `qk_circuit_to_python` → `{'cx':4,'h':1,'x':1}`, 0,9 мс | Обробка схеми через C API | Створення `QuantumCircuit`, `_data`, повернення `pyobj` |

Швидкість (однакові розміри, 10 задач × 4 копії, n = 20; postprocess 40 результатів × 50 ключів):
- CPython `original.py` (`probe/bench_py.py`): preprocess 7,6 мс, postprocess 0,9 мс.
- C/Codon (`probe/bench.c`, два запуски): preprocess 2,09 / 0,52 мс, postprocess 0,085 / 0,079 мс.
Тобто ~4–15× на preprocess і ~10× на postprocess, абсолютні цифри в мілісекундах. Для маршруту «`from python import qiskit`» окремого бенчмарка preprocess не робив (гіпотеза, не перевірено: приблизно як CPython, бо вся робота зі схемою йде через інтерпретатор).

ГСЧ: `np.random.default_rng(seed).integers(0, 2, size=…)` у Codon збігається з NumPy 2.5.5 для seed 0 (4×3) і seed 7 (4×5) (`probe/rng.codon` проти `.venv` python); Codon реалізує `PCG64` (`~/.codon/lib/codon/stdlib/numpy/random/__init__.codon:7,14,21`). Фліпи в `probe/main` і `probe/ref.py` також збіглись: `1 1 1 0 0 / 0 0 0 0 1 / 1 1 1 1 1 / 1 1 1 1 1`.

## 3. Чи допомагає машинний код «встигнути до декогеренції»

- У `original.py` `preprocess` будує схеми до відправлення, `postprocess` обробляє словники `counts` після виконання; обидва отримують `tasks`/`results` як звичайні Python-об'єкти на хості. IBM Qiskit patterns (quantum.cloud.ibm.com/docs/en/guides/intro-to-patterns): кроки «Map… / Optimize… / Execute on target hardware / Post-process results»; post-process — «classical data-processing steps», після повернення виходів. Між відправленням і поверненням результату кубіти вже виміряні; стан після вимірювання не існує, тож швидкість `postprocess` на час когерентності не впливає.
- У вікні когерентності виконується тільки те, що вшите у схему: IBM «Execute dynamic circuits» (quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits): «IBM Quantum Compute Service currently only supports the conditional `if` statement», «Arithmetic operations are not supported», «operand … must be 32 or fewer bits», «limited physical memory on control electronics»; значення зі `store` «only saved in memory during execution and not copied or returned in the job result». Латентність feed-forward: блог IBM (ibm.com/quantum/blog/utility-scale-dynamic-circuits) «Feedforward latency is also down to around ~600ns»; там же: «qubits that aren't being measured are left to sit idle and decohere».
- Висновок: Codon на хості не стає ближчим до QPU, ніж CPython; обидва відділені від контрольної електроніки мережею та чергою хмарного сервісу (гіпотеза, не перевірено: типова затримка черги/мережі — секунди-хвилини, на порядки більша за будь-який виграш у мілісекундах). Якщо мета — класична логіка під час когерентності, єдиний шлях — dynamic circuits (`if_test`, classical expressions у `qiskit.circuit.classical`, OpenQASM 3) у самій схемі; twirling з випадковими X перед вимірюванням — статична підстановка і не потребує real-time логіки взагалі.
- Де Codon усе ж корисний: якщо preprocess/postprocess робити для десятків тисяч схем або в C/C++-застосунку без Python (libtwirl як C-бібліотека), або у середовищі без CPython. Це не перевіряв на масштабі (гіпотеза).

## 4. Практична перевірка

Усе в `/Users/slava.karkunov/Projects/Codon`:
- `~/.codon/bin/codon --version` → 0.20.7; `.venv` (uv, Python 3.12.13): qiskit 2.6.2, numpy 2.5.5; Rust toolchain `1.91-aarch64-apple-darwin` (без default, але `rust-toolchain.toml` Qiskit пінить `channel = "1.91"`, тож `make c` зібрався).
- `qiskit/dist/c/lib/libqiskit.dylib`, `qiskit/dist/c/include/qiskit.h` + `qiskit/*.h`.
- Правки `twirl.codon`: лише `@tupleclass` → `@tuple` (рядок 27): Codon видав `unsupported class decorator`; `@tuple` — його декоратор для незмінного struct-подібного класу. Усе інше (`from C import …`, `Ptr[u32]`, `"meas".c_str()`, `np.random.default_rng`, `dict[int,float]`) скомпілювалось без змін. `build.sh` не запускав (він з одинарними дефісами `-lib`, `-linker-flags`; я використав `--lib`, `--linker-flags=`; чи приймає Codon одинарні — не перевіряв).
- `libtwirl.dylib` (52 КБ) експортує `_twirl_preprocess`, `_twirl_postprocess`.
- `probe/main.c` + `probe/ref.py`: однакові фліпи, однакові `count_ops` і `clbits=5` на всіх 4 копіях, однакові 7 ймовірностей (0.15, 0.175×4, 0.075×2) на тих самих синтетичних результатах. Правка в драйвері: `qk_opcounts_free` не існує, є `qk_opcounts_clear(&oc)` (`funcs.h:1260`).
- `probe/bench.c` / `probe/bench_py.py`: таймінги вище. `probe/rng.codon`: ГСЧ збігається. `probe/pyqiskit.codon`, `probe/mixed.codon`: маршрути з п. 2.

Відкрите / не зроблено:
- Не перевірив поведінку `twirl_preprocess`, коли вхідна схема має клбіти (повертає `TWIRL_ERR_HAS_CLBITS`; видаляти фінальні виміри в C API нечим — треба або робити це в Python до виклику, або писати обхід через `qk_circuit_get_instruction`).
- Не тестував `twirl.h` із C++ (`extern "C"` є, але не компілював).
- Не перевіряв, чи стабільний ABI `Task` (`@tuple` з `cobj, int` ↔ `struct {QkCircuit*; int64_t}`) на інших платформах; на arm64 macOS працює.
- Таймінг Codon-маршруту «python import» для повного preprocess не робив.

## 5. Доповнення 2026-11-20: `remove_final_measurements` через C API

- `twirl.codon` тепер сам прибирає кінцеві вимірювання й бар'єри: порт `calc_final_ops` із `qiskit/transpiler/passes/utils/remove_final_measurements.py` на DAG-функціях (`qk_circuit_to_dag`, `qk_dag_predecessors`/`successors`, `qk_dag_op_node_gate_op`), потім схема перебудовується без clbits.
- Перевірка: `probe/rfm.c` проти `probe/rfm_ref.py` (`original.py`) на 3-кубітній схемі з фазою 0.5, `rz(0.3)`, бар'єром посередині й частковим бар'єром між вимірюваннями: варіанти без некінцевих вимірювань і з `reset` збіглися з Python по кожній інструкції (`diff`).
- Обмеження: некінцеве вимірювання або операція, крім gate/barrier/reset, дають `TWIRL_ERR_UNSUPPORTED_OP` (Python такі схеми приймає, лишаючи старий регістр поруч із `meas`). Символьні параметри гейтів: `qk_dag_op_node_gate_op` панікує (`crates/cext/src/dag.rs`, `panic!("Invalid parameter on instruction")`).
- Час, медіана 50 запусків, 10 задач × 4 копії × 20 кубітів, схеми з `measure_all` (`probe/bench_rfm.c`, `probe/bench_rfm.py`), M1 Pro під навантаженням (load average ≈ 9): preprocess 0,70 мс (Codon) проти 6,33 мс (Python); postprocess 0,051 мс проти 0,855 мс.
- `build.sh`: прапорці виправлено на ті, з якими збірка пройшла (`--lib`, `--linker-flags=`).
