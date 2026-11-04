# Allocation and arena probe

This optional Linux development probe uses the pinned compiler and GNU-compatible
linker wrapping. It measures memory behavior, **not execution time**:

```sh
make setup
python3 bench/alloc/run.py
```

The default output is ignored `.build/alloc/results.json`. It retains source,
compiler binary, standard library and harness hashes, flags, platform details,
and every phase. Input changes during the run invalidate the result. Choose
`--iterations N` to change warm calls (default 10000). Each phase is a fresh
process, and whole-process runtime initialization is reported separately.
See [recorded observations](RESULTS.md) for two retained runs.

The host checks complete bytes and sink counts for 4097 input bytes of `0xff`.
The plain profile reaches the exact 16417-byte colored line bound. The contextual
record reaches the exact 28592-byte bound using capped metadata and fields,
maximum line number, and excess-field marker. The synchronous sink only compares
against a fixed expected byte array; it neither allocates nor writes externally.
Cold phases measure one call. Warm phases first render the corresponding maximum
line once outside measurement, then measure repeated calls. The warm filtered
phase first fills plain scratch, then verifies disabled calls preserve it and
never invoke the sink; the cold filtered phase starts with empty scratch.

## What is counted

- **Direct C allocation calls:** `malloc`, `calloc`, `realloc`, and `free` from
  the generated translation unit and probe host. Requested bytes are counted,
  not allocator usable sizes or retained capacity. A realloc request is not
  its net growth. Calls include failed requests if a future implementation
  makes any. Calls inside dynamically linked libc are **not intercepted**.
- **Direct OS memory calls:** `mmap`, `mprotect`, `munmap`, and `madvise` from
  that same program. Mapping bytes are requested virtual bytes, including
  guard gaps, not resident memory. The real-call control exercises all eight
  wrappers and fails if their expected counts are not observed.
- **Arena snapshots:** region count, reserved virtual bytes, and the sum of
  current stack tops minus their bases in the pinned runtime registry before
  and after each phase. Stack tops describe logical live arena bytes at those
  two boundaries. They are **not** peak temporary use or a heap-allocation count.
- **Minor page faults:** `getrusage` process deltas. On Linux these can include
  demand paging when an already-reserved arena is first touched, without any
  new mapping call. These are process-level observations, not exact page or
  physical allocation counts attributable solely to the logger.

The pinned runtime reserves growable-array backing with `mmap` at startup on
Linux, then advances and rewinds stack tops inside those reservations. Its
`clear` does not necessarily return physical pages to the OS. This is why
zero measured malloc/mmap calls during a render does **not** prove no memory
was used or no physical pages were first committed. Initialization, retained
virtual regions, C/native stacks, libraries, and caller/sink work still matter.
The probe deliberately does not publish an allocation-free guarantee or RSS
estimate. Its registry access is tied to the full Goose pin, not a public Goose
API. A future compiler update must review it alongside the counter control.
