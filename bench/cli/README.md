# CLI diagnostic component profile

This optional Linux development tool measures the real
[`examples/cli` diagnostics helper](../../examples/cli/diagnostics.goose), the
logger, and that example's error-aware C file sink. It does **not** measure an
entire Honk command, process startup, child execution, or product throughput.
The actual CLI consumer is checked separately. The `adapter` stage measures its
public `diagnostics::write` wrapper without adding product instrumentation hooks.

The separate [whole-Honk logging study](../honk/README.md) measures repeated
native metadata commands and keeps allocator/delayed-write instrumentation
separate from plain latency. Its scope and startup costs differ from this probe.

```sh
make setup
# Small correctness/build check; dirty working trees are allowed here only.
python3 bench/cli/run.py --smoke --cpu 3 --build-cpu 3
# Commit/freeze the implementation and harness before recording measurements.
python3 bench/cli/run.py --iterations 20000 --rounds 9 --warmup 64 --cpu 0 --build-cpu 3
python3 bench/cli/run.py --no-build --iterations 20000 --rounds 9 --warmup 64 --cpu 0 --output .build/cli/repeat.json
```

Choose CPUs available to your process. The runner, independent oracle, and
measurement children are pinned to `--cpu`; compilation children move to
`--build-cpu`. Affinity does not reserve a core or isolate filesystem/kernel
activity. The defaults above keep measurements on CPU 0 and builds off the
source-editor CPU 1 on the shared development host. No governor or exclusive
core policy is imposed.

## Workload and stages

The Python runner writes a runtime binary fixture with 64 events and passes its
path and seed as process arguments. Event names are the real fixed application
events: started, item completed, returned, failed, and child failed. Numeric
durations/outcomes vary by seed; zero and maximum `u64`/`u32` values exercise
integer formatting. Default seed is `0x6005e`. The exact fixture bytes and hash
are retained in results. There is no user text or credential data in the fixture.
Durations are replayed numbers; per-event clock acquisition and business work
are outside these component measurements.

Each child loads the fixture, configures the actual helper, constructs all 64
messages with `diagnostics::message`, and builds message/line pools before
timing. A separate proof file contains every complete constructed message and
rendered line; the Python oracle checks these bytes independently. Those two
proof appends are setup I/O and can warm directory/filesystem state.

| Stage | Timed work |
| --- | --- |
| `construction` | Build owned bytes through the real message helper; consume length and a byte in a checksum |
| `render` | Render prebuilt runtime messages using real event severity and reused scratch; consume output |
| `append` | Append pre-rendered lines through the real safe file adapter; consume output |
| `full` | Invoke core `emit_lazy`, with counted closures calling the real message and append helpers |
| `adapter` | Call the actual configured `diagnostics::write` wrapper with its lexical per-call scratch and error latch |
| `filtered` | Invoke that pipeline at minimum Off; require zero builder/sink calls and unchanged scratch |

The minimum comes from a runtime process argument (Info for enabled stages,
Off for filtered); failed/child-failed events are Error and other
events are Info. Colors and automatic timestamps are absent. `full` uses the
same construction/severity/sink helpers as the application wrapper, but owns
its own logger and reused scratch so builder/sink suppression can be counted
without product probe hooks. The actual adapter uses lexical scratch per call;
that buffer policy and its configuration/latch checks are outside this stage.
`adapter` includes them: configure runs once before warmup and is never reset
during timing. It counts successful boolean returns. Private builder/sink calls
and in-memory byte/checksum counters are unobserved (`null`, not zero); complete
file bytes validate delivery externally. Its different counter work and buffer
policy mean an adapter/full difference is not an isolated scratch-cost measure.

Stages run in separate fresh processes with nine shuffled rounds by default.
Pools and scratch are prepared outside timing. Each stage then performs 64
untimed warmup operations before 20000 measured operations. Both warmup and
measured sequences start at fixture index zero; observed counters/checksums,
successful adapter returns, and complete files are independently validated.
Non-default counts are recorded. Smoke mode is
limited to 64 operations/warmups and two rounds, and produces validation data,
not publication measurements.

Counters, checksums, loop/indexing, status checks, and one stage dispatch per
batch are included. Summary median/min/max values are over batch-average
nanoseconds per call, not individual-call tail latencies. These component
results have different cache and ownership conditions: **do not add them or
subtract them as an exact decomposition of full-pipeline time**. Fixed control
flow can still specialize; runtime numeric fixtures do not prevent every
compiler optimization.

## Real file delivery and validation

Every sample gets a private temporary directory and a pre-existing 0600 regular
file with a sentinel prefix. The append, full, and adapter files retain all warmup plus
measured output. Python checks every byte, the preserved prefix, file ownership,
mode, link count, inode, byte count, and hash after timing. Other stages must
leave that file unchanged. Complete proof bytes are also checked outside timing;
render/full validate the final scratch line, and filtered validates preservation.

The real sink walks path components without following symlinks, opens the file
for each call, checks owner/0600/regular/single-link metadata, takes an advisory
nonblocking lock, rechecks quota/metadata, writes, and closes. All these per-call
open/walk/lock/stat/write/close costs are included in append/full/adapter. The fixture
uses a relative path; its component count is recorded without private names.
The lock coordinates cooperating writers, not arbitrary outside modification.

There is a 16417-byte line limit and a **16 MiB per-file total cap**, including
the existing prefix and warmup. The runner rejects counts whose predicted output
would exceed that cap. Files are verified and removed between jobs, so this is
not a growing unbounded log or a disk-pressure/backpressure experiment. Record
counts, bytes, filesystem type/block size, and sample durations are retained.
Any delivery failure invalidates the run; partial output may already exist and
no logging retry or rollback is attempted.

The destination is a real regular file, not `/dev/null`. No `fsync` is performed:
successful append-and-close plus readback demonstrates OS/page-cache delivery,
**not durable physical-disk throughput**. Filesystem, scheduling, shared-host
activity, and dirty-page/writeback policy can affect results. No allocation-free,
fixed-capacity, cold-start, atomic multiwriter, or durability guarantee follows
from scratch reuse or these measurements. The separate allocation probe has its
own boundaries and does not count all libc work in a real file sink.

## Provenance and reproduction

Non-smoke runs require a clean source tree. The runner fingerprints the actual
logger, helper and C sink, driver/runner, Goose binary, complete pinned standard
library, GCC binary/version, and explicit build flags. `--no-build` verifies a
manifest and executable hash. Source, compiler, fixture, or executable changes
during the run invalidate results. Output defaults to ignored
`.build/cli/results.json`; no private log/fixture paths are stored in it.

Results include OS/kernel/architecture/libc, page size, CPU model/affinity,
filesystem type/block size, seed, exact fixture bytes, warmup, counts, validated
file/proof hashes, all elapsed batches, and summaries. Pin the recorded source
commit and toolchain when reproducing. The benchmark writes ignored `.build/cli`
artifacts and does not modify an application checkout.

See [recorded results and raw samples](RESULTS.md) for the measured source pin.
