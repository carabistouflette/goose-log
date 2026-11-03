# Contributing

Keep the API small, explicit, and independent of process or file I/O.
Applications own output, configuration, and scratch storage. Prefer Goose's
standard library over duplicate implementations. Discuss changes to output
escaping, bounds, and ownership before broadening the contract.

Use focused branches (`feat/...`, `fix/...`, `docs/...`) and Conventional
Commits: `feat: add ...`, `fix: reject ...`, `docs: clarify ...`,
`test: cover ...`, `chore: update ...`. Subjects are imperative and each
commit contains one coherent change. Use semantic versions when a reviewed
release is ready; there is no stability guarantee before 1.0.

For behavior changes, add public API regression cases in `tests/logger.goose`.
Run `make format`, `make check test`, and `git diff --check`. Exercise filtering,
all byte values, truncation boundaries, buffer reuse, and sink failures.
For safety or buffer changes, also run `make test-sanitize` with GCC or Clang
sanitizer runtimes installed. On POSIX, run `make test-guarded` for changes to
filtering or input bounds. Keep the independent differential oracle in sync
with deliberate contract changes; do not derive its expected bytes from the
library under test.
Request independent review, fix actionable findings, and keep CI passing.
Never commit credentials, generated compiler output, or private workspace notes.

Compiler changes require a reviewed full upstream commit in `GOOSE_REVISION`
and full validation. CI builds that exact revision with optional graphics/audio
disabled. Report vulnerabilities privately through GitHub's security advisory
reporting when enabled; avoid public exploit details before a fix is available.
