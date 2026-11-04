# Synchronous comparison harness

This is an optional Linux development benchmark, not a runtime dependency.
It needs the pinned Goose compiler (`make setup`), Git, GCC, G++ with C++17,
Python 3.9+, and network access to fetch pinned source repositories. All external
sources/builds stay under ignored `.build/compare/`, retaining upstream licenses.

```sh
make setup
make check test
python3 bench/compare/run.py --iterations 100000 --rounds 9 --cpu 0
```

`make bench-compare` runs these defaults. Use an available logical CPU; affinity
does not reserve that core or isolate the host. The runner builds without LTO,
using GCC/G++ `-O2` and Goose `-O2` inlining. spdlog is header-only with its bundled
fmt. No spdlog thread-ID or atomic-level removal macros are defined. The only
level-name customization uppercases labels and calls critical `FATAL` so the
shared output can be byte-identical. A no-op mutex sink matches the single-thread
application-owned synchronization contract; this is not a thread-safety test.

The runner pins source URLs/commits, rejects dirty dependency checkouts, and
records compiler versions, binary hashes, the full standard-library source
hashes, fixture hashes, driver hash, source commit, and dirty state. `--no-build`
validates these inputs against the build manifest; it does not silently reuse
a stale executable. Source/input changes during a run invalidate the results.
Output defaults to `.build/compare/results.json`, containing every raw sample.

## Shared-output profile

`goose-log`, `rxi/log.c`, and synchronous spdlog produce exactly
`[LEVEL] message\n` into the same copying/checksum memory sink. Fixtures are read
before timing: empty, 39 printable bytes, 512 printable bytes, 4096 printable
bytes, and a filtered Debug call at an Error minimum. Unadapted inputs are
restricted to printable ASCII **excluding backslash**, at most 4096 bytes.
Controls, Unicode, backslashes, and larger messages need different security
adapters and must not be compared as if the libraries had identical contracts.

Each process configures its logger once, validates complete output and callback
counts, warms up with 1000 calls, then times one batch. All adapters use the same
preselected function-pointer dispatch and checksum/copy loop. Complete final
output, callback counts, and checksums are checked after timing. Nine rounds
shuffle the job order with seed `0x6005e`. An untimed preflight checks all seven
minimum levels against all six emitted severities for each adapter. Every
sample includes normal process scheduling effects and shared-host noise.

The displayed times include harness dispatch/copy/checksum work. They are
batch-average nanoseconds per call, not tail latency or external I/O throughput.
rxi's custom callback always initializes its clock/calendar metadata, even
though this profile does not print it. spdlog's normal overload captures time
and thread metadata; `spdlog-supplied-time` uses its public supplied-time overload
but retains default thread-ID and atomic-level behavior. Goose does not capture
an unused clock implicitly. These are real implementation differences, not
proof of equal internal work or whole-framework feature/security parity.

## Logical record with matched external policy

`macho-record` calls the pinned Goose alternative's native record formatter.
`goose-record+policy` calls goose-log's record formatter, but deliberately uses
the **same third-party timestamp formatter and secret-redaction policy** on its
input first. Neither clock reads nor I/O are timed; both receive the same fixed
timestamp and source location. This does not make the policy a built-in feature
of goose-log. Two reviewed fixtures cover ordinary text and a synthetic password
redaction. Record batches use at most 1000 calls because the policy is expensive.

The logical fields/policy match, but native wire formats and lengths differ;
each has its own complete expected output and checksum. These rows describe
logical-record pipelines, not equal-byte formatting throughput. Do not compare
their checksums as if they must be identical or attribute the whole result to
the formatter. See [feature comparison](../comparison.md) for remaining gaps.
