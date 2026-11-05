# Optional UTC consumer component measurements

This Linux-only development tool measures the real application-owned
[`utc_log::emit`](../../examples/utc/utc.goose) adapter and existing `emit_record`.
It does not change the core logger or measure file/network delivery, complete
application throughput, or individual-call tail latency. The optional entrypoint
pins goose-time to `343887caeee0a1f4e2e536ff322fcafb454e11bd`.

```sh
make setup
# Every run requires a new or empty output directory.
python3 bench/utc/run.py --smoke --output .build/utc/smoke-01
# Commit/freeze sources first; seven shuffled rounds, 100000 calls per stage.
python3 bench/utc/run.py --iterations 100000 --rounds 7 --warmup 64 \
  --cpu 0 --build-cpu 3 --output .build/utc/measurement-01
```

Choose available CPUs; defaults use the first available CPU for measurement and
last available CPU for compilation. `--goose /absolute/path/to/goose` overrides
the default pinned compiler, and `--cc gcc` selects the C compiler. Builds use
`-O2 --standalone` without native CPU tuning. The runner verifies the compiler
checkout and executable’s advertised revision against GOOSE_REVISION and records
its binary hash and version. The advertised short revision is an identity check,
not cryptographic verification of the executable.
`--allow-dirty` permits exploratory measurements while recording the dirty state
and exact source hashes. Smoke permits dirty sources, caps iterations at 64 and
rounds at two, and provides correctness evidence rather than useful timings.
Existing output contents are always preserved; the runner refuses to overwrite.

Each fixture contains eight runtime-loaded signed Unix-nanosecond samples and
messages, plus independently computed expected timestamp/plain/record bytes.
Samples include i64 endpoints, pre-epoch fractions, epoch values and varying
fractional precision. The two fixtures use short ASCII messages or messages
with NUL, non-ASCII, newline, tab, backslash and escape bytes. Runtime configuration
selects Info/Off filters, Info records and no color. Source values are loaded from
binary fixture files before timing. There is no live user or credential data.

| Stage | Timed work |
| --- | --- |
| `plain_record` | Core `emit_record` with no timestamp |
| `preformatted_record` | Core `emit_record` with a precomputed runtime timestamp |
| `format_only` | Clear reused timestamp builder, convert sampled integer, append canonical UTC |
| `adapter_fixed` | Real adapter with runtime fixture clock and synchronous checksum sink |
| `adapter_os` | Real adapter with real OS wall-clock acquisition and same checksum sink |
| `filtered_record` | Core timestamp record rejected at minimum Off |
| `filtered_adapter` | Real adapter rejected at minimum Off; clock and sink must remain unused |
| `clock_only` | OS clock wrapper and counter/sample-store/checksum work |

All output bytes contribute to a position-weighted integer checksum. Enabled
record stages share a sink that counts calls, bytes and checksum. Fixed/OS clock
wrappers count calls and store each sample in a preallocated i64 array; these
stores are included in timing. OS trace serialization and file I/O happen after
timing. Normal calls store the last sample too. Stage dispatch, iteration/indexing,
assertions, status checks, counters and checksum work are measured. A single
batch timer surrounds the loop; no per-call timer is inserted.

Every process independently verifies all fixture outputs outside timing, then
runs the selected stage with the same scratch builders for warmup and timing.
Warmup results are excluded from counters and the timer. Builders retain their
capacity; this is a reused-scratch workload, not a fresh allocation benchmark.
Both filtered stages must preserve sentinel bytes in both builders. Stages run
in fresh processes in a seeded shuffled order in each round. Compilation is outside timing and pinned to the build CPU. Independent
Python validation runs outside timing in the parent process with its inherited
affinity; measurement children are pinned to the selected measurement CPU. Affinity does
not reserve a CPU or control turbo, frequency, scheduling, thermal state or
other work on the host.

