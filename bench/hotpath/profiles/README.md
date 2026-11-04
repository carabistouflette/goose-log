# Supplementary instruction/cycle counters

Four separate `perf stat` runs on CPU 3 used the frozen native binaries from
the repeated series, source `66c7b7e0954d9fdf1d05fb6aff2794985c2e26a6`.
Each performed 10000000 timed accepted calls with the same runtime fixtures.
The [manifest](manifest.json) records binary hashes and hashes of the retained
counter CSVs and checked driver output. Compiler/stdlib/toolchain provenance
is identical to [the repeated run](../repeat-results.json).

These counters cover the **entire child process**, including startup, warmup,
timed calls, and final checks. They are single supplementary observations,
not repeated formatter-only instruction counts or timing estimates. Do not
substitute their elapsed/cycle counts for the nine-round measurements.

| Case | Baseline user instructions | Candidate user instructions | Baseline user cycles | Candidate user cycles |
| --- | ---: | ---: | ---: | ---: |
| short39 | 5810972486 | 2510641669 | 982868029 | 303248202 |
| escaped39 | 8931476223 | 8951478434 | 1108528095 | 1343881622 |

The hybrid CPU's `cpu_core` events counted for the full enabled interval;
`cpu_atom` entries are explicitly not counted. Short-printable instruction
work dropped, while the escaped case's similar instruction count does not
explain its cycle penalty. No causal claim about cache, branch prediction,
register allocation, or instruction layout follows from these counters.
Sampling via `perf record` was denied by host permissions; no host settings
were changed to obtain it.

After reproducing the frozen series, collect the same supplementary counters:

```sh
taskset -c 3 perf stat -e instructions:u,cycles:u -x, \
  .build/hotpath/paired/baseline/driver .build/hotpath/paired/short39.bin 10000000
taskset -c 3 perf stat -e instructions:u,cycles:u -x, \
  .build/hotpath/paired/candidate/driver .build/hotpath/paired/short39.bin 10000000
```

Repeat with `escaped39.bin`. Counter availability and results depend on the
CPU, OS permissions, frequency, and other host activity. These Linux probes
make no claim about macOS performance.
