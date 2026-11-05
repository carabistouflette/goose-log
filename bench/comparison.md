# Synchronous logging feature comparison

Reviewed 2026-11-04 against primary sources. The initial feature review used
published goose-log `b4c664b3c41179fb38b25e98929891283318bd8f`. The updated
implementation below is pinned to `5c5db8fd5fe733e51e5230def818a336a367e069`:
the measured API has six severities, deferred builders, bounded metadata/string
fields and explicit sensitive-field masking. The old single-library
[results](results.md) retain their original source pin; the new
[measured comparisons](compare/RESULTS.md) use the updated implementation.
Sources: [README][gl-readme], [implementation][gl-code], [benchmark][gl-bench].

## Compared projects

The measured baselines are rxi/log.c for a small synchronous C logger, spdlog for
configurable sinks, and Macho0x/goose-logger for a Goose record renderer. The
Macho path includes timestamp formatting and redaction, so its rows use a
separate logical-record comparison. Rust log/env_logger and Go slog are feature
references here, not measured backends. Versions below are fixed source-review
snapshots, not a list of current releases.

Goose-log's six severities, lazy builders, bounded metadata and explicit field
masking cover a small synchronous API. Async queues, rotation, global sinks and
automatic secret detection remain outside it. See [current API](../API.md) and
[checked measurement source comparisons](CURRENTNESS.md).

## Ecosystem identification and search limits

“Goose” here means [aardappel/goose][goose], not the Block coding agent, Go database migrations, or the Go-to-Coq Goose project. Go `slog` is explicitly a cross-language reference.

At the inspected Goose compiler revision, `stdlib` supplies formatting helpers and `os::write_stdout`/`write_stderr`, but no dedicated severity-based logging module. The stdout/stderr functions return no I/O result. The inspected upstream blessed-package list contains graphics, audio, UI and physics, not a logger. These are useful application primitives, not a competing logging facade/backend. Sources: [pinned stdlib/os][goose-os], [stdlib/std][goose-std], [upstream tree][goose-tree], [blessed packages][goose-blessed].

