# Linux CLI diagnostics example

This Linux reference integration adds application state and a native file
adapter around goose-log. The core logger remains independent of file I/O.
It accepts fixed events and numeric data, so command arguments, child output,
paths and other arbitrary strings are never copied into diagnostic messages.
It is not a general text logger or a signal-handler logging API.

Declare both packages in the entry source, for example from `consumer.goose`:

```goose
import logger from "../..";
import diagnostics from ".";
```

The diagnostics namespace is `diagnostics`; the core namespace is `log`.
The package is restricted to the main thread in `diagnostics.build`, which
compiles `log_sink.c` with C11, `-Wall -Wextra -Werror`.

Run the reference consumer from a standalone goose-log checkout:

```sh
make setup
make test-cli
.build/cli-consumer 1000 --log-file .build/cli-events.log
```

It preserves a JSON business result on stdout while writing diagnostic events
to the explicitly selected private file. `--fail` exercises a fixed business
failure and exit code 7. This fixture replays a lifecycle; it is not Honk itself.
Applications adapt this fixed lifecycle boundary to their own control flow.

## Goose API

- `Event { Started, ItemCompleted, Returned, Failed, ChildFailed }`.
- `event_name(event)` returns `started`, `item_completed`, `returned`, `failed`
  or `child_failed`. `level(event)` returns Error for Failed/ChildFailed and
  Info for the other events.
- `message(event, duration_ns: u64, outcome: u32)` returns owned bytes of the
  exact form `EVENT duration_ns=DECIMAL outcome=DECIMAL`. Both numeric values
  are caller supplied; the helper reads no clock. Decimal conversion uses a
  bounded local digit array rather than application formatting overloads.
- `configure(path, minimum = log::Level.Info)` owns a copy of the path and
  starts a new configuration session on success, clearing an earlier failure.
  It does no I/O. Empty paths, paths of 4096 bytes or more, and embedded NUL
  are rejected; rejection disables the previous configuration and sticks a
  configuration error. Otherwise it returns true even if a later open fails.
  Path storage is a fixed 4096-byte application-owned array. This and lexical
  rendering buffers keep error callbacks usable while Honk builds or borrows
  parser/manifest data with the pinned compiler; no ownership checks are disabled.
- `active()` reports a valid configuration with no sticky error and a minimum
  other than Off. Wrappers can avoid clocks and related lifecycle work when
  false. It does not test whether a particular event passes the minimum level.
- `write(event, duration_ns = 0, outcome = 0)` uses owned logger configuration
  and a lexical scratch buffer per call, so terminal logging does not clear
  shared storage while callers hold borrowed data. It uses `emit_lazy`.
  Filtered calls neither build a message nor invoke the sink.
  Before any configuration attempt, a call is a successful no-op. A failed
  configuration or delivery makes it return false on subsequent calls without
  construction or I/O until a successful explicit configuration. There is no
  recursive error logging or automatic retry.
- `append(path, line)` exposes the native boolean adapter for tests/profiling.
  It has no configuration or sticky state. The C symbol is
  `goose_cli_log_append`, taking two `{ const uint8_t *data; int64_t len; }`
  slices by value and returning `uint8_t` (zero or one).
- `stdout_ok()` is a reference-consumer adapter that flushes and checks stdout.
  It returns false for a failed flush or an earlier stream error. Honk uses
  its existing checked stdout adapter instead; this is not a goose-log API.

## File policy and limits

The path is explicit and is resolved from `/` for absolute paths or an opened
current directory for relative paths. Every supplied directory component is
opened separately with `O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`. The final file
uses `O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC | O_APPEND`; symlinks in any supplied
component are rejected. Relative `.`/`..` and repeated interior separators
are accepted; trailing separators are rejected. This is path validation, not
a sandbox restricting which directories the caller may select.

Only a regular file owned by the effective user, with exact mode `0600` and
one hard link, is accepted. Existing files with other permissions are rejected
without changing them. A new file is exclusively created and then set to
`0600`, even under a restrictive umask. A newly created empty file may remain
after a later failure. Parent directories are never created.

Each append opens and closes its descriptor. A nonblocking exclusive `flock`
coordinates cooperating writers. Metadata and the 16 MiB total file limit are
checked under the lock before writing. A busy lock, invalid path/target,
quota exhaustion or I/O failure returns false. Lines must contain 1–16417
bytes; the low-level adapter does not validate their text format. The fixed
event formatter and goose-log renderer supply the expected safe single line.

Writes retry EINTR and complete short writes while holding the lock; close
errors are reported. A failure can follow partial output, and there is no
rollback, fsync, rotation, durability promise or coordination with writers
that ignore the advisory lock. File attributes/pathnames can also be changed
by other processes after inspection; this is not protection against a process
with the same user's authority modifying the log concurrently. Calls are
ordinary main-thread operations and must never run in a signal handler.

This adapter is validated on Linux only. Its checked-close behavior follows
Linux's rule that a descriptor is closed even when close reports EINTR; close
is not retried. No other platform support is claimed.
