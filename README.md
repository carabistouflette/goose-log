# goose-log

Logging for the [Goose programming language](https://github.com/aardappel/goose).
It filters by severity, escapes arbitrary message bytes into one line, and calls
a sink supplied by your program. Your program owns the configuration, scratch
buffer and output. The core reads no clocks or environment and owns no files.

Apache-2.0. Latest release: [v0.1.3](https://github.com/carabistouflette/goose-log/releases/tag/v0.1.3).
The API is experimental before 1.0. This page describes main; its core API and
implementation match v0.1.3. Main adds Linux ARM64 CI and benchmark evidence
that are not in that tag.

## Quick start

Install Bash, Git, Make, CMake 3.27+, a C compiler and a C++20 compiler. Linux
also needs libc development headers; macOS needs Xcode command-line tools.
Tests need Python 3.9+.

```sh
git clone https://github.com/carabistouflette/goose-log.git
cd goose-log
make setup
.toolchain/goose/build/goose run examples/hello.goose
```

This prints `[INFO] Hello, Goose!` and a newline to stderr. Setup builds the
[pinned Goose compiler](GOOSE_REVISION); no compiler binary is bundled.

For a program saved beside the `goose-log` directory:

```goose
import logger from "./goose-log";
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

The package import is `logger`; the API namespace is `log`. For an immutable
released dependency, replace the relative import with:

```goose
import logger from "carabistouflette/goose-log@e93a71c0ff2f852b2d68f0a2c70f25ded3e8893a";
```

The remote import needs Git/network access on first use.

Goose's `write_stderr` returns no I/O status, so this example reports success
unconditionally. Use an error-reporting output API when delivery matters.

## API and limits

- Six severities: Trace, Debug, Info, Warn, Error and Fatal. The default minimum
  is Info; Off disables output. Fatal does not exit the process.
- `render` replaces caller scratch and returns whether it rendered a line.
  `emit` also calls a synchronous boolean sink and returns Filtered, Written or
  SinkError. Filtered calls leave scratch alone.
- `emit_lazy` builds a message only when enabled. `Record` adds caller-supplied
  timestamp/source text and up to eight string fields with explicit masking.
- Plain messages inspect at most 4096 source bytes and emit at most 16417 bytes.
  Contextual records have separate field limits and a 28592-byte output bound.
  Controls, backslashes and non-ASCII bytes are escaped. This is byte-oriented
  text, not JSON; Unicode is shown as escaped UTF-8 bytes.
- Input must not borrow from scratch. Sinks borrow a line synchronously and must
  copy bytes they retain. Sink errors may follow partial output; there is no retry
  or rollback. Your program owns synchronization and delivery guarantees.

See [API.md](API.md) for signatures, exact formats, colors, truncation and ownership.
Escaping does not detect secrets. No async queue, rotation, global sink registry,
automatic source capture or allocation-free guarantee is provided.

## Examples

- [File append](examples/file.goose): `goose run examples/file.goose -- ./application.log`.
  Replace `goose` with `.toolchain/goose/build/goose` from the quickstart.
- [Linux CLI diagnostics](examples/cli/README.md): fixed events, checked private-file
  delivery and separate JSON stdout.
- [UTC timestamps](examples/utc/README.md): an optional adapter using an injected
  clock and pinned goose-time dependency. The core does not depend on goose-time.

## Platforms and development

With the pinned compiler, core CI covers Linux x86-64, native Linux ARM64 and
macOS 15 ARM64. The CLI file adapter is tested on both Linux architectures.
Main also tests the optional UTC adapter on both Linux architectures; v0.1.3
predates the ARM64 CI addition. Windows and macOS x86-64 are unverified.
See [platform coverage](PORTABILITY.md) for tool versions and test limits.

[Testing](TESTING.md) has build/check commands and sanitizer limits.
[Benchmarks](bench/README.md) separates measured scopes, current-code checks and
historical experiments. Results depend on the workload, compiler, sink and host.
[Contributing](CONTRIBUTING.md) covers commits and reviews;
[security](SECURITY.md) covers reporting and trust limits.

[License](LICENSE) · [Notice](NOTICE) · [Third-party notes](THIRD_PARTY_NOTICES.md)
