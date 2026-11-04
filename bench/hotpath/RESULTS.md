# Short-message and filtering investigation

## Decision: keep the released runtime

The six-line short-ASCII candidate is **rejected**. Clean 39-byte messages
improved, but 39 escape-heavy bytes regressed in all 18 paired comparisons,
by about 24% in each series. Unsafe-first messages regressed by about 9%, and
15-byte printable messages by about 5%, also in all 18 pairs. These penalties
violate the acceptance criterion; they are not averaged away against the wins.
The retained `logger.goose` and compiler pin remain byte-identical to v0.1.1.
No release speedup, universal filtering cost, or superiority claim is made.

The accepted work is the reproducible native benchmark, independent validation,
and 56 exact protected-page cases (14 sizes × four patterns) covering empty,
clean, first/last unsafe, and final backslash input. Existing severity, byte and
record oracles, ownership checks, Linux CLI tests and sanitizer coverage remain.

## Frozen method and provenance

Measured 2026-11-04 UTC. Both series began and ended clean at candidate source
[`66c7b7e0954d9fdf1d05fb6aff2794985c2e26a6`](https://github.com/carabistouflette/goose-log/tree/66c7b7e0954d9fdf1d05fb6aff2794985c2e26a6).
The candidate adds a clean-input check/copy only for 16..511-byte messages;
unsafe input falls back to the original byte loop. The baseline logger comes
from [`0ec9a007c128bcb48d6bb8923faf7e3cbc281a4f`](https://github.com/carabistouflette/goose-log/tree/0ec9a007c128bcb48d6bb8923faf7e3cbc281a4f).
Both are rebuilt under the same current compiler and harness; this is not a
comparison of complete historical builds.

- Goose pin `eadca409f68210893f366e60d0c2f0dc29a339be`, `goose eadca40 (runtime 3025e5810379)`.
- Intel Core Ultra 7 258V, Linux 7.2.11-arch1-1, GCC 16.2.1 20260810.
- Native children pinned to logical CPU 3, builds on CPU 5. No other local
  goose-log heavy jobs ran during the final series. This was a shared host;
  affinity/courtesy coordination provided no exclusive core, fixed frequency,
  or host isolation. Outliers remain in the raw records.
- Two independently built/launched nine-round series, 33 cases × two variants:
  **1188 raw process samples**. Pair order and case order are shuffled with
  seed `0x6005e`; each process warms scratch with 1000 calls.
- Short accepted samples use 1000000 calls, long samples 10000, and filtered
  samples 10000000. Native GCC/Goose `-O2`, no LTO, sanitizers, or external I/O.
- Runtime-loaded fixtures/configuration; two file-loaded severity slots are
  selected per call. Configurations remain fixed per process; colors are off.
  The native sink consumes a byte/checksum and does not copy the line.
- Exact warmup bytes/status, final bytes, timed Written/Filtered counts,
  callback counts, and independent Python checksums pass. All 49 named
  severity/minimum pairs are preflighted for both binaries. Sources, fixtures,
  compiler, stdlib, and binary hashes are verified after timing.

See [the method](README.md), [first raw run](results.json), and
[independent repeat](repeat-results.json) for full hashes, versions, fixture
metadata, every process result, and all per-case median/min/max summaries.
An independent reviewer reconstructed all 33 fixture hashes, all 1188 checksums,
and every summary statistic, and confirmed the rejection.

## Selected results

Base/candidate values are median **batch-average ns/call**. Paired change is the
median of the nine within-round `(candidate / baseline - 1)` values, so it can
differ from the ratio of the two displayed medians. Negative favors the candidate;
positive is a penalty. These are not single-call tail latencies or production
throughput. All 33 cases and ranges remain in the raw files.

| Case | Base 1 | Candidate 1 | Paired change 1 | Base 2 | Candidate 2 | Paired change 2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| short39 | 65.42 | 20.34 | -68.96% | 63.09 | 19.34 | -69.17% |
| ascii15 | 24.42 | 25.64 | +5.23% | 23.19 | 24.60 | +5.11% |
| ascii16 | 24.72 | 16.39 | -34.45% | 25.02 | 16.24 | -35.18% |
| ascii511 | 455.66 | 72.45 | -84.16% | 441.53 | 69.90 | -84.47% |
| unsafe-first39 | 49.56 | 54.10 | +9.02% | 47.55 | 52.06 | +9.48% |
| unsafe-middle39 | 49.56 | 52.36 | +5.63% | 48.48 | 49.48 | +3.93% |
| escaped39 | 71.25 | 88.73 | +24.53% | 69.10 | 85.75 | +23.90% |
| backslashes4096 | 2770.37 | 2810.23 | +0.10% | 2696.76 | 2739.98 | +1.53% |
| filtered-mixed | 4.33 | 4.17 | -4.96% | 4.19 | 3.99 | -6.76% |

[Interactive paired-change chart](results.html) includes every case and both
series. In particular, filtering results are specific to this optimizable native
caller and checksum/status workload. They do not establish an unhoisted general
per-call cost. The filtered gains do not compensate for the repeated penalties.

The escaped-first cases skip the added scanner; their slowdown cannot be
attributed simply to rescanning. Whole-process instruction/cycle counter probes
are retained in [profiles](profiles/README.md); they do not isolate a causal
microarchitectural explanation. No sampling profile was obtained because this
host denied `perf record`; its security settings were left unchanged.

## Alternatives and scope

The [existing pinned rxi/log.c and synchronous spdlog comparisons](../compare/RESULTS.md)
remain the relevant cross-library evidence: the released runtime is unchanged.
Their sink copies bytes and includes a C-host bridge, so their absolute times
must not be compared with this native checksum-only harness. The prior supplied-time
spdlog short/filtered advantage remains an explicitly documented limitation;
this rejected experiment does not establish a new win over another library.

No macOS performance claim follows from Linux measurements. Platform correctness
coverage is described in [PORTABILITY.md](../../PORTABILITY.md). Exploratory
variants are not included in the frozen tables or used as release evidence.

## Reproduce the rejected experiment

```sh
git clone https://github.com/carabistouflette/goose-log.git
cd goose-log
git checkout 66c7b7e0954d9fdf1d05fb6aff2794985c2e26a6
make setup
python3 bench/hotpath/run.py --baseline 0ec9a007c128bcb48d6bb8923faf7e3cbc281a4f --cpu 3 --build-cpu 5 --rounds 9
python3 bench/hotpath/run.py --baseline 0ec9a007c128bcb48d6bb8923faf7e3cbc281a4f --cpu 3 --build-cpu 5 --rounds 9 --output .build/hotpath/paired/repeat-results.json
```

Use CPUs available on your host. On current main the same command compares
unchanged logger sources; check out the identified candidate to reproduce the
experiment. Timings will vary. No compiler, native binary, cached dependency,
private workspace note, or generated build is distributed with these results.
