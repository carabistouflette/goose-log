# Measured synchronous comparisons

Measured on 2026-11-04 UTC, source [`5c5db8fd5fe733e51e5230def818a336a367e069`](https://github.com/carabistouflette/goose-log/tree/5c5db8fd5fe733e51e5230def818a336a367e069).
Both runs started and ended with a clean, unchanged source tree, identical
compiler/stdlib inputs and driver hash. The later documentation/results commit
does not change the measured implementation or harness.

These are **scoped pipeline measurements**, not proof that every feature of
another framework is present or that goose-log is universally faster. See the
[feature contract comparison](../comparison.md) and [harness method](README.md).

## Provenance and method

- CPU: Intel(R) Core(TM) Ultra 7 258V; both runs pinned measurement children to logical CPU 0.
- Host: Linux 7.2.11-arch1-1; shared development machine, no exclusive core, fixed-frequency control, or host isolation.
- C compiler: `gcc (GCC) 16.2.1 20260810`; C++ compiler: `g++ (GCC) 16.2.1 20260810`.
- Goose: `goose eadca40 (runtime 3025e5810379)`, full source pin `eadca409f68210893f366e60d0c2f0dc29a339be`.
- GCC/G++ `-O2`, Goose `-O2` inlining; no LTO, sanitizers, or debug instrumentation in the measured driver.
- Pinned dependencies: rxi/log.c `f9ea34994bd58ed342d2245cd4110bb5c6790153`; spdlog v1.17.0 `79524ddd08a4ec981b7fea76afd08ee05f83755d`; Macho0x/goose-logger v0.3.4 `50695a3df0eb5a1048a4b183538d59f43f5eb279`.
- Two independently launched series, each nine shuffled rounds, seed `0x6005e`, 24 jobs/round: **432 retained samples** total.
- Shared-output jobs: 100000 measured calls/sample; logical-policy records: 1000 calls/sample. Each process warms up with 1000 calls once.
- Untimed preflight covers all minimum/severity pairs. Full output, callback counts, and timed checksums are validated. Fixtures load outside timing; external I/O is not measured.
- Goose uses a generated C-host bridge here; results include that bridge rather than representing every native Goose call site. Every backend shares preselected function-pointer dispatch and memory-sink copy/checksum work.

## Results

All values below are **batch-average ns/call**. Ranges are min–max over nine
samples, not single-call tail latencies. Large ranges expose scheduling/power
variation on this shared host. Raw samples, versions, source/fixture/compiler
hashes and per-job counters are retained in [results.json](results.json) and
[repeat-results.json](repeat-results.json).

| Case | Adapter | First median | First range | Repeat median | Repeat range |
| --- | --- | ---: | ---: | ---: | ---: |
| ascii4096 | goose-log | 616.84 | 590.46–1870.11 | 586.35 | 579.18–634.02 |
| ascii4096 | log.c | 1538.26 | 1465.86–4711.46 | 1479.63 | 1447.45–1536.50 |
| ascii4096 | spdlog | 1631.50 | 1569.00–4912.00 | 1525.08 | 1509.03–1583.69 |
| ascii4096 | spdlog-supplied-time | 1631.49 | 1546.79–2289.63 | 1517.49 | 1493.92–1647.07 |
| ascii512 | goose-log | 82.52 | 77.14–268.22 | 77.71 | 75.14–80.24 |
| ascii512 | log.c | 1377.25 | 1343.66–1419.29 | 1321.73 | 1281.19–1391.16 |
| ascii512 | spdlog | 286.01 | 275.63–896.41 | 276.92 | 272.63–296.77 |
| ascii512 | spdlog-supplied-time | 266.70 | 245.47–820.85 | 256.65 | 247.15–272.25 |
| empty | goose-log | 19.61 | 18.16–80.66 | 18.69 | 18.10–19.63 |
| empty | log.c | 1367.18 | 1333.04–4156.42 | 1310.09 | 1264.32–1363.83 |
| empty | spdlog | 82.50 | 78.89–231.50 | 79.89 | 77.79–98.55 |
| empty | spdlog-supplied-time | 47.26 | 43.58–54.95 | 44.14 | 43.03–46.82 |
| policy-hit | goose-record+policy | 125676.93 | 120983.49–333931.56 | 122072.62 | 113765.10–129692.40 |
| policy-hit | macho-record | 130729.96 | 124050.36–458783.99 | 121996.99 | 117682.65–128824.08 |
| short | goose-log | 77.19 | 63.80–260.52 | 74.35 | 68.22–78.44 |
| short | goose-record+policy | 115748.44 | 112911.31–406984.39 | 109899.09 | 105730.15–116088.51 |
| short | log.c | 1357.51 | 1282.54–2755.39 | 1295.45 | 1262.72–1347.99 |
| short | macho-record | 119900.90 | 111907.82–412135.40 | 110444.78 | 105123.43–115961.65 |
| short | spdlog | 102.92 | 94.86–104.69 | 96.16 | 92.43–232.48 |
| short | spdlog-supplied-time | 65.40 | 60.18–241.93 | 61.70 | 61.10–68.52 |
| filtered | goose-log | 6.69 | 6.45–7.29 | 6.33 | 6.31–6.53 |
| filtered | log.c | 7.46 | 7.27–67.16 | 7.41 | 6.95–16.42 |
| filtered | spdlog | 5.35 | 5.09–55.11 | 5.40 | 5.01–8.09 |
| filtered | spdlog-supplied-time | 5.42 | 4.75–114.56 | 5.14 | 4.84–6.15 |

## Interpretation

The 512-byte and 4096-byte printable-message results favor goose-log in both
series. Short messages favor goose-log against the normal spdlog overload, but
**the supplied-time spdlog path is faster for short and filtered calls**.
There is no universal win. Filtered differences are only a few nanoseconds and
include adapter/host-dispatch costs.

rxi/log.c always initializes time/calendar data for its callback, even though
this shared-output profile does not print it. Normal spdlog captures time;
its supplied-time variant still retains normal thread-ID and atomic-level
behavior. Goose does not capture unused time implicitly. Report these as
implementation/configuration differences, not identical internal work.

`goose-record+policy` uses Macho's exact timestamp formatter and redactor first;
that policy is an external adapter, not a goose-log built-in. Native record
formats and lengths differ. The policy pipelines are broadly similar at this
scale, and overlapping/noisy samples do not support a decisive formatter-only
win. Explicit sensitive-field masking is a different feature from automatic
secret-pattern detection and is not used as a shortcut in these policy rows.

The unadapted shared-output corpus is printable ASCII excluding backslash,
maximum 4096 bytes. It does not establish equal safety behavior on arbitrary
bytes or oversized data. goose-log's separate byte oracles, metadata tests,
protected pages and sanitizer suites validate those documented guarantees.

## Reproduce

```sh
git clone https://github.com/carabistouflette/goose-log.git
cd goose-log
git checkout 5c5db8fd5fe733e51e5230def818a336a367e069
make setup
make check test
python3 bench/compare/run.py --iterations 100000 --rounds 9 --cpu 0
python3 bench/compare/run.py --no-build --iterations 100000 --rounds 9 --cpu 0 --output .build/compare/repeat-results.json
```

Choose a CPU available on your system. The harness fetches exact comparison
source pins into ignored build storage. Results will vary by toolchain, CPU,
power state, and concurrent work. No cold-start, allocation-free, durability,
async, rotation, or multi-threaded throughput guarantee follows from this run.
