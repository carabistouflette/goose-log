# goose-log

Small, bounded, explicit logging for the
[Goose programming language](https://github.com/aardappel/goose).
Apache-2.0. Experimental API; no release yet.

Severity filtering, single-line byte-safe formatting, optional label colors,
and synchronous delivery to a caller-supplied sink. The application owns output
and reusable scratch storage. No global state, file handles, clocks, environment
access, or runtime dependencies beyond Goose's standard library.

## Quick start

Clone and run the included example without a parent workspace:

```sh
git clone https://github.com/carabistouflette/goose-log.git
cd goose-log
make setup
make check test
.toolchain/goose/build/goose run examples/hello.goose
```

For a program in a sibling directory of that clone:

```goose
import logger from "../goose-log";
import os;

fn main() {
    let config = log::Logger { .. };
    var scratch: u8[>..] = [];
    let status = log::emit(config, log::Level.Info, "Hello, Goose!", scratch) { line =>
        write_stderr(line);
        true
    };
}
```

Output: `[INFO] Hello, Goose!` followed by a newline. The import declares the
package; its API lives in `namespace log`. See [examples/hello.goose](examples/hello.goose).
Goose's `write_stderr` returns no I/O status, so this adapter always reports
success. Use an output API that reports errors when delivery must be checked.

From this checkout, run `make setup`, then `make check test`. Setup needs Git,
CMake 3.27+, a C/C++20 toolchain, and Make; tests also need Python 3.9+. On Linux,
the in-process runner needs libc development headers. An existing compiler can
be selected with `make GOOSE=/path/to/goose check test`.

Tests require Python **3.9 or newer**. Git, Bash, CMake, Make, and a working
C/C++20 toolchain are needed for a fresh setup; setup fetches the pinned Goose
source and builds it locally. No compiler binaries are distributed here.

Goose also accepts a remote dependency pinned to a published full commit. For
example, the library revision used in the recorded benchmark results is:

```goose
import logger from "carabistouflette/goose-log@e450b55dcda36ca8b197ed5f17c2da79f847d8db";
```

Use this import in place of the relative import above. It exposes the same
`log` namespace. There are no tagged releases or API stability guarantees yet.

## Tested platforms

The library is pure Goose with no platform-specific calls; applications supply
their output adapter. Actual validation is currently limited to **Linux x86-64**:
Arch Linux locally with GCC and Clang, and an Ubuntu 24.04 GitHub CI workflow configured for both compilers.
macOS, Windows, and other architectures are unverified, not promised supported.
The setup script requires Bash. The optional protected-page tests additionally
require POSIX `mprotect` and Python's `resource` module. Sanitizer tests require
GCC/Clang sanitizer runtimes. See [benchmark provenance](bench/results.md) for
the exact locally measured tool versions; CI uses the runner's installed tools.

Setup requires a full commit hash and refuses tracked edits or nonignored
untracked files in the cached compiler source. Index flags that hide source
changes (`assume-unchanged` or `skip-worktree`) are also refused. Refusals leave
local source untouched; resolve them before rerunning setup. Ignored compiler
build output is allowed. Make goals
run serially even with `-j`, because the pinned Goose compiler shares generated
C paths between builds of the same source. Use one Make invocation per checkout;
separate simultaneous invocations do not coordinate with each other.

## API and behavior

- `Logger { minimum: Level.Info, color: false }` is the default configuration.
  Levels are `Trace`, `Debug`, `Info`, `Warn`, `Error`, `Fatal`, and `Off`, in increasing order.
  `Off` disables the logger and is never an emitted severity.
- `Fatal` is a severity only: it never terminates the process.
- `level_name(level)` returns its uppercase static name; `parse_level(text)`
  returns `(level, ok)`. Parsing accepts exact ASCII names case-insensitively,
  without whitespace or aliases; failure returns `Off, false`.
- `enabled(config, level)` checks the minimum level without formatting.
- `render(config, level, message, scratch)` returns `false` when filtered,
  leaving scratch untouched. Otherwise it replaces scratch with one complete
  line and returns `true`.
- `emit(config, level, message, scratch) { line => ... }` renders and invokes
  the sink once, synchronously, with a read-only borrowed slice. Its result
  must be `bool`; optional references are rejected. A true sink
  result returns `Status.Written`; false returns `Status.SinkError`. Filtering
  returns `Status.Filtered` without calling the sink. These statuses describe
  what the sink reported; they do not imply flushing or durable storage.

Sink failure can follow partial external output. There is no retry or rollback;
the rendered line remains in scratch. A sink that needs to retain bytes must
copy them into its own storage. Goose function arguments are compile-time
generic parameters; the logger does not store a runtime callback.

The input message must not borrow from scratch, which rendering clears. Goose
checks these lifetimes; compile-failure regression tests cover both `render`
and `emit`. The line parameter is read-only; sinks must preserve captured
scratch storage while consuming it. The application coordinates
any concurrent output or scratch sharing; no locking or cross-call atomicity
is provided. Each enabled call makes one sink call, which may itself perform
multiple writes.

Arguments are evaluated before filtering. Guard expensive message construction
with `enabled` in the application:

```goose
if log::enabled(config, log::Level.Debug) {
    // Construct the expensive message here, then render or emit it.
}
```

Alternatively, `emit_lazy(config, level, scratch, build_message) { line => ... }`
calls the zero-argument message builder once only when enabled. A builder may
return owned bytes or a borrowed byte slice. Its work and allocations are
application code, outside the formatter's bounds. The sink still returns `bool`.
Goose permits one trailing function block; pass the builder by name.

## Output contract and limits

Lines have the form `[LEVEL] message\n`. Printable ASCII bytes pass through;
backslash becomes `\\`, and all remaining bytes become lowercase `\xhh`.
This is byte-oriented: Unicode is shown as escaped UTF-8 bytes, and malformed
UTF-8 is accepted as bytes. Embedded CR/LF, NUL, terminal escapes, Unicode line
separators, and invalid bytes cannot inject raw terminal controls into the
message. Escaping does not redact credentials or other sensitive content.

Only the first `MAX_MESSAGE_BYTES` (4096) source bytes are inspected. Longer
messages append `... [truncated]`; the limit counts source bytes, including
bytes of an escape or UTF-8 sequence. No escape is cut short in the output.
Empty messages are valid. A literal truncation marker in user text stays literal.

With `color: true`, only the level label is colored: bright blue for trace,
cyan for debug, green for info, yellow for warn, red for error, magenta for fatal.
The library emits a reset before the
space preceding the message. Colors are opt-in with no terminal detection.
Without colors, output contains printable ASCII and exactly one final newline.

Both public bounds are `const`, including through references. The renderer's
cap uses a direct comparison so application function overloads cannot change it.
`MAX_LINE_BYTES` is 16417: at most 8 bytes for label and space, 9 for optional
color/reset, 16384 for escaped content, 15 for the truncation marker, and 1 for
the newline. This bounds bytes appended per enabled call and work inspecting
message content, regardless of the full input length. It does not cap
caller-allocated scratch capacity, memory used constructing a message, or sink
work. Allocation failure follows Goose's runtime behavior; it is not a sink error.

## Performance and validation

Filtering is constant time and performs no buffer writes, message scanning, or
sink calls. Rendering scans at most 4096 source bytes, appending directly into
the reusable caller buffer without a temporary message copy. No allocation-free
or throughput guarantee is made.

`make check test` checks formatting and types, runs public API tests both in
process and as native binaries (including a debug build retaining every bounds
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

On systems with GCC and its sanitizer runtimes, `make test-sanitize` runs the
oracle against a standalone debug build instrumented with AddressSanitizer and
UndefinedBehaviorSanitizer, and an optimized build with the usual bounds-check
elision enabled. Diagnostics terminate the process, and the oracle verifies
the exact completed case count and rejects unexpected diagnostic output. Set
`SANITIZER_CC=clang` to select Clang instead; the wrapper requires GCC-compatible
sanitizer flags. CI runs both builds under both GCC and Clang.

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
builds; CI runs them under GCC and Clang. Protection covers the remaining whole
pages inside the backing array; it does not cover its final partial page.

`make bench BENCH_ITERATIONS=100000` builds a native GCC `-O2` benchmark with
empty, short/maximum printable, backslash-heavy, mixed binary, escape-heavy,
oversized, filtered, and checksum-consuming sink calls. It reuses scratch and
consumes output in a checksum; output reports the median and min/max of seven
samples in local nanoseconds per call, including loop/checksum overhead and
excluding external I/O. Rendering cases warm the scratch buffer before timing.
The threshold case uses a runtime minimum (default `Error`) to avoid assuming
filter rejection at compile time; `.build/bench 100000 0` selects `Debug` instead
and exercises accepted calls in that same loop. Treat these as local measurements
rather than cross-library or production claims.
Fixed messages and configurations allow compiler specialization, so these
rows do not represent every runtime-input or configuration pattern.
See [recorded results and reproduction steps](bench/results.md). They are local
measurements, not cross-library comparisons or production throughput promises.

The first version deliberately excludes file rotation, asynchronous queues,
JSON output, and automatic formatting of application objects.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and commit standards.
[SECURITY.md](SECURITY.md) describes vulnerability reporting and the trust model.
[GOOSE_REVISION](GOOSE_REVISION) pins the compiler used in CI.
Compatibility with other compiler revisions is not guaranteed.

[Apache-2.0](LICENSE). Copyright 2026 goose-log contributors.
See [NOTICE](NOTICE) and [third-party notes](THIRD_PARTY_NOTICES.md).
