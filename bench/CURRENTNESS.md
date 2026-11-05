# Measurement source checks

This audit compares recorded measurement inputs with published main
`1f10b1d2c92a4ea7de48250f57f55b968b5339ba`. The documentation update changes no
logger, example adapter, benchmark driver, compiler pin or dependency pin.
The exact file hashes and raw-record checks are in [source-bridges.json](source-bridges.json).
Raw measurements have not been rewritten or relabeled as new runs.

## What still matches

| Measured source | Unchanged relevant code on main | Other differences |
| --- | --- | --- |
| `5c5db8f` synchronous comparison | Logger, compiler pin, Goose adapter and C++ driver; comparison dependency pins | Runner adds missing-CPU-model handling and architecture metadata |
| `10a794a` allocation probe | Logger, compiler pin, probe, C host and runner | None in measured code |
| `0c37940` CLI components | Logger, compiler pin, driver, diagnostics module/build file and native sink | Runner adds missing-CPU-model handling |
| `0ec9a00` native baseline | Logger and compiler pin | The later candidate was rejected |
| `5ede662` final UTC capture | Logger, compiler pin, UTC adapter, measured driver and runner; goose-time pin | Later results/docs and smoke replay tests are outside timed code |
| `e8668cc` Honk metadata harness | Harness, logger and compiler pin | The supplied application remains frozen Honk v0.2.0, not current Honk |
| `7c5202e` Honk instrumentation | Final instrument script | Earlier `13bf924` controls have their own source/hash and omit late-failure checks |

The measured compiler source remains
`eadca409f68210893f366e60d0c2f0dc29a339be`. The audit matched recorded stdlib and
runtime-header hashes against that Git object, alongside local input hashes in
eight clean raw records. Executable hashes, native compiler versions and flags
remain those of each original run; identical source is not proof that a new
compiler build or machine will reproduce its timing.

Comparison pins remain rxi/log.c `f9ea34994bd58ed342d2245cd4110bb5c6790153`,
spdlog `79524ddd08a4ec981b7fea76afd08ee05f83755d` and Macho0x/goose-logger
`50695a3df0eb5a1048a4b183538d59f43f5eb279`. UTC still imports goose-time
`343887caeee0a1f4e2e536ff322fcafb454e11bd`; its three recorded dependency-file
hashes match that Git object. These are measurement pins, not latest-version claims.

## What remains historical

- The literal-input table at `e450b55` measures a different logger. Its driver
  and compiler pin still match, but its numbers do not describe current code.
- Candidate `66c7b7e` differs from main and remains rejected. Its tables and
  supplementary single-process instruction/cycle counts document the experiment;
  they are not a release speedup. Main matches its baseline, not its candidate.
- The initial UTC capture used uncommitted benchmark files. Its recorded hashes
  identify that exploratory run; the clean final capture supplies the current
  measured-code comparison. Full-run OS checksums cannot be reconstructed from
  compact metadata alone because those traces were discarded by design.
- Honk results use the owner's supplied `855fb055` release binary. Its build
  flags were not independently reconstructed. Equal logger bytes do not make
  newer application versions equivalent. Heaptrack/strace results are separate
  instrumented controls; the failed Valgrind startup is not allocation evidence.

No new timing run was needed for this audit: active renderer/adapter claims have
checked source comparisons, and superseded implementations are explicitly
historical. There is no current performance claim for Windows, macOS, ARM64,
other compiler revisions, or a newer Honk application binary.

## Recheck the file comparisons

Use a normal Git clone with history (not a source archive). This checks recorded
Git/file hashes without compiling or measuring:

```sh
python3 - <<'PY'
import hashlib, json, pathlib, subprocess
root = pathlib.Path('.')
audit = json.loads((root / 'bench/source-bridges.json').read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
for check in audit['source_checks']:
    for item in check['files']:
        old = subprocess.check_output(['git', 'show', check['measured_revision'] + ':' + item['path']])
        new = (root / item['path']).read_bytes()
        assert sha(old) == item['measured_sha256']
        assert sha(new) == item['audited_sha256']
        assert (old == new) == item['identical']
for item in audit['raw_record_checks']:
    assert sha((root / item['artifact']).read_bytes()) == item['sha256']
print('Source comparisons and retained-record hashes match')
PY
```

This is a reproducibility check, not authentication of a host or executable.
Follow each result's pinned checkout and original tool/platform protocol when
reproducing the measurement itself.
