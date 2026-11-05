# Changelog

## Unreleased

- Validate the full Linux test/filesystem/sanitizer suites and correctness smokes
  on native Ubuntu 24.04 ARM64, alongside x86-64, with separate architecture
  caches and native architecture assertions. No runtime/compiler-pin change.
- Report an unavailable CPU model as JSON `null` in synchronous comparison, CLI
  and hot-path benchmark metadata when `/proc/cpuinfo` lacks `model name`; record
  architecture independently.

## 0.1.3 — 2026-11-05

Optional-consumer maintenance release. The core logger, documented API/output/
bounds, standard-library-only core dependency graph, and compiler pin are
unchanged from 0.1.2. Existing release tags remain immutable.

- Optional application-owned UTC record consumer using pinned goose-time,
  injected clocks and reusable builders. Core source, contract and dependencies
  remain unchanged; optional tests and component measurements cover the integration.
- Deterministic clock/sink tests, compiler ownership/type rejection, and GCC/Clang
  ASan/UBSan validation for the optional consumer. Optional entrypoints pin
  experimental goose-time `343887caeee0a1f4e2e536ff322fcafb454e11bd`.
- Runtime-input component measurements with independent byte/checksum oracles,
  replayable smoke traces, executable-revision checks and corruption controls.
  All stages/outliers remain recorded; no speedup or exact cost decomposition
  is claimed. UTC-consumer platform validation is Linux x86-64 only; macOS
  ARM64 core CI does not establish optional-consumer portability.

## 0.1.2 — 2026-11-05

Test-and-documentation maintenance release. The core implementation, documented
API/output/bounds, and compiler pin are unchanged from 0.1.1. No performance
gain is claimed.

- Seeded mixed-operation state tests with replayable fixtures, bounded reduction,
  owned/borrowed lazy builders and a state-only mutation control.
- Native runtime-input paired benchmarks with independent fixture/checksum
  validation, retained raw samples, and explicit reporting of a rejected
  short-ASCII optimization. No runtime speedup is claimed.
- Exact protected-page coverage for 56 short-input slices around scanner
  boundaries, including empty input, unsafe bytes, and trailing backslashes.

## 0.1.1 — 2026-11-04

- Fix compiler setup incorrectly rejecting a clean Git index under locale-aware
  Bash range matching. Hidden-source index flags remain rejected, with a
  collation regression test.
- Validate the core on macOS 15 ARM64 with Apple Clang, including JIT/native
  checks, ownership rejection, independent oracles, protected pages, and native
  ASan/UBSan. Add portable `check-core`/`test-core` targets while retaining full
  Linux coverage. See [platform validation](PORTABILITY.md).
- Application-owned Linux CLI reference with fixed numeric diagnostic events,
  private bounded append delivery, checked business stdout, and real failure tests.
- Separate construction, formatting, file delivery, and application-adapter
  profiles using the reference's actual helpers.
- Compiler lifetime regression coverage for terminal logging while callers build
  or borrow data. The documented core API and runtime remain unchanged.

## 0.1.0 — 2026-11-04

First tagged source release, under Apache-2.0. Validated on Linux x86-64 with
the full Goose compiler revision in [GOOSE_REVISION](GOOSE_REVISION).

- Six emitted severities, explicit per-call filtering, level names and parsing.
- Bounded byte-safe plain lines, optional label colors, and synchronous boolean
  sinks with explicit filtered/written/error results.
- Deferred message builders and optional bounded contextual records, quoted
  string fields, and explicit sensitive-value masking.
- Independent byte and record oracles, compiler ownership/type rejection tests,
  GCC/Clang sanitizers, protected-page checks, and pinned CI.
- An application-owned file append example with error propagation, and a
  reproducible allocation/arena probe separating direct allocation calls from
  logical arena growth and minor page faults.
- Reproducible comparisons against rxi/log.c, synchronous spdlog and the direct
  Goose ecosystem reference. Scope, raw samples, and limitations are retained
  with the measurements; no universal performance or feature-parity claim.

The [README](README.md) defines the 0.1 API contract and deliberate scope limits.
Applications own I/O, storage, synchronization, and redaction policy. This
release does not add async queues, file rotation, or automatic secret detection.
