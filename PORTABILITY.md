# Platform validation

Current main's CI covers the following with the compiler in
[GOOSE_REVISION](GOOSE_REVISION):

| Component | Linux x86-64 | Linux ARM64 | macOS 15 ARM64 |
| --- | --- | --- | --- |
| Core logger and generic file example | Tested | Tested | Tested |
| CLI file adapter | Tested | Tested | Not tested |
| Optional UTC adapter | Tested | Tested on main | Not tested |

Released v0.1.3 predates the Linux ARM64 CI addition. Its core and adapter source
bytes match main; this does not claim that the tag ran the newer CI matrix.
Performance results remain Linux x86-64 only. Windows and macOS x86-64 are unverified.
The sections below retain exact environments and coverage from specific runs.

Initial Linux x86-64/macOS validation ran on 2026-11-04 at source
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

## Linux ARM64

Native Ubuntu ARM64 validation passed at source
[`86b7ab599b19710a7739fc13f97e6e2773145b21`](https://github.com/carabistouflette/goose-log/commit/86b7ab599b19710a7739fc13f97e6e2773145b21).
The `linux-arm64` job in
[CI run 41935734506](https://github.com/carabistouflette/goose-log/actions/runs/41935734506)
completed successfully at `2026-11-04T23:45:01Z`, along with the unchanged
x86-64 and macOS suites. The runtime and compiler pin remain unchanged from
v0.1.2; no performance improvement is claimed.

The `ubuntu-24.04-arm` runner checked `uname -s = Linux` and
`uname -m = aarch64` before cache restoration or setup. It reported Ubuntu
24.04.5 LTS, kernel `7.0.0-1017-azure`, four Neoverse-N2 CPUs, little-endian
byte order and 4096-byte pages. Workspace and `/tmp` filesystem labels from
`stat -f` were `ext2/ext3`. GNU GCC/G++ 13.3.0 built the pinned compiler from
source; Clang 18.1.3, CMake 3.31.6 and Python 3.12.3 were recorded.

The same Linux job definition runs on both architectures, with separate
OS/architecture caches and `fail-fast: false`. It retained every prior check:

- `make check test`: JIT/native/debug API checks, independent 1792-case byte
  and 160-case record oracles per native driver, ownership rejection, generic
  file append/open/`/dev/full` checks, setup guards and Linux CLI tests.
- Seeded mixed-operation sequences on normal/debug/JIT drivers, including the
  state-only mutation/reduction/replay control. This is the bounded four-seed
  CI corpus; the larger local campaign remains separate evidence.
- Optimized/debug protected-page tests under GCC and Clang, including exact
  short slices and inaccessible filtered/sensitive inputs.
- Core standalone ASan/UBSan and sequence tests in debug/optimized builds,
  plus the native CLI adapter's real filesystem suite under GCC and Clang.
- Correctness smokes for the pinned cross-library comparison, allocation
  probe, CLI component profiler and paired native hot-path harness.

The combined source
[`84b0cf8ed540a988ba9638f1db7602d9baf0b712`](https://github.com/carabistouflette/goose-log/commit/84b0cf8ed540a988ba9638f1db7602d9baf0b712)
also passed all three jobs in
[CI run 41937670364](https://github.com/carabistouflette/goose-log/actions/runs/41937670364).
That Linux ARM64 run additionally passed the existing optional UTC consumer
tests, its component correctness smoke, and its GCC/Clang sanitizer suites.
This extends the earlier Linux x86-64 consumer checkpoint; it does not establish
macOS consumer support or an ARM64 performance result.

Reproduce on a native Ubuntu ARM64 host with the documented prerequisites:

```sh
make setup
make check test
make GOOSE_CC=gcc test-guarded
make GOOSE_CC=clang test-guarded
make SANITIZER_CC=gcc test-sanitize test-cli-sanitize
make SANITIZER_CC=clang test-sanitize test-cli-sanitize
```

Review identified that three reporting scripts assumed the x86-style
`/proc/cpuinfo` field `model name`. They now report JSON `null` if it is absent,
and retain the actual architecture independently. Local synthetic missing-field
controls passed all three scripts' output/counter/checksum smokes; the real
ARM64 job then passed the complete suite. These smoke timings are not ARM64
benchmark results. Existing published measurements remain Linux x86-64 evidence.

## Limits

Only the core and generic stdlib file example are validated on macOS. The
hardened application-owned CLI file adapter and optional profiling/comparison
tools retain their Linux scope. No macOS performance result is claimed.
Windows, macOS x86-64, other OS versions, and other Goose compiler
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
