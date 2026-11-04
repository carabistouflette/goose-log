# Optional UTC record consumer

This application-owned adapter composes goose-log's existing `Record.timestamp`
with [goose-time](https://github.com/carabistouflette/goose-time) at the reviewed
experimental v0.1.0 commit `343887caeee0a1f4e2e536ff322fcafb454e11bd`.
It does not extend the core logging interface. `logger.goose` and its documented
output formats, filtering, limits and dependency graph are unchanged.

From a standalone goose-log checkout with the pinned compiler:

```sh
make test-utc
.toolchain/goose/build/goose run examples/utc/main.goose
```

The optional entrypoints fetch that full-commit dependency through Goose's normal
package cache on first use (network/Git access required then). Core imports and
`make check-core test-core` do not fetch or depend on goose-time. The optional
consumer is validated on Linux x86-64; existing core macOS coverage does not
establish platform coverage for this consumer.

The helper `utc.goose` expects its root entrypoint to declare both the logger
and time sourced imports, as [main.goose](main.goose) does. Copying the helper
alone does not install dependencies or acquire a clock.

`utc_log::emit(config, level, message, timestamp, scratch, clock) { line => ... }`
returns the existing `log::Status`. The clock returns an `i64` count of Unix
nanoseconds and the sink returns `bool`. Both callbacks are caller-owned.

- Filtering occurs before the adapter reads message bytes, samples the clock,
  or changes either builder. Filtered calls preserve both builders and invoke
  neither callback. Function arguments and message construction are still
  evaluated by callers before entering this non-lazy function.
- An enabled call samples the clock exactly once, replaces timestamp storage
  with canonical UTC, and sends one complete line to the sink exactly once.
  Full signed-i64 Unix-nanosecond samples are valid in goose-time's range, so
  conversion/formatting cannot reject such a sample. Clock acquisition errors
  and callback exceptions/failures outside the boolean sink remain caller policy.
- Timestamps use uppercase T/Z, 20..30 ASCII bytes, fractional nanoseconds with
  trailing zeroes removed. They fit inside the core's 64-byte timestamp limit.
  Example: `[INFO] timestamp="1970-01-01T00:00:00Z" application started` plus LF.
- Timestamp and line builders must be distinct. Message input cannot borrow
  either mutable builder. The compiler enforces lifetimes; the sink borrows
  the complete line synchronously and must copy bytes it wants to retain.
- A false sink result returns `SinkError`. A sink may already have produced
  external output. The adapter retains both formatted buffers and never retries,
  resamples, rolls back, or claims durable/atomic delivery.

`main.goose` uses the standard-library `os` module’s `time_ns()` and writes stderr.
The standard `write_stderr` reports no I/O status, so this example's sink always
returns true; replace it with an error-reporting sink when delivery matters.
Wall-clock time can jump and must not be used as a monotonic deadline.

The timestamp builder and record line can be reused across calls. There are no
new global clocks or dynamic callback objects. Allocation follows builder growth
and Goose runtime behavior; this is not an allocation-failure recovery interface.
Caller clock and sink work are outside the formatter's byte/work bounds.

[Validation evidence](VALIDATION.md) records the checks and limitations.
Tests inject deterministic samples, validate exact bytes and callback counts,
and exercise compiler ownership rejection. `make test-utc-sanitize` adds native
ASan/UBSan (`SANITIZER_CC=gcc` or `clang`). Component measurements separately account for optional clock, output and
checksum work.
