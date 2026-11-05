# CLI component measurements

Measured on 2026-11-04 UTC from clean, unchanged source
[`0c3794066cb3d5c5c1e06cace92b953437baea46`](https://github.com/carabistouflette/goose-log/tree/0c3794066cb3d5c5c1e06cace92b953437baea46).
Both independently launched series used identical implementation, harness,
compiler/stdlib inputs and driver hash. The measured driver, logger and
file-adapter sources are retained unchanged. Raw samples: [results.json](results.json) and
[repeat.json](repeat.json). See [method and workload](README.md).

These are native component pipelines for the fixed enum/numeric CLI helper,
**not whole Honk command latency**, process startup, physical disk throughput,
or production service results. Each stage has its own loop/counter/checksum
work and process/cache/lifetime context. Do not add or subtract stage timings
to attribute a cost to construction, scratch policy, or configuration alone.

Current-code status: the timed implementation and pinned compiler/dependencies
still match main. See the [checked source comparisons](../CURRENTNESS.md) for
exact paths and any reporting-only runner changes. This does not turn the
recorded timings into measurements on a different host or toolchain.

## Provenance

- CPU: Intel(R) Core(TM) Ultra 7 258V; measurement/oracle children pinned to CPU 0; build children on CPU 3.
- Linux 7.2.11-arch1-1, x86_64, 4096-byte pages; libc glibc 2.44.
- Filesystem: `btrfs`, 4096-byte filesystem blocks. Each delivery path has four relative components.
- Compiler: `gcc (GCC) 16.2.1 20260810`; Goose `goose eadca40 (runtime 3025e5810379)`; full source pin `eadca409f68210893f366e60d0c2f0dc29a339be`.
- Goose/GCC `-O2`, C11, no LTO/sanitizers. The native sink also has `-Wall -Wextra -Werror`. Full flags and hashes are retained in the raw files.
- Two independently launched series, nine shuffled rounds × six stages each: **108 retained process samples**.
- Each process prebuilds the 64-event runtime pool outside timing, performs 64 warmup calls, then 20000 measured calls. A proof file validates all 64 constructed messages and rendered lines independently.
- File stages preserve an existing prefix and verify every warmup/measured output byte and private-file metadata outside timing. Filtered stages verify zero builder/sink calls and unchanged scratch.
- Shared development host; no exclusive core, filesystem isolation, frequency control, or tail-latency claim.

## Results

All times are **batch-average nanoseconds per call**. Ranges are min–max over
nine process samples, not per-call latency percentiles.

| Stage | First median | First range | Repeat median | Repeat range |
| --- | ---: | ---: | ---: | ---: |
| construction | 71.79 | 70.54–77.17 | 70.79 | 64.93–71.90 |
| render | 77.44 | 72.64–88.09 | 77.31 | 74.77–80.26 |
| filtered | 2.27 | 2.23–9.19 | 2.33 | 2.23–10.07 |
| append | 10438.43 | 10176.56–10926.74 | 10247.91 | 9842.52–10581.55 |
| full | 10590.54 | 10234.18–10743.52 | 10620.86 | 10156.73–10856.20 |
| adapter | 10716.45 | 10341.94–10997.10 | 10619.62 | 9744.43–10809.96 |

`construction` calls the actual numeric message helper. `render` consumes
prebuilt runtime messages and reuses caller scratch. `append` delivers prebuilt
lines through the real native file policy. `full` uses counted message/sink
closures through `emit_lazy` with reused scratch. `adapter` calls the actual
`diagnostics::write` wrapper, including its lexical scratch and configuration/
failure-latch checks. Its private builder/sink/byte/checksum counters are **null**,
not assumed zero; successful returns and complete file bytes are validated.

The checked append stages are much larger than the compute stages in this
workload. Each append walks directory components, opens and validates the
private file, takes a nonblocking advisory lock, checks quotas, writes and
closes. Existing files are opened rather than held persistently. Results
include syscall and OS/page-cache behavior; there is no fsync, durable-storage,
rotation, async, allocation-free, or general throughput guarantee.

File timing begins after setup/proof I/O and warmup. It is not cold-file
creation performance, and the similar full/adapter medians do not isolate the
cost of their different buffer policies. The core logger is unchanged from
v0.1.0; these results do not establish a release speedup or replace the older
[matched alternative comparison](../compare/RESULTS.md).

## Reproduce

```sh
git clone https://github.com/carabistouflette/goose-log.git
cd goose-log
git checkout 0c3794066cb3d5c5c1e06cace92b953437baea46
make setup
make check test
python3 bench/cli/run.py --iterations 20000 --rounds 9 --warmup 64 --cpu 0 --build-cpu 3
python3 bench/cli/run.py --no-build --iterations 20000 --rounds 9 --warmup 64 --cpu 0 --output .build/cli/repeat.json
```

Choose available CPUs. The profile requires Linux and a trusted private checkout;
results vary with filesystem, kernel, toolchain, power state and concurrent work.
