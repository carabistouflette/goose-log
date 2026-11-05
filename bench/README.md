# Benchmarks

Choose the measurement that matches your question. All recorded timings are
local Linux x86-64 observations, not throughput or latency guarantees. The
renderer, callback dispatch and real file sink do different work.

| Measurement | What it covers | Current-code status |
| --- | --- | --- |
| [Synchronous alternatives](compare/RESULTS.md) | Printable-message pipelines with rxi/log.c and spdlog; separate logical-record policy comparison with a Goose logger | Timed code and dependency pins match main |
| [Allocation probe](alloc/RESULTS.md) | Direct allocation calls, arena snapshots and page faults | Measured code matches main; not a timing or allocation-free claim |
| [CLI components](cli/RESULTS.md) | Message construction, rendering and checked file append | Timed logger/adapter code matches main |
| [UTC adapter](utc/README.md#frozen-source-follow-up) | Fixed and OS clocks, timestamp formatting and contextual output | Final measured code and goose-time pin match main |
| [Native input experiment](hotpath/RESULTS.md) | A rejected short-message change, including its slower cases | Historical candidate; main retains the measured baseline |
| [Honk v0.2.0](honk/RESULTS.md) | Whole-command metadata, heap observations and injected write controls | Historical application binary; not current Honk performance |
| [Early literal-input suite](results.md) | An earlier renderer with fixed messages | Historical implementation; not current logger performance |

[Source comparisons](CURRENTNESS.md) explain how these classifications were
checked, including reporting-only changes in three runners. Identical source
does not make an old number a new-machine measurement. Machine, OS, compiler,
flags, fixtures, units, warmups, repetitions, raw samples and dispersion are
recorded with each result. Keep those conditions when interpreting a table.

## Running a benchmark

Each linked method has complete commands and prerequisites. Start with
`make setup`; use the compiler in [GOOSE_REVISION](../GOOSE_REVISION). Comparison
sources and the optional UTC dependency use full commits, not moving branches.
Choose CPUs available to the process and keep one build/measurement invocation
per checkout. CPU affinity does not isolate a host or filesystem.

Smoke modes check outputs and counters; their timings are not benchmark results.
Run source checks and output controls before a measurement, then keep every
sample, including slower cases and outliers. Existing reports retain the slower
supplied-time spdlog rows and the rejected candidate's escaped-input regressions.

The small `make bench` literal-input driver is still available for experiments,
but its old published table uses a different renderer. No current literal-suite
speed claim is made, so this documentation audit did not rerun it.

## Limits that matter

- Shared-output comparisons use printable ASCII without backslashes and a
  copying memory sink. They do not establish matching binary-input safety or
  full framework feature parity. See the [feature comparison](comparison.md).
- Native checksum sinks, copying sinks and real file sinks have different
  costs. Do not mix their absolute times or subtract stages as an exact cost
  decomposition.
- Allocation tools see different boundaries. Direct heap-call counts and
  heaptrack observations do not count every logical allocation in Goose arenas.
- Synchronous file delivery can block. Readback without fsync proves neither
  durable storage nor a worst-case latency bound.
- The compact full UTC capture omits OS traces after validating them. Its
  smoke captures retain traces for replay; see the [UTC method](utc/README.md).
