# Platform validation

Validated on 2026-11-04 at source
[`dae6c5b47ca5655af774af73b601df4c01cd650b`](https://github.com/carabistouflette/goose-log/commit/dae6c5b47ca5655af774af73b601df4c01cd650b),
with pinned Goose compiler `eadca409f68210893f366e60d0c2f0dc29a339be`
(`goose eadca40`, runtime `3025e5810379`). Both jobs in
[CI run 41890244787](https://github.com/carabistouflette/goose-log/actions/runs/41890244787)
passed. This is correctness/portability evidence, not a performance measurement.
The core `logger.goose` implementation and compiler pin are unchanged from 0.1.0.

## macOS ARM64

The `macos-15` runner was checked for Darwin and `arm64` before setup. Its
recorded environment was macOS 15.8.2 (24H232), runner image
`macos-15-arm64/20261028.0489.1`, Apple Clang 17.0.0
(`clang-1700.0.13.5`, target `arm64-apple-darwin24.6.0`), CMake 4.4.4, and
Python 3.15.2. The compiler was built from the full pinned source on this runner.

From a standalone clone, reproduce the core validation with Git, Make,
CMake 3.27+, Python 3.9+, and the Xcode command-line C/C++ toolchain installed:

```sh
export CC=clang CXX=clang++ GOOSE_CC=clang SANITIZER_CC=clang
export ASAN_OPTIONS=detect_leaks=0:halt_on_error=1
export UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
make setup
make check-core test-core
make test-guarded
make test-sanitize
```

Verified coverage:

- Formatting/types, JIT logger/features/overload tests, native normal/debug
  logger/features tests, and the hello/file examples. The generic stdlib file
  example checks append preservation, open failures, and usage; Linux's
  `/dev/full` test is skipped on macOS.
- Ownership/type rejection with a positive control, including scratch/message
  aliasing, sink mutation, optional sink returns, and public limit mutation.
- Independent Python byte oracle: 1792 cases per normal/debug native driver;
  record oracle: 160 cases per normal/debug native driver.
- Optimized/debug protected-page probes, including an intentional fault control
  and filtered messages beginning in inaccessible memory. Tests use the actual
  OS page size and accept the platform's protected-read fault signal.
- Standalone Apple Clang ASan/UBSan: the same 1792-case oracle in debug and
  optimized builds, debug feature tests, and the 160-case optimized record
  oracle. LeakSanitizer is explicitly disabled; no leak-check claim is made.
- Eight setup cases, including clean locale-aware collation and refusal of
  modified/staged/untracked compiler sources, non-full pins, and hidden-source
  index flags. Refusal leaves source and HEAD untouched.

The first macOS attempt exposed a bootstrap bug: Bash locale collation could
make `[a-z]` match Git's ordinary uppercase `H` index tag. The guard now spells
out lowercase tags, still rejecting assume-unchanged and skip-worktree entries.
A local negative control rejected the old guard under the regression's locale
settings; the fixed guard passed locally and on macOS.

## Linux x86-64

The same CI run passed the full Ubuntu 24.04 job: `make check test`, protected
pages and sanitizers under GCC and Clang, the Linux CLI adapter's normal and
sanitized real-filesystem tests, and correctness smokes for the pinned
comparison, allocation probe, and CLI component profiler. Smokes establish
output/counter checks only; their timing is not a benchmark result.

Existing Arch Linux measurements and exact tool versions remain in
[benchmark provenance](bench/results.md), [matched comparison](bench/compare/RESULTS.md),
[allocation observations](bench/alloc/RESULTS.md), and
[CLI component results](bench/cli/RESULTS.md).

## Limits

Only the core and generic stdlib file example are validated on macOS. The
hardened application-owned CLI file adapter and optional profiling/comparison
tools retain their Linux scope. No macOS performance result is claimed.
Windows, macOS x86-64, Linux ARM64, other OS versions, and other Goose compiler
revisions remain unverified.

Sanitizers do not poison every logical array boundary/lifetime inside Goose's
custom mmap-backed data stacks. Protected pages cover whole protected pages,
not every logical boundary or the backing array's final partial page. These
checks complement compiler ownership/bounds checks and independent output
oracles; passing them does not prove absence of bugs.

One Make invocation per checkout is required: the pinned compiler shares
generated C paths. Make goals run serially, including with `-j`, but separate
simultaneous invocations do not coordinate. Use the pinned source and avoid
editing the cached compiler; setup refuses source states that hide local edits.
