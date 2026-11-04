# Recorded randomized-sequence validation

On 2026-11-04 UTC, clean source
[`36e7469527eb599fdc7e3bf2c50aea865336bdd2`](https://github.com/carabistouflette/goose-log/tree/36e7469527eb599fdc7e3bf2c50aea865336bdd2)
passed an extended seeded sequence run. **No production mismatch was observed**
for these inputs; this is not proof of absence of bugs or a performance result.
The logger and compiler pin remain unchanged from v0.1.1.

## Observed scope

- Seeds 0 through 31, with 299 fixed transitions and 2048 random transitions
  per seed: **75104 transitions per driver**.
- Five drivers: Clang normal native, debug native with bounds checks retained,
  JIT, Clang standalone debug ASan/UBSan, and Clang standalone optimized
  ASan/UBSan. **375520 completed state transitions** across these drivers.
  The same input sequences run on each driver; these are not 375520 unique
  generated inputs. Caller-prefill transitions are included in the count.
- 160 complete process results, all with the expected 2347 operations, no
  unexpected stderr, and identical fixture hashes across the five drivers
  for each seed. Source state, workspace inputs and executable fingerprints
  were checked unchanged before recording the result.
- Linux `7.2.11-arch1-1`, Clang `23.1.4`, Python version recorded in the
  [manifest](sequences-results.json). Goose `eadca40`, runtime `3025e5810379`,
  compiler pin `eadca409f68210893f366e60d0c2f0dc29a339be`.
- Separately, the default four-seed normal/debug/JIT suite and standalone
  debug/optimized sanitizer suites passed locally under GCC and Clang, along
  with the existing full tests, byte/record oracles and protected-page tests.

The manifest retains all seeds, fixture hashes, per-process counts, executable
hashes, source fingerprints, build command and environment versions. Hashes
identify the recorded inputs; they do not authenticate every machine/build
setting. No raw real-world messages or production data were used.

## Negative control

The private state-only mutant deliberately clears filtered plain scratch only
after the previous output exceeds 16417 bytes. An isolated filtered call passes.
The new sequence oracle rejects the mixed sequence, deletes unrelated calls,
and reproduces the same named `scratch` failure with two calls. The original
logger passes that witness. The control also confirms artifact persistence,
source/executable replay checks and explicit replay against the original binary.
This controlled mutation is not a production defect or a runtime fix.

## Reproduce

```sh
git clone https://github.com/carabistouflette/goose-log.git
cd goose-log
git checkout 36e7469527eb599fdc7e3bf2c50aea865336bdd2
make setup
make GOOSE_CC=clang SANITIZER_CC=clang test-guarded test-sanitize test-sequences
```

Run the extended suite with Python argv construction to preserve exact seeds:

```python
import subprocess
args = ["python3", "-O", "tests/sequences.py", "--steps", "2048"]
for seed in range(32):
    args += ["--seed", str(seed)]
args += [".build/sequences-native", ".build/sequences-debug",
         "tests/sequences_jit.sh", ".build/sequences-sanitized",
         ".build/sequences-sanitized-release"]
subprocess.run(args, check=True)
```

Run one invocation at a time per checkout. Failures retain their original
fixtures; see [the method and reduction limits](SEQUENCES.md). ASan's coverage
of Goose's custom mmap-backed stacks is limited; ownership/bounds checks,
independent byte/state oracles, and physical protected pages complement it.
The default CI suite repeats four seeds on Linux and macOS ARM64. The extended
32-seed result above is local Linux evidence, not a claim that the extended
campaign ran on every CI platform.