Python's datetime plus integer division constructs expected calendar bytes
without float Unix timestamps or local-time conversion. For every batch the
runner independently checks counts, all-byte aggregate checksums and complete
final output. It checks **every** OS sample against its exact recorded i64 trace,
reconstructing the corresponding timestamp/record bytes independently. No
assumption of wall-clock monotonicity or equality across processes is made.

Results retain every raw batch in `rounds.jsonl`, runtime fixtures and hashes,
compiler/standard-library/runtime-header/source hashes, exact dependency commit
and source hashes, flags, tool/platform/CPU identities, affinity and dirty state.
Measured sources/compiler/dependency/executable are checked again after capture.
A failed run retains its evidence and never marks validation passed. Summary
median/min/max values are over batch-average nanoseconds per call, not individual
latency distributions. No rounds are discarded.

Smoke always retains compressed complete OS sample traces. Full measurements
independently verify each trace and retain its hash, then discard per-call traces
to keep routine result records small; use `--retain-traces` to keep them compressed
as well. Full-run OS checksums without retained traces cannot be independently
recomputed from the compact record alone; the companion smoke capture provides
replayable trace/byte-oracle evidence. Fixed stages remain replayable from their
retained fixtures and iteration counts.

Preformatted timestamp records are the closest logging baseline for the adapter.
Plain records emit fewer bytes; their timings include different rendering and
checksum work. OS and fixed samples have different output distributions. Costs
from separate stages **must not be added or subtracted as an exact decomposition**.
The traces and counters also add instrumentation work. Results are scoped
component measurements, with no universal rankings or latency guarantees.

## Initial exploratory record

[Full capture](results/initial/metadata.json): seven shuffled rounds, 100000 calls
per stage, 64 warmups, two fixtures and all eight stages (112 raw batch results).
All independent output/count/checksum checks passed. Feature checkout
`a29dd800171bdc2084155393e795908bf20d2632` had uncommitted benchmark sources and
application documentation, recorded explicitly as dirty. Source hashes identify
all measured core/adapter/benchmark/compiler/dependency bytes. These results
are exploratory evidence, not a clean-commit release benchmark.

[Summary](results/initial/summary.json) and [all batches](results/initial/rounds.jsonl)
retain substantial variation and outliers; no samples were removed. Full-run OS
traces were independently checked before discarding them; their hashes remain.
The [small smoke capture](results/smoke/metadata.json) retains compressed traces
and complete raw counters, enabling OS-oracle replay. Both captures use matching
benchmark/source hashes. Runtime fixture files carry the exact messages, fixed
clock samples and expected bytes. Nonempty-output rejection was exercised and
preserved existing result-file bytes.

Run one measurement process at a time per checkout/cache: Goose caches generated
C by source path. Source/executable hash checks catch ordinary concurrent drift,
but do not establish adversarial race freedom. CPU affinity does not reserve a CPU.

## Frozen-source follow-up

The [final capture](results/final/metadata.json) records clean source commit
`5ede662`, after adding executable-revision validation and verifier mutation
controls. Seven shuffled rounds at 100000 calls, two fixtures, all eight stages
and every outlier remain in [112 raw batches](results/final/rounds.jsonl).
The companion [final smoke](results/final-smoke/metadata.json) retains 32 batches
and compressed OS traces. Both captures passed independent counters, complete
output and all-byte checksums. The logger, compiler pin, UTC adapter, benchmark driver and runner still match
source `5ede662`; see the [checked source comparisons](../CURRENTNESS.md).
Later commits added results, release documentation and final-smoke replay tests;
those changes are not timed implementation changes. The UTC adapter remains
byte-identical to a29dd80.

Run `make bench-utc` from a clean checkout for full measurements, or
`make bench-utc-smoke` for correctness. Both allocate fresh result directories.
`python3 tests/utc_bench.py` replays every originally retained smoke sample and
requires rejection of corrupted checksum, callback-count and final-byte fields;
it also rejects malformed/mismatched compiler-advertised revisions. These checks
pass under normal Python and `python3 -O`.
