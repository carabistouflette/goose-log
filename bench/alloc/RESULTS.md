# Allocation and arena observations

Measured on 2026-11-04 UTC from clean, unchanged source
[`10a794ab376786dd949671c5942c4bb9124c0aa5`](https://github.com/carabistouflette/goose-log/tree/10a794ab376786dd949671c5942c4bb9124c0aa5).
The later results/documentation commit does not change the probe or library.
Both independently launched runs used identical source/compiler/stdlib hashes
and the same driver hash. Raw results are [results.json](results.json) and
[repeat-results.json](repeat-results.json). See the [probe method](README.md)
for counter boundaries and exact-output controls.

## Environment

- Linux x86-64, kernel `7.2.11-arch1-1`, 4096-byte OS pages.
- `gcc (GCC) 16.2.1 20260810`, `-O2 -std=c11`, no LTO; the four heap functions
  have `-fno-builtin-*` flags so the real-call control cannot be optimized away.
- Goose `eadca40 (runtime 3025e5810379)`, full compiler source pin
  `eadca409f68210893f366e60d0c2f0dc29a339be`, generated with `-O2`.
- Eight fresh processes per run: counter control, initialization, and six
  formatter phases. Warm phases perform one maximum-size render before measuring
  10000 calls; cold phases measure one call. These are memory observations,
  not execution-time or latency measurements.

## Formatter phases

All six phases observed **zero direct calls** to `malloc`, `calloc`, `realloc`,
`free`, `mmap`, `mprotect`, `munmap`, and `madvise` during measurement, in both runs.
This statement only covers calls from the instrumented translation unit.

| Phase | Measured calls | Logical arena bytes before → after | Minor faults, first / repeat |
| --- | ---: | ---: | ---: |
| Cold plain | 1 | 0 → 16417 | 5 / 5 |
| Warm plain | 10000 | 16417 → 16417 | 0 / 0 |
| Cold record | 1 | 0 → 28592 | 7 / 7 |
| Warm record | 10000 | 28592 → 28592 | 0 / 0 |
| Cold filtered | 1 | 0 → 0 | 0 / 0 |
| Warm filtered | 10000 | 16417 → 16417 | 0 / 0 |

The independent host checked every emitted line against the exact maximum
16417-byte plain or 28592-byte contextual output. Filtered calls preserved
scratch and never called the sink. Each phase retained one virtual arena
reservation of **2148532224 bytes** established during initialization, including
the guard gap. This is virtual address space, **not resident memory**.

## Initialization and interpretation

Initialization was measured separately. In both runs it made one direct
`malloc` request of 65536 bytes, two `calloc` requests totaling 48 bytes, one
`mmap` request of 2148532224 bytes, one `mprotect`, and one `madvise`. Its minor
fault count was 6 in the first run and 7 in the repeat. Runtime teardown is
outside these measurement windows.

Cold rendering advanced logical arena tops and faulted pages despite zero new
direct heap/mapping calls. Warm rendering reused its existing logical arena
extent. These boundary snapshots do not capture peak temporaries, C/native
stack usage, libc-internal allocations, or physical memory committed elsewhere.
Minor faults are process observations, not exact logger-only physical allocation
counts. The caller's message construction and any real I/O sink also add work
outside this probe. **No allocation-free, zero-memory, RSS, or durability guarantee
follows from these results.**

## Reproduce

```sh
git clone https://github.com/carabistouflette/goose-log.git
cd goose-log
git checkout 10a794ab376786dd949671c5942c4bb9124c0aa5
make setup
python3 bench/alloc/run.py
python3 bench/alloc/run.py --output .build/alloc/repeat-results.json
```

GNU-compatible linker wrapping and the pinned runtime registry are required.
Page-fault observations can vary with the OS and concurrent work; the raw files
retain all counters, requested-byte totals, arena boundaries and build inputs.
