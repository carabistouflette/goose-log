# Native hot-path comparisons

The [published candidate experiment](RESULTS.md) is historical and was rejected.
Current `logger.goose` matches its baseline, not the candidate. See the
[source comparisons](../CURRENTNESS.md).

Optional Linux development measurements compare two versions of `logger.goose`
with the same native Goose caller. This is separate from the C-host
[cross-library copying-sink harness](../compare/README.md). Absolute times from
these two harnesses must not be compared directly.

```sh
make setup
make check test test-guarded test-sanitize
python3 bench/hotpath/run.py \
  --baseline 0ec9a007c128bcb48d6bb8923faf7e3cbc281a4f \
  --cpu 3 --build-cpu 5 --rounds 9
```

Use available logical CPUs; affinity does not reserve a core or isolate the
host. The baseline commit must be available in local Git history. Both baseline
and current logger source are rebuilt under the **current** pinned compiler,
standard library, and GCC `-O2`, without LTO or sanitizers. The original baseline
compiler pin is also recorded. No compiler-version comparison follows from this
run. Generated sources, binaries, and default results stay in ignored
`.build/hotpath/paired/`. Run only one invocation per checkout.

Messages, configuration, and expected output load from binary fixtures before
timing. Each call chooses one of two file-loaded severity slots. Accepted cases
use identical slots; a mixed filtered case alternates Debug/Info at Error.
Configuration and message are fixed per process, colors are disabled, and the
synchronous sink counts calls and consumes one output byte in a checksum; it
does not copy or perform external I/O. These optimizable native callers do not
establish a universal per-call filtering cost or model changing configurations.

Each process checks complete expected bytes/status and warms scratch with 1000
calls before timing. Final output/status/callback counts are checked, and Python
independently checks the timed checksum. A preflight checks all 49 named
minimum/severity pairs, including Off, for both binaries. Cases cover printable
sizes around 16/32/512 bytes, a 39-byte request, unsafe bytes at several positions,
escape/backslash-heavy and mixed data, long/oversized messages, and filtering.

Each round shuffles cases and baseline/candidate order within each pair, seed
`0x6005e`. Short accepted cases use one million timed calls by default; long
inputs use one hundredth as many, at least 1000; filtered cases use ten times
as many, capped at ten million. Values are batch averages, not per-call tail
latencies. Shared-host scheduling and power variation remain in every sample.

Results retain every process sample, fixture hashes, source commit/dirty state,
library/driver/runner/compiler/stdlib hashes, native binary hashes, compiler
versions, CPU/kernel, affinity and exact counts. Inputs, fixtures, binaries, and
source state are rechecked after timing. Clean source is required unless
`--allow-dirty` explicitly marks an exploratory run. Exploratory numbers are not
release evidence. `--smoke` runs ten calls/case in one round solely for
correctness; CI compares HEAD with itself in this mode.
