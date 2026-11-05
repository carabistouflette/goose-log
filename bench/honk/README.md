# Whole-Honk logging profile

This Linux controller runs the same trusted native Honk binary and synthetic,
dependency-free `metadata` project with and without `--log-file`. It never builds
or modifies an application checkout. Use a separate clean checkout and build its
binary first, or copy a verified owner-provided binary to `.build/honk` there.
A source pin and executable hash do not prove a binary came from that source;
trust and record its build provenance.

```sh
python3 bench/honk/run.py \
  --honk-source /absolute/path/to/isolated/honk \
  --honk-revision 855fb0552aefd5f0c033826af64f3bdd09ae6482 \
  --goose /absolute/path/to/pinned/goose --cpu 6 \
  --rounds 9 --calls 32 --output .build/honk-profile/results.json
```

Commit the harness before measuring. Sources must be clean; outputs are created
exclusively. A private synthetic fixture, sanitized child environment and isolated
HOME/cache avoid user projects, credentials and network dependencies. Metadata
does not invoke the compiler. Harness/source/binary/compiler/fixture identities
are checked before and after execution; paths and metadata stdout stay private.

Both paths warm once before deterministic shuffled paired rounds. Every batch
launches fresh sequential native processes. Timing includes process creation,
startup, metadata work, clocks, output capture, synchronous logging when enabled,
parent loop/wait work and timeout management. Validation follows each batch.
Results are batch-average whole-command times, not formatter costs, per-call
percentiles or long-lived process throughput.

Every enabled call must preserve exact metadata stdout/status/stderr and append
Started then Returned with zero outcomes and valid numeric durations. Batches
use a private 0600 regular file and sentinel prefix; full bytes, mode, ownership,
device/inode and link count are checked. Disabled batches preserve file bytes.
One relative path component is used. Readback is outside timing; delivery is to
the OS/page cache without fsync, not durable disk throughput.

Busy-lock and 16 MiB quota rejection are untimed acceptance controls: nonzero
diagnostic failure, no metadata, unchanged bytes/identity/mode. They do not model
slow filesystems or late failures. A blocking syscall can delay synchronous
delivery; this establishes no bounded sink latency. Existing library/Honk CLI
acceptance tests separately cover partial writes, quota-after-Started, stdout
failure and privacy. Any slow-I/O shim must be explicitly separate instrumentation.

No allocator hooks are added to the product. The existing
[allocation probe](../alloc/RESULTS.md) covers formatter boundaries, not whole-Honk
allocation totals. Do not infer allocations from time, virtual memory or RSS.
Build/run workloads, compiler costs and UTC logging are outside this profile.

Affinity is not exclusive core/filesystem isolation. Keep every round/outlier and
repeat independently before interpreting small differences. Enabled/disabled
differences include all changed application work, not exact logger-only cost.
Production changes require a demonstrated bottleneck and matched comparison.
