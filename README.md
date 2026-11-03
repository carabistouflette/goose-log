# goose-log

Small, bounded, explicit logging for the
[Goose programming language](https://github.com/aardappel/goose).
Apache-2.0. Experimental API; no release yet.

The application owns output and reusable scratch storage. The library will
provide severity filtering, single-line byte-safe formatting, optional label
colors, and synchronous delivery to a caller-supplied sink. No global state,
file handles, clocks, environment access, or runtime dependencies beyond Goose's
standard library.

The first version deliberately excludes file rotation, asynchronous queues,
JSON output, and automatic formatting of application objects.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and commit standards.
[GOOSE_REVISION](GOOSE_REVISION) pins the compiler used in CI.
