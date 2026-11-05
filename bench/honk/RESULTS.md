# Honk logging observations

The frozen public Honk v0.2.0 source is
[`855fb0552aefd5f0c033826af64f3bdd09ae6482`](https://github.com/carabistouflette/honk/tree/855fb0552aefd5f0c033826af64f3bdd09ae6482).
Two independently launched plain series used clean harness source `e8668cc`,
the same owner-supplied native binary, compiler selection and fixture template.
The binary, source tree and complete stdout/event bytes were validated; the
vendored logger bytes equal current goose-log. No product source was changed.

[Environment and ownership provenance](results/environment.json),
[first series](results/first.json), [repeat](results/repeat.json),
[initial instrumentation controls](results/instrument-initial.json), and
[final instrumentation controls](results/instrument-final.json) retain identities,
every accepted sample and validation outcomes. See [method](README.md).

## Plain whole-command results

Linux x86-64, Intel Core Ultra 7 258V, CPU6, kernel 7.2.11-arch1-1, glibc 2.44,
Python 3.14.9, btrfs, 4096-byte pages. The host was shared, without exclusive core,
frequency or filesystem isolation. Honk's independent build/run owner used CPU0;
this does not establish absence of other shared-host interference.

Each series has nine shuffled paired rounds of 32 sequential fresh processes:
36 batches / 1152 measured commands across both series. Each enabled command
emits two records. Startup, process/capture/wait overhead and metadata work are
included; these are batch averages, not individual tail latencies.

| Series | Logging disabled, median (range), ms/command | Logging enabled, median (range), ms/command |
| --- | ---: | ---: |
| First | 10.887 (10.004–14.154) | 10.993 (10.213–20.574) |
| Repeat | 10.464 (9.921–11.316) | 10.822 (10.170–10.926) |

Ranges overlap substantially; the enabled first-series outlier is retained.
These observations do not isolate a logger-only overhead, establish statistical
equivalence or support an optimization claim. No throughput ranking, production
service workload, build/run improvement or universal performance claim follows.

## Allocation and sink controls

The final separate instrumented source is `7c5202e`; earlier 18 controls at
`13bf924` are also retained. Heaptrack 1.5.0 observed 11 allocation-function calls,
one temporary allocation and displayed 144.96K peak heap in each of three fresh
processes per enabled/disabled path, in both runs. These are whole-process
intercepted heap observations. They exclude logical arena allocations, stack and
mapping reservations, and do not establish allocation-free logging or equal
memory consumption. The explicit compiler selection differs in executable hash
from the owner's build-time compiler receipt, but advertises the same pinned
revision/runtime; metadata does not execute it. Both hashes are named separately.

A Valgrind 3.25.1 attempt could not reserve the runtime's data-stack address space
before executing metadata. It produced no usable application allocation sample;
its startup counts are excluded, rather than reported as logger observations.

All normal records, exact metadata stdout and private-file metadata checks
passed. Untimed busy-lock/full-quota failures preserved all prior file bytes and
identity, returned nonzero and produced no metadata. Separate strace controls
confirmed zero diagnostic writes on the disabled path, exactly two delayed
writes on the enabled path, and a second-write ENOSPC failure that preserved
completed metadata stdout plus Started while returning nonzero without Returned.
This demonstrates the expected synchronous/failure behavior under explicit
instrumentation, not a storage-latency bound. Instrumented timings are retained
but are not interpreted as plain latency or exact delay attribution.

The frozen release prints two identical fixed diagnostics on delivery failure;
that application observation was handed to Honk's owner. No logger-core mismatch,
new delivery contract violation or evidence-backed production optimization was
identified. Core, sink policy, application pins and release tags stay unchanged.
