# Historical single-library benchmark

Recorded 2026-11-04 UTC for an older logger implementation. **These numbers
are historical, not current-library results.** The current logger differs from
the measured source; no source bridge is claimed. Use the [benchmark index](README.md)
for measurements whose timed code still matches main. Raw output remains unchanged.

## Provenance

- Library and benchmark source: [`e450b55dcda36ca8b197ed5f17c2da79f847d8db`](https://github.com/carabistouflette/goose-log/tree/e450b55dcda36ca8b197ed5f17c2da79f847d8db). Reproduction checks out that exact historical implementation, not main.
- Goose source: [`eadca409f68210893f366e60d0c2f0dc29a339be`](https://github.com/aardappel/goose/tree/eadca409f68210893f366e60d0c2f0dc29a339be).
- Goose version: `goose eadca40 (runtime 3025e5810379)`.
- Native C compiler: `gcc (GCC) 16.2.1 20260810`.
- Build: Goose `-O2` inlining and GCC `-O2`, without debug/sanitizer instrumentation.
- CPU: Intel(R) Core(TM) Ultra 7 258V; architecture `x86_64`; 8 logical CPUs.
- OS: Arch Linux (rolling); kernel `7.2.11-arch1-1`.
- Command: `make bench BENCH_ITERATIONS=100000`.
- Seven measured batches of 100000 calls per row (700000 measured calls/row).
- No CPU affinity or fixed-frequency control; other development work may share the host.

## Results

Values are median/min/max across seven **batch-average nanoseconds per call**,
not individual-call latency percentiles. Checksums consume results to make the
work observable. Raw output is retained in [results.txt](results.txt).

| Case | Median ns/call | Min ns/call | Max ns/call | Checksum |
| --- | ---: | ---: | ---: | ---: |
| threshold (default: filtered) | 6.22261 | 6.09289 | 6.54177 | 5600000 |
| empty | 6.86953 | 6.61384 | 6.95778 | 53900000 |
| printable | 39.38394 | 37.62697 | 40.45613 | 93355423 |
| emit-printable | 36.47285 | 33.83169 | 62.722 | 93266047 |
| printable-4096 | 3871.07108 | 3809.32759 | 4745.49677 | 2940661409 |
| backslashes-4096 | 2745.43367 | 2686.62652 | 2765.7701 | 5804383830 |
| mixed-4096 | 4899.11952 | 4836.23705 | 4923.1966 | 8356037599 |
| escaped-256 | 406.16349 | 398.81837 | 414.43609 | 795010454 |
| truncated-100k | 6086.29193 | 6066.78755 | 6130.38095 | 11557676200 |

## Method and limits

The render and emit rows warm reusable scratch with 1000 untimed calls once
per row. The threshold row has no explicit warmup. This measures reused storage,
not process-cold allocation or an allocation-free guarantee. Timings include
loop, checks, and checksum work; they exclude external file/terminal/network I/O.

Default configuration has colors off and minimum Info. The threshold row
instead uses runtime-selected Error and alternates Debug/Info, so its default
calls are filtered. Render rows alternate Info/Warn; `emit-printable` uses only
Info and a synchronous checksum sink returning true. Their difference does not
isolate callback overhead. Literal messages/configurations can be specialized
by the native compiler; runtime-provided inputs may behave differently.

Cases include empty input, a 39-byte printable message, 4096 printable bytes,
4096 backslashes, bytes 0..255 repeated to 4096 bytes, 256 `0xff` bytes, and
100000 `0xff` bytes truncated to the first 4096 source bytes. All emitted data
remains subject to the library's documented bounds and escaping rules.

## Reproduce

```sh
git clone https://github.com/carabistouflette/goose-log.git
cd goose-log
git checkout e450b55dcda36ca8b197ed5f17c2da79f847d8db
make setup
make check test
make bench BENCH_ITERATIONS=100000
```

The checked-out revision intentionally predates this results document and
contains the exact benchmark source measured here. Install GCC and the setup
requirements listed in the current README. Performance values will vary with
tool versions, hardware, CPU scheduling, power state, and concurrent load.
