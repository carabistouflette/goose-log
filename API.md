# API reference

Import the package as `logger`; its namespace is `log`. See the
[quickstart](README.md#quick-start) for a complete program. This contract is
shared by latest main and released v0.1.3; see [release history](CHANGELOG.md).

The documented types, functions, constants, byte formats, limits and ownership
rules form the 0.1 API. Patch releases preserve them. Before 1.0, an intentional
API or output change requires a new minor version. Undocumented helpers are
implementation details.

## Levels and plain messages

- `Logger { minimum: Level.Info, color: false }` is the default configuration.
  Levels are `Trace`, `Debug`, `Info`, `Warn`, `Error`, `Fatal`, and `Off`, in increasing severity order.
  `Off` disables the logger and is never an emitted severity.
  Enum representation tags preserve historical values; use `enabled` for filtering.
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

## Types and defaults

`Field` contains `key` and `value` byte slices (empty by default), and
`sensitive: bool = false`. `Record` defaults to Info, empty message/timestamp/
target/file text, `line: u32 = 0`, and no fields. `Status` has Filtered, Written
and SinkError variants. The logger's default minimum is Info; a bare `Level`
value defaults to Debug for compatibility. Use named variants for filtering,
not their enum representation order.

## Contextual records

The plain `render`/`emit` format remains unchanged. `Record` adds opt-in,
bounded context and string fields; bind it to a local before passing it to
`render_record(config, record, scratch)` or `emit_record(config, record, scratch)`.
These functions borrow a read-only `Record&`. They have the same filtering,
buffer replacement, boolean sink, and status rules as their plain counterparts.

Inside `main`, after creating `config` and `scratch` as in the quickstart:

```goose
let fields = [log::Field { key: "account", value: "demo" },
    log::Field { key: "token", value: "application-provided", sensitive: true }];
let record = log::Record { level: log::Level.Info, message: "request complete",
    target: "http", file: "app.goose", line: 42, fields: fields };
log::render_record(config, record, scratch);
```

Rendered line: `[INFO] target="http" file="app.goose" line=42 "account"="demo" "token"="***" request complete`
followed by a newline. Optional `timestamp` is caller-formatted text: there is
no implicit clock read, date parser, or automatic source-location capture.
`line` is a `u32`; zero omits it. Empty timestamp/target/file values are omitted.
Timestamp, target and file values, and field keys/values, are quoted; `line` is
unquoted decimal. Quotes, backslashes, controls and non-ASCII bytes are escaped. Field keys remain quoted even when
they match a reserved metadata name. This is a text format, not JSON.

Timestamp and target inspect at most 64 source bytes each; file inspects at
most 256. At most eight arbitrary fields are inspected, with 64 key bytes and
256 value bytes per field. Each truncated string gets `... [truncated]` inside
its closing quote; excess fields add `[fields truncated] `. Message truncation
still uses 4096 bytes. `MAX_RECORD_LINE_BYTES` is **28592**, including all
syntax, truncation markers, a maximum line number, optional colors, and newline.
The plain `MAX_LINE_BYTES` remains 16417. All borrowed record text and field
storage must remain alive and must not alias output being replaced.

`sensitive: true` replaces the entire value with `"***"` without inspecting it.
This is explicit field masking, **not** automatic secret detection: unmarked
fields and message text are not redacted. Applications choose their redaction
policy before calling the logger. See [the comparison](bench/comparison.md)
for features that remain outside this synchronous core.

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

The public bounds are `const`, including through references. The renderer's
cap uses a direct comparison so application function overloads cannot change it.
`MAX_LINE_BYTES` is 16417: at most 8 bytes for label and space, 9 for optional
color/reset, 16384 for escaped content, 15 for the truncation marker, and 1 for
the newline. This bounds bytes appended per enabled call and work inspecting
message content, regardless of the full input length. It does not cap
caller-allocated scratch capacity, memory used constructing a message, or sink
work. Allocation failure follows Goose's runtime behavior; it is not a sink error.

## Named bounds

| Constant | Value | Meaning |
| --- | ---: | --- |
| `MAX_MESSAGE_BYTES` | 4096 | Source message bytes inspected |
| `MAX_LINE_BYTES` | 16417 | Maximum new plain line, including color/newline |
| `MAX_TIMESTAMP_BYTES` | 64 | Source timestamp bytes inspected |
| `MAX_TARGET_BYTES` | 64 | Source target bytes inspected |
| `MAX_FILE_BYTES` | 256 | Source filename bytes inspected |
| `MAX_FIELD_KEY_BYTES` | 64 | Source bytes per inspected field key |
| `MAX_FIELD_VALUE_BYTES` | 256 | Source bytes per nonsensitive field value |
| `MAX_FIELDS` | 8 | Fields inspected |
| `MAX_RECORD_LINE_BYTES` | 28592 | Maximum new contextual line |

These bounds apply to enabled rendering. A filtered call can retain a larger
previous line in scratch; it does not replace or shorten that line.
