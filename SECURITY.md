# Security

This library has an experimental API before 1.0. Security fixes target the
latest released version and `main`; older releases and pinned commits are not
separately maintained. Review updates before replacing an application's pinned
revision. Core validation covers Linux x86-64, native Linux ARM64 and macOS 15
ARM64 with the pinned compiler; the hardened CLI adapter is validated on both
Linux architectures. See
[platform validation](PORTABILITY.md) for tested coverage and limitations.

## Report a vulnerability

Use GitHub's private vulnerability reporting form:
https://github.com/carabistouflette/goose-log/security/advisories/new

Please include the full library and Goose compiler commits, platform, a minimal
reproducer, and the expected versus observed behavior. Do not put credentials,
personal data, or live secrets in the report. Keep exploit details private until
a fix or coordinated disclosure is ready. Non-security defects can use ordinary
GitHub issues. No response-time guarantee is made for this volunteer project.

## Trust model and limits

Messages may contain arbitrary bytes. The formatter escapes controls, non-ASCII
bytes, and backslashes; it inspects at most 4096 source bytes and emits at most
16417 bytes per enabled call, including explicit optional label colors. It does
not redact secrets, parse its output as structured data, or make durable writes.

Opt-in contextual records cap metadata and fields separately, with at most
28592 output bytes. Metadata and arbitrary string fields are quoted and escaped;
explicitly sensitive field values are replaced by `***` without being inspected.
This does not detect secrets in ordinary fields or message text. Timestamp text
and source locations come from the application. Lazy message builders run only
when enabled, but their arbitrary CPU/allocation work remains outside these caps.

The application owns the logger, message construction, scratch storage, output
sink, synchronization, and sink error reporting. The input must not borrow from
scratch; sinks must preserve their borrowed line while consuming it. Sink
failures may follow partial external output and are not retried. Work done by
message expressions and sinks is outside the formatter's limits. Native FFI
that violates Goose's ownership or layout requirements is outside this contract.

Validation combines exact-output tests, compiler ownership rejection tests,
protected pages, and native sanitizers. Goose's mmap-backed data stack allocations
do not expose every logical array boundary/lifetime to ASan. No single check
proves absence of bugs. The tested compiler revision is pinned in
`GOOSE_REVISION`; other revisions and platforms require separate validation.

Setup checks source cleanliness for reproducibility. It does not authenticate
an already-compromised machine, Git configuration, compiler binary, or cached
build artifacts. GitHub CI uses read-only contents permissions and immutable
action revisions; generated toolchains and build outputs are not published.
