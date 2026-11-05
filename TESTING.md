# Testing

Use the compiler commit in [GOOSE_REVISION](GOOSE_REVISION). Setup requires
Bash, Git, Make, CMake 3.27+, C and C++20 compilers and Linux libc development
headers (or Xcode command-line tools on macOS). Tests need Python 3.9+;
protected-page tests use POSIX `mprotect` and Python's `resource` module.

```sh
make setup
make check-core test-core
# Linux application examples and profiling sources:
make check test
# Optional UTC example; fetches its pinned goose-time dependency:
make test-utc
```

With an existing compiler, use `make GOOSE=/absolute/path/to/goose check-core test-core`.
Use the pinned revision; other compiler versions require separate validation.
[Platform coverage](PORTABILITY.md) lists the exact hosted runs and limits.

## Compiler setup and parallel builds

Setup requires a full commit hash and refuses tracked edits or nonignored
untracked files in the cached compiler source. Index flags that hide source
changes (`assume-unchanged` or `skip-worktree`) are also refused. Refusals leave
local source untouched; resolve them before rerunning setup. Ignored compiler
build output is allowed. Make goals
run serially even with `-j`, because the pinned Goose compiler shares generated
C paths between builds of the same source. Use one Make invocation per checkout;
separate simultaneous invocations do not coordinate with each other.

## What the checks cover

`make check-core test-core` checks formatting and types, runs public API tests
both in process and as native binaries (including a debug build retaining every bounds
check), runs the example, and checks compiler rejection
of input/output aliasing and sink mutation. Tests exercise every severity/minimum
pair, all 256 byte values, colors, truncation boundaries, worst-case size, buffer
reuse, and sink failures.

The suite also runs 1792 deterministic cases against an independent Python byte
oracle in normal and debug native builds. Cases include the full configuration
matrix, random binary data, escape-heavy input, cap boundaries, and 1 MiB
messages. The same buffers are reused across accepted and filtered calls.
Consumer regression tests cover application overloads and reject reference
mutation of the safety limits.

The [randomized sequence suite](tests/SEQUENCES.md) mixes plain/contextual/lazy
calls on shared scratch and checks independent bytes, statuses, builder/sink
counts and retained copies. `make test-sequences` runs normal/debug/JIT drivers;
`make test-sequences-sanitize` adds standalone debug/optimized ASan/UBSan.
Both are included in the existing CI targets. Failures retain seeded fixtures
and support bounded operation-deletion reduction.

On systems with GCC or Clang sanitizer runtimes, `make test-sanitize` runs the
oracle against a standalone debug build instrumented with AddressSanitizer and
UndefinedBehaviorSanitizer, and an optimized build with the usual bounds-check
elision enabled. Diagnostics terminate the process, and the oracle verifies
the exact completed case count and rejects unexpected diagnostic output. Set
`SANITIZER_CC=clang` to select Clang instead; the wrapper requires GCC-compatible
sanitizer flags. Linux CI runs both builds under both GCC and Clang; macOS CI
uses Apple Clang with `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1`.

Goose allocates arrays within custom mmap-backed data stacks. ASan does not
poison every logical array boundary or lifetime inside these regions, so it
cannot independently detect every such overrun. Sanitizers supplement Goose's
bounds/lifetime checks, exact-output oracle, and physical protected-page tests.

On POSIX systems, `make test-guarded` places inaccessible pages immediately
after the 4096-byte readable prefix, and checks that rendering leaves the tail
untouched. Filtered calls receive a message starting on inaccessible memory
and must leave scratch unchanged without calling the sink. The runner first
requires an intentional protected read to fault, distinguishing a working
guard from unrelated setup errors. It tests both optimized and debug native
builds; Linux CI runs them under GCC and Clang, macOS CI under Apple Clang.
Protection covers the remaining whole pages inside the backing array; it does
not cover its final partial page.

See [benchmarks](bench/README.md) for measurement commands and scope.