GitHub repository searches for [`"aardappel/goose" log in:readme`](https://api.github.com/search/repositories?q=%22aardappel%2Fgoose%22%20log%20in%3Areadme) and [`goose logger in:name,description`](https://api.github.com/search/repositories?q=goose%20logger%20in%3Aname%2Cdescription), plus upstream package docs/tree inspection, found [Macho0x/goose-logger][ml-readme]. Its own README explicitly targets aardappel's language, and its source confirms that relationship through Goose imports and APIs. The former query did not find every relevant project, so search absence is not evidence of absence. Goose's official [package documentation][goose-packages] says packages are fetched directly from repositories and there is no registration registry. An exhaustive catalog of private, unindexed, embedded application or newly published loggers is unknown. No claim that goose-log is the only Goose logger is justified.

## Reviewed versions and licenses

Release information was checked against official GitHub release endpoints/pages; commit IDs were resolved through official repository commit APIs. Versions below are comparison pins, not promises about future latest releases. The dates are release publication dates unless stated otherwise.

| Project / layer | Reviewed release or snapshot | Exact commit | License from project source |
| --- | --- | --- | --- |
| goose-log: facade + renderer + sink bridge | implementation snapshot; no tagged release | `5c5db8fd5fe733e51e5230def818a336a367e069` | [Apache-2.0][gl-license] |
| Macho0x/goose-logger: process-log renderer/backend | [v0.3.4][ml-release], 2026-11-03 | `50695a3df0eb5a1048a4b183538d59f43f5eb279` | [Apache-2.0][ml-license] |
| rxi/log.c: small synchronous frontend/backend | Header says `0.1.0`; no tags and no GitHub release returned; commit dated 2020-06-20 | `f9ea34994bd58ed342d2245cd4110bb5c6790153` | [MIT][rxi-code] |
| gabime/spdlog: frontend + configurable sinks | [v1.17.0][spd-release], 2026-01-04 | `79524ddd08a4ec981b7fea76afd08ee05f83755d` | [MIT; bundled fmt has its own MIT notice][spd-license] |
| rust-lang/log: facade only | [v0.4.35][rust-release], 2026-10-30 | `a46450ba763280c29d35b53aa8ad0ff1fc1d78d0` | [MIT OR Apache-2.0][rust-manifest] |
| rust-cli/env_logger: backend for `log` | [v0.11.11][env-release], 2026-06-25 | `b4d3f2b8dd3f1c3362f07da8f6f4a30c701358cf` | [MIT OR Apache-2.0][env-manifest] |
| Go log/slog: frontend + handler API + built-in handlers | [Go 1.27.3][go-release]; source commit dated 2026-10-20 | `2aae1000ea1d4b28923b96db28acf4e3b99d6aff` | [BSD-3-Clause][go-license] |

Goose itself is pinned locally to `eadca409f68210893f366e60d0c2f0dc29a339be`; do not silently update it for this comparison. Its [official releases][goose-releases] also list v2026.3 (2026-10-21). The selected Macho adapter paths compile and run against this local pin; this does not establish compatibility of every upstream API or test suite. License labels describe the inspected upstream sources; any later vendoring must preserve their actual notices and review selected dependencies.

## Feature gap matrix

Cells describe the reviewed sources, not every possible third-party plugin. “Application” means possible outside the library, not built-in parity. `log` is not treated as a renderer: the env_logger column below describes the combined Rust stack where appropriate.

### Core facade and event construction

| Feature | goose-log snapshot | Macho0x/goose-logger v0.3.4 | rxi/log.c | synchronous spdlog v1.17.0 | Rust log + env_logger | Go slog |
| --- | --- | --- | --- | --- | --- | --- |
| Severities | Trace, Debug, Info, Warn, Error, Fatal; Off disables; Logger defaults to Info | Trace through Fatal (six); no Off enum | Trace through Fatal (six); no Off enum | trace, debug, info, warn, err, critical; off | trace, debug, info, warn, error; Off filter, no Fatal | Debug, Info, Warn, Error; numeric custom levels; no built-in Trace/Fatal |
| Runtime filtering | Per-call Logger minimum; `enabled` | Explicit `levels::enabled`; convenience writers do not enforce a configured floor | Global stderr floor; independent callback floors | Logger and sink floors | Facade maximum; backend target/module directives | `Handler.Enabled`; built-in minimum/LevelVar |
| Compile-time filtering | No logging-level switch; optimizer may specialize | No logging-level switch seen | No level-removal macro switch | `SPDLOG_ACTIVE_LEVEL` with logging macros | Cargo max-level/release-max-level features | No dedicated logging-level build switch |
| Message construction | Prebuilt byte slice or emit_lazy builder after filtering; manual enabled guard also available | Already-built text; manual guard | printf formatting after routing; C argument expressions already evaluated | Formatting after level check unless backtrace enabled; argument expressions already evaluated | Macros guard format-argument construction by static/runtime maximum; backend can reject later | Call arguments eager; `Enabled` guard or `LogValuer` defers expensive value computation |
| Metadata | Optional caller-supplied timestamp text, target, file and u32 line | Caller-supplied file/row; timestamp; field builders; optional run-id helper | File/line macros; lazily initialized local time | Name, time, thread, explicit source_loc/macros | Record target/module/file/line; backend timestamp/format controls | Record time/PC; optional source output; context passed to handlers |
| Structured fields/context | Up to eight bounded quoted string fields; explicit sensitive-value flag; not typed JSON | Text `begin`/`field`; domain-specific key/symbol rules | printf text only | fmt/custom types and MDC; not a slog-style typed field facade | Optional `log/kv` and env_logger `kv` formatting | Typed attrs, groups, `With`, `WithGroup` |
| Fatal/critical terminates? | No: Fatal is a severity only | No: `fatal` delegates to write | No: macro delegates to log_log | `critical` is a severity, not an exit API | No Fatal | No Fatal; custom severity does not imply exit |

Matrix evidence: [goose-log source][gl-code]; [Macho logger][ml-code], [levels][ml-levels], [emit][ml-emit]; [rxi header][rxi-header] and [implementation][rxi-code]; [spdlog README][spd-readme] and [logger implementation][spd-logger]; [Rust facade source][rust-code], [macros][rust-macros], [manifest][rust-manifest]; [env_logger implementation][env-code]; [slog docs][slog-doc], [logger][slog-logger], [handlers][slog-handler].

### Backend, rendering and output ownership

| Feature | goose-log snapshot | Macho0x/goose-logger | rxi/log.c | synchronous spdlog | log facade / env_logger backend | Go slog built-in handlers |
| --- | --- | --- | --- | --- | --- | --- |
| Render without external I/O | render / render_record replace caller scratch | `record`, appends to caller buffer; no newline | Custom callback must implement rendering | Custom sink/formatter or memory sink | Facade has no renderer; env_logger custom formatter/pipe | Custom Handler or writer buffer |
| Default output and lifetime | No default sink; one synchronous borrowed complete line | `write`: fresh line buffer, stdout write then separate newline write | Default stderr plus up to 32 callbacks; callback borrows event/va_list | Caller-created logger/sinks; borrowed event on synchronous path | Global facade install optional for calls; backend can be built separately; thread-local format buffer | Logger holds Handler; text/JSON handlers own formatting and writer integration |
| Byte/control safety | All non-ASCII/nonprintable bytes escaped; backslash doubled; exactly one final newline | Secret redaction; field quoting; not goose-log's universal byte escaping | printf text; embedded NUL/string/control limitations | Text by default; explicit binary-to-hex helper | Formatting text; no universal goose-log escape contract | Text quoting / JSON escaping, different Unicode and record semantics |
| Work/message bounds | 4096 message bytes; plain line 16417; separately capped metadata/fields, record line 28592 | No equivalent input cap in reviewed record/sanitizer path | No equivalent cap | No equivalent default cap | No facade cap; no equivalent backend default cap | No equivalent default cap |
| Secret redaction | Explicit sensitive-field mask only; no automatic pattern detector | Built-in multi-pass rules incl. URLs, tokens, PEM and BIP-39 | None built in | Custom extension | Custom formatter/backend | `LogValuer` / ReplaceAttr extension |
| Color and patterns | Opt-in label colors; fixed format | No ANSI color option seen; fixed record format | Compile-time ANSI option for stderr; fixed built-in formats | Configurable patterns, optional color sinks | Facade none; backend styles/custom formatter | No built-in ANSI option; TextHandler/JSONHandler |
| Delivery errors | Filtered/Written/SinkError returned per call; no rollback | stdout API returns no result; no per-call status | log_log/callback return void; built-in stdio results ignored | Error handler/exception configuration; no bool delivery status | Facade returns unit; env_logger discards format/print errors in its logging path | Handler.Handle returns error; Logger methods discard it |
| Threading/atomicity | Caller coordinates output and scratch | No lock or atomic whole-record write in reviewed writer | Optional caller-supplied lock around dispatch | `_st` no sink locking; `_mt` locking | Facade implementer thread safety; env_logger thread-local formatting and writer behavior | Built-in handlers lock around one writer call per record |
| Files/fanout/flush | Application sink; no owned files/flush | stdout; caller can route record buffer; no general fanout/flush interface seen | FILE* and callbacks; per-destination floor; built-in outputs fflush each event | Multiple sinks, files, rotation, flush policy | Facade flush hook; env_logger stdout/stderr/custom pipe; its Log::flush implementation is empty | io.Writer; no general rotation/flush manager in TextHandler/JSONHandler |
| Async and spans/tracing | Neither | Neither; PORTING explicitly excludes tracing subscriber | Neither | Async available separately; backtrace buffer is not distributed tracing | Facade backend-dependent; env_logger synchronous, not a span system | Custom handler can extend; built-ins synchronous, no span lifecycle |

Backend evidence: sources above plus [Macho sanitization][ml-sanitize], [porting notes][ml-porting], [env_logger backend source][env-code], and [slog common handler][slog-handler]. “No equivalent cap” is limited to these reviewed default paths; it does not rule out application adapters. Redaction and escaping solve different problems: neither implies the other.

## Semantic and performance fairness requirements

1. **Publish separate comparison questions.** A native-configuration row measures each product's actual contract and must list unequal work. An equal-contract row must match output bytes and semantics, including level label, newline, escape expansion, truncation, metadata, and delivery. If an adapter adds escaping to rxi/log.c, identify it as “log.c + comparison adapter,” not an upstream feature. Run exact-output checks before timing.
2. **Use real dispatch for log.c.** Set quiet mode to suppress stderr, install exactly one custom callback, and call its public logging API. Its `init_event` still calls `time`/`localtime` before every accepted callback even if the adapter ignores time. Its filtered path may still invoke the configured lock and traverse callback registration. Report these residual costs; do not remove them silently. `log_set_level` only controls stderr, so set callback floors too. Fatal has no exit cost. Source: [log.c][rxi-code].
3. **Respect binary input contracts.** goose-log accepts arbitrary byte slices, including NUL. printf `%s` does not. For embedded-NUL and binary corpora, a log.c callback adapter needs an explicitly length-bearing interface/fixture convention; feeding a pre-escaped or truncated message outside its timed interval shifts work unfairly. Cap at the same source-byte count, not an output-byte count. Report an unadapted ASCII-only common-subset test separately.
4. **Separate render, sink and I/O.** First measure rendering/dispatch into reusable memory with the same checksum consumer. Do not compare goose-log memory rendering with log.c's stderr/file callbacks (which timestamp, format and flush), Macho's stdout writes, or spdlog file sinks. Then optionally compare identical buffered file/pipe sinks, same write completion/error/flush policy. A null callback that skips rendering is not a renderer benchmark. One sink call is not necessarily one syscall, atomic output, flush, or durable storage.
5. **Control extra features explicitly.** Turn off colors and optional metadata on both sides for the minimal case. spdlog's synchronous `_st` path is the closest locking policy; `_mt` belongs in a separate shared-output case with equivalent caller locking for goose-log. Disable spdlog backtrace, async, periodic flushing and global registry lookup in the minimal path. A `%v` pattern removes visible metadata but the normal record constructor still acquires time and, unless `SPDLOG_NO_THREAD_ID` is defined, thread ID. Disclose those costs and any build switches. Sources: [spdlog README][spd-readme], [logger][spd-logger] and [record constructor][spd-record].
6. **Treat Macho's extra work honestly.** `emit::record` includes supplied-timestamp calendar formatting, file/row formatting and `sanitize::text`; it appends and does not add a newline. `write` also acquires time, allocates a fresh line and makes two stdout calls. Compare those as different workloads unless goose-log gains matching semantics. Do not disable redaction or omit timestamp cost and call the result full parity. Its [existing benchmark][ml-bench] creates fresh record storage; goose-log's [benchmark][gl-bench] warms and reuses scratch. Those numbers are not directly comparable.
7. **Separate eager work from deferred work.** Measure a prebuilt-message call, a disabled call with expensive message construction, and an explicitly guarded/deferred equivalent. Count builder calls to confirm zero when filtered. Rust macros only guard through their maximum-level checks before a backend's later filtering; target/regex rejection is not a promise that arbitrary expensive arguments were never evaluated. C/C++ and Go function arguments are eager; deferred formatting is not deferred argument evaluation. Sources: [Rust macros][rust-macros], [spdlog logger][spd-logger], [slog performance docs][slog-doc].
8. **Make optimization opportunities comparable.** Use runtime-selected levels, configuration and message fixtures alongside literal-input rows; preserve generated output observability. Match full-byte validation outside timing and equivalent checksum work inside it. Use the same C toolchain/optimization level for native Goose and C/C++; record LTO, assertions, bounds-check configuration and build mode. Do not compare Goose's in-process/TinyCC execution with an optimized native competitor. Fixed inputs can legitimately specialize, but label that workload.
9. **Cover contracts, not just short ASCII.** Include empty, short and 4096-byte printable, all 256 bytes, backslashes, Unicode UTF-8, invalid UTF-8, NUL/CR/LF/ANSI, exact cap and cap+1, and oversized inputs. Test every threshold/severity pair and callback failure separately. Measure cold and reused storage separately; bounded output does not prove allocation-free behavior.
10. **Use paired measurements and modest conclusions.** Match sample counts, iteration counts, warmups and sink; alternate order and repeat isolated runs on the same machine. Record CPU, OS, clocks, compiler revisions/flags, source hashes, affinity/power policy and concurrent load. Report median/min/max batch averages as batch averages, not tail latencies. Include code and raw output. Existing goose-log results have seven batches, checksum/loop overhead, warm reusable storage, no external I/O and no CPU/frequency controls; their render and emit cases even use different severity patterns, so their difference does not isolate callback overhead. Source: [results.md](results.md).

## Current scope

The [API reference](../API.md) defines six emitted severities, lazy builders,
caller-supplied metadata, bounded string fields and explicit sensitive-value
masking. The [examples](../README.md#examples) show stderr, checked file delivery
and an optional UTC adapter.

Typed JSON fields, environment filter directives, automatic secret detection,
rotation, asynchronous queues, global sink management and tracing spans are
outside the core. A custom adapter does not make those built-in features.

## Measurement and scope boundaries

- The [two retained comparison series](compare/RESULTS.md) measure pipeline time.
  They do not measure allocation/syscall counts, durability or multithreaded I/O.
  Separate probes are listed in the [benchmark index](README.md).
- The direct Goose reference's exact timestamp/redaction helpers are used on
  both logical-record benchmark paths. This is an external policy adapter,
  not a built-in automatic secret detector or full upstream feature parity.
- No exhaustive ecosystem search or security audit of competitors is claimed.
  Secret-redaction coverage and arbitrary-input behavior are not established by
  a short benchmark fixture or by reading a feature list.
- Async queues, rotation, implicit clocks/source capture, global sink registries,
  typed JSON, environment directive parsing, crash hooks, and spans remain absent.
  Caller-owned adapters are integration capabilities, not built-in parity.
- Compare matched output profiles separately from logical-record native formats.
  Preserve the legacy byte contract and test each enabled feature independently.

[gl-readme]: https://github.com/carabistouflette/goose-log/blob/5c5db8fd5fe733e51e5230def818a336a367e069/README.md
[gl-code]: https://github.com/carabistouflette/goose-log/blob/5c5db8fd5fe733e51e5230def818a336a367e069/logger.goose
[gl-bench]: https://github.com/carabistouflette/goose-log/blob/e450b55dcda36ca8b197ed5f17c2da79f847d8db/bench/bench.goose
[gl-license]: https://github.com/carabistouflette/goose-log/blob/5c5db8fd5fe733e51e5230def818a336a367e069/LICENSE
[gl-contrib]: https://github.com/carabistouflette/goose-log/blob/5c5db8fd5fe733e51e5230def818a336a367e069/CONTRIBUTING.md
[goose]: https://github.com/aardappel/goose
[goose-releases]: https://github.com/aardappel/goose/releases
[goose-tree]: https://github.com/aardappel/goose/tree/335fddc13dc74666398ffe160ec8a8f2958329d0/stdlib
[goose-packages]: https://github.com/aardappel/goose/blob/335fddc13dc74666398ffe160ec8a8f2958329d0/docs/packages.md
[goose-blessed]: https://github.com/aardappel/goose/blob/335fddc13dc74666398ffe160ec8a8f2958329d0/src/blessed.txt
[goose-os]: https://github.com/aardappel/goose/blob/eadca409f68210893f366e60d0c2f0dc29a339be/stdlib/os.goose
[goose-std]: https://github.com/aardappel/goose/blob/eadca409f68210893f366e60d0c2f0dc29a339be/stdlib/std.goose
[ml-readme]: https://github.com/Macho0x/goose-logger/blob/50695a3df0eb5a1048a4b183538d59f43f5eb279/README.md
[ml-release]: https://github.com/Macho0x/goose-logger/releases/tag/v0.3.4
[ml-license]: https://github.com/Macho0x/goose-logger/blob/50695a3df0eb5a1048a4b183538d59f43f5eb279/LICENSE
[ml-code]: https://github.com/Macho0x/goose-logger/blob/50695a3df0eb5a1048a4b183538d59f43f5eb279/logger.goose
[ml-levels]: https://github.com/Macho0x/goose-logger/blob/50695a3df0eb5a1048a4b183538d59f43f5eb279/levels.goose
[ml-emit]: https://github.com/Macho0x/goose-logger/blob/50695a3df0eb5a1048a4b183538d59f43f5eb279/emit.goose
[ml-sanitize]: https://github.com/Macho0x/goose-logger/blob/50695a3df0eb5a1048a4b183538d59f43f5eb279/sanitize.goose
[ml-porting]: https://github.com/Macho0x/goose-logger/blob/50695a3df0eb5a1048a4b183538d59f43f5eb279/PORTING.md
[ml-bench]: https://github.com/Macho0x/goose-logger/blob/50695a3df0eb5a1048a4b183538d59f43f5eb279/bench.goose
[rxi-header]: https://github.com/rxi/log.c/blob/f9ea34994bd58ed342d2245cd4110bb5c6790153/src/log.h
[rxi-code]: https://github.com/rxi/log.c/blob/f9ea34994bd58ed342d2245cd4110bb5c6790153/src/log.c
[spd-release]: https://github.com/gabime/spdlog/releases/tag/v1.17.0
[spd-readme]: https://github.com/gabime/spdlog/blob/79524ddd08a4ec981b7fea76afd08ee05f83755d/README.md
[spd-license]: https://github.com/gabime/spdlog/blob/79524ddd08a4ec981b7fea76afd08ee05f83755d/LICENSE
[spd-logger]: https://github.com/gabime/spdlog/blob/79524ddd08a4ec981b7fea76afd08ee05f83755d/include/spdlog/logger.h
[rust-release]: https://github.com/rust-lang/log/releases/tag/v0.4.35
[rust-manifest]: https://github.com/rust-lang/log/blob/a46450ba763280c29d35b53aa8ad0ff1fc1d78d0/Cargo.toml
[rust-code]: https://github.com/rust-lang/log/blob/a46450ba763280c29d35b53aa8ad0ff1fc1d78d0/src/lib.rs
[rust-macros]: https://github.com/rust-lang/log/blob/a46450ba763280c29d35b53aa8ad0ff1fc1d78d0/src/macros.rs
[env-release]: https://github.com/rust-cli/env_logger/releases/tag/v0.11.11
[env-manifest]: https://github.com/rust-cli/env_logger/blob/b4d3f2b8dd3f1c3362f07da8f6f4a30c701358cf/Cargo.toml
[env-code]: https://github.com/rust-cli/env_logger/blob/b4d3f2b8dd3f1c3362f07da8f6f4a30c701358cf/src/logger.rs
[go-release]: https://go.dev/dl/#go1.27.3
[go-license]: https://github.com/golang/go/blob/2aae1000ea1d4b28923b96db28acf4e3b99d6aff/LICENSE
[slog-doc]: https://github.com/golang/go/blob/2aae1000ea1d4b28923b96db28acf4e3b99d6aff/src/log/slog/doc.go
[slog-logger]: https://github.com/golang/go/blob/2aae1000ea1d4b28923b96db28acf4e3b99d6aff/src/log/slog/logger.go
[slog-handler]: https://github.com/golang/go/blob/2aae1000ea1d4b28923b96db28acf4e3b99d6aff/src/log/slog/handler.go
[spd-record]: https://github.com/gabime/spdlog/blob/79524ddd08a4ec981b7fea76afd08ee05f83755d/include/spdlog/details/log_msg-inl.h
