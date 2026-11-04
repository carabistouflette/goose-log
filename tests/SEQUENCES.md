# Randomized logging sequences

`make test-sequences` mixes plain render/emit, contextual render/emit, lazy
borrowed/owned builders, and caller prefills on one shared scratch buffer.
A second owned buffer retains the sink's copied line across later operations.
Production logger code and the compiler pin are unchanged.

Each seed starts with 299 fixed transitions: maximum record → filtered
plain/lazy calls, failed owned-builder sink, binary prefill, then all 49 named
minimum/severity pairs for six logging operations. Colors and sink outcomes
vary; every combination per pair is not exhausted. Four default seeds
(`0x6005e`, `0x5ec0ad`, `0`, `0xffffffff`) each add 256 random steps:
**2220 transitions per driver**, 6660 across normal/debug/JIT drivers.
`make test-sequences-sanitize` tests standalone debug/optimized ASan/UBSan.
These targets run within the existing core and sanitizer CI targets.

## Model and coverage

The runner reuses the existing independent Python plain/record byte encoders,
not the Goose formatter. It models exact scratch/retained bytes, status,
builder/sink counts and builder-before-sink order. Filtering preserves previous
bytes: a filtered plain call after a maximum record retains 28592 bytes.
The 16417-byte plain bound applies only to newly accepted plain output.
Failed sinks retain the rendered line and are called once without a retry.

Every input frame is copied before the call and checked unchanged afterward.
Unrelated temporary allocations precede another retained-copy check. Inputs
include ASCII, binary and backslash-heavy data, cap neighbors, excess/sensitive
fields, changing levels/colors, sink failures, and arbitrary caller prefills.
This is valid API sequence testing, not malformed-wire or coverage-guided
fuzzing. Existing ownership rejection and protected-page checks still apply;
ASan does not cover every logical boundary in Goose's custom mmap data stacks.

## Reproduce and reduce

```sh
make setup
make test-sequences
python3 -O tests/sequences.py --seed 1234 --steps 2048 .build/sequences-native .build/sequences-debug
GOOSE=.toolchain/goose/build/goose python3 -O tests/sequences.py --seed 1234 --steps 2048 tests/sequences_jit.sh
```

Failures retain original JSON/binary fixtures, seed, argv, executable hashes,
workspace source hashes/commit, exit/timeout state and stdout/stderr under a
unique ignored `.build/sequences/failure-*` directory. JIT identity includes
the supplied wrapper and selected Goose compiler. Replay verifies these recorded
executables and workspace sources before re-encoding; this does not authenticate
all compiler flags, imported toolchain sources or machine state.

```sh
python3 -O tests/sequences.py --replay .build/sequences/failure-XYZ/original.json .build/sequences-native
python3 -O tests/sequences.py --replay .build/sequences/failure-XYZ/original.json --minimize .build/sequences-native
# Explicit opt-in for rebuilt/fixed binaries or changed workspace/oracle sources:
python3 -O tests/sequences.py --replay .build/sequences/failure-XYZ/reduced.json --allow-new-driver .build/sequences-native
```

`--minimize` deletes operations and recomputes oracle state. It permits at most
64 trials, a 20-second search budget checked between trials, child timeouts of
at most five seconds, and a separate five-second confirmation. Only a repeated
named driver check produces reduced artifacts. Parser errors, timeouts, unnamed
signals and incomplete execution are not accepted reductions. The same check
class does not prove the same semantic cause or a globally/byte-minimal case.
The original binary fixture preserves the exact prior expected bytes.

## Negative control

`tests/sequence_control.py` builds a private mutant in ignored temporary storage:
filtered plain calls incorrectly clear scratch only after output exceeds 16417
bytes. An isolated filtered call passes, but the sequence oracle must reject
the mutant, reduce 299 operations to a two-call state dependency, repeat that
failure, and pass the original logger on the reduced witness. It also tests
fixture persistence, recomputed state, changed-binary/source refusal, and
explicit fixed-driver replay. Operational checks run under Python `-O`.
This controlled failure is not a production defect.

Run one Make invocation per checkout, without concurrent source/binary rebuilds.
See [local validation](SEQUENCES-RESULTS.md) for the extended seeded run.
