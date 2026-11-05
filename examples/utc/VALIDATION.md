# Optional UTC consumer validation

The adapter and independent behavioral tests were first committed at a29dd80.
`logger.goose` remains byte-identical to the public baseline
`7b0fc5675b62c8b397cc082ce5630e350edeef9d` (blob
`336fae4a31dc5b5b09ca2c36e3219732b4513e2e`). GOOSE_REVISION is unchanged at
`eadca409f68210893f366e60d0c2f0dc29a339be`. Only optional entrypoints import
experimental goose-time `343887caeee0a1f4e2e536ff322fcafb454e11bd`.

Local checks use Linux x86-64, GCC 16.2.1 and Clang 23.1.4, with that exact Goose
compiler. The consumer does not acquire a global clock or introduce an optional
dependency into the core import graph. Tests inject clock readings deterministically.

Performed checks:

- Existing `check-core test-core`, including independent byte/record oracles,
  ownership, mixed-operation replay and mutation controls, passed with a fresh
  GOOSE_HOME and no goose-time fetch. Existing Linux CLI tests also passed.
- New `test-utc`: normal/debug runner and executable, exact complete output,
  all severity/Off and color combinations, callback invocation counts, filtered
  buffer preservation, full signed-nanosecond endpoints, negative dates, buffer
  reuse, hostile bytes, truncation, empty messages, and false sinks without retry.
- Hostile consumer integer/text formatting overloads run in the same consumer
  tests; they do not alter timestamp or log output.
- The ownership probe accepts its valid control and rejects 11 invalid programs
  for the expected type, alias or mutability reason. It covers shared buffers,
  inputs borrowing either output, incompatible clock/sink results, and mutation
  of the sink's borrowed line. Python checks use explicit failures rather than
  optimization-removable asserts.
- GCC and Clang native ASan/UBSan checks passed in debug (`--no-bce`) and optimized
  standalone executable modes. The behavioral tests also passed in ordinary
  standalone debug GCC/Clang executables.
- Fresh-cache execution of the real-clock example fetched the pinned dependency,
  left stdout empty, and emitted one complete UTC-stamped stderr record.
- Source formatting, Python syntax compilation, and whitespace checks passed.
- Benchmark controls replay retained smoke rows, reject deliberately corrupted
  checksums/callback counts/final bytes, and reject mismatched executable revisions.
  They pass both normal and optimization-enabled Python.
- Frozen source 5ede662 produced 112 full benchmark batches plus 32 replayable smoke
  batches, all validated with the exact dependency and recorded source/tool hashes.
  All stages and outliers remain retained; these are instrumented batch costs.
- Independent design and implementation reviews checked filtering, bounds,
  callback counts, borrowing, sink outcomes and the optional dependency graph.

Reproduce from this checkout after `make setup`:

```sh
make check test
make test-utc
make test-utc-sanitize
SANITIZER_CC=clang make test-utc-sanitize
```

The optional CI steps run on Linux. Existing core macOS validation does not
establish macOS support for the UTC consumer or goose-time. The consumer's core
formatter still provides bounded output, not bounded callback execution or
allocation-failure recovery. The stderr example cannot check delivery because
Goose's standard stderr function returns no I/O status.

Hosted CI must pass on the published source before parent registration. Local
commands above are not presented as a hosted result. See the optional component
benchmark for instrumentation costs and retained evidence; no default-core speed
change or universal performance ranking is claimed.

## Publication checkpoint

The consumer was published through
[PR #3](https://github.com/carabistouflette/goose-log/pull/3) at
`b7c46dab861bd8875fff58f48d990e265976dd44`, whose full tree equals tested head
`03e96ac12bdad6e62bf1b5a4da452e6305cacaf0`.
[Actual main CI](https://github.com/carabistouflette/goose-log/actions/runs/41935649420)
passed on that published commit: Linux covers the optional consumer and core;
macOS ARM64 covers the core. These are hosted results, separate from the local
commands above. No Linux ARM64 consumer coverage is claimed by this checkpoint.

Version 0.1.3 preparation changes only release documentation. Its implementation,
compiler pin, tests, measurement tools and retained samples remain byte-identical
to the published checkpoint. Successful maintained CI on the exact release
commit is required before tagging. The
[release record](https://github.com/carabistouflette/goose-log/releases/tag/v0.1.3)
links that exact-commit evidence and identifies the source-only archive/checksum.
