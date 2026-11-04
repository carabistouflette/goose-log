#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reject a state-only mutation and reduce its failure to two calls."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import sys
import tempfile
import sequences


def require(ok, message):
    if not ok:
        raise SystemExit(message)


def main():
    require(len(sys.argv) == 2, "usage: sequence_control.py GOOSE")
    goose = Path(sys.argv[1]).resolve()
    sequences.CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="control-", dir=sequences.CACHE) as tmp:
        root = Path(tmp)
        (root / "tests").mkdir()
        source = (sequences.ROOT / "logger.goose").read_text()
        anchor = "    if !enabled(logger, level) { return false; }"
        require(anchor in source, "negative control no longer matches render's filter gate")
        (root / "logger.goose").write_text(source.replace(anchor,
            "    if !enabled(logger, level) { if out.len > MAX_LINE_BYTES { out.clear(); } return false; }", 1))
        shutil.copyfile(sequences.ROOT / "tests/sequences.goose", root / "tests/sequences.goose")
        binary = root / "mutant"
        subprocess.run([str(goose), "build", str(root / "tests/sequences.goose"), "-o", str(binary)],
                       check=True, capture_output=True, timeout=90)
        cases = sequences.generate(0, 0)
        good, _, _ = sequences.run(binary, [cases[1]], root / "isolated.bin")
        require(good, "isolated filtered call must pass; mutation requires earlier large record")
        result = subprocess.run([sys.executable, "-O", str(sequences.ROOT / "tests/sequences.py"),
                                 "--seed", "0", "--steps", "0", "--minimize", str(binary)],
                                capture_output=True, text=True, timeout=60)
        match = re.search(r"artifacts=(.+)", result.stderr)
        require(result.returncode == 1 and match is not None,
                f"mutation escaped the oracle or failed without artifacts: {result.stderr}")
        failure = Path(match[1])
        require(failure.resolve().parent == sequences.CACHE.resolve() and failure.name.startswith("failure-"),
                "unexpected artifact directory")
        original = json.loads((failure / "original.json").read_text())
        reduced = json.loads((failure / "reduced.json").read_text())
        require(original["cases"] == json.loads(json.dumps(cases)), "original JSON lost the input")
        require((failure / "original.bin").read_bytes() == sequences.encode(cases), "original fixture mismatch")
        require(len(reduced["cases"]) == 2 and reduced["signature"] == "scratch", "lost two-call dependency")
        require((failure / "reduced.bin").read_bytes() == sequences.encode(reduced["cases"]), "stale reduced oracle")
        good, signature, _ = sequences.run(binary, reduced["cases"], root / "reduced.bin")
        require(not good and signature == "scratch", "reduced fixture did not reproduce the same check")
        (root / "logger.goose").write_text(source)
        baseline = root / "baseline"
        subprocess.run([str(goose), "build", str(root / "tests/sequences.goose"), "-o", str(baseline)],
                       check=True, capture_output=True, timeout=90)
        good, _, _ = sequences.run(baseline, reduced["cases"], root / "baseline.bin")
        require(good, "unmodified runtime failed the reduced witness")
        replay_command = [sys.executable, "-O", str(sequences.ROOT / "tests/sequences.py"),
                          "--replay", str(failure / "reduced.json")]
        refused = subprocess.run(replay_command + [str(baseline)], capture_output=True, timeout=30)
        require(refused.returncode == 2 and b"replay binary differs" in refused.stderr,
                "replay silently changed driver binaries")
        identity = dict(reduced, sources=dict(reduced["sources"]))
        identity["sources"]["logger.goose"] = "0" * 64
        (root / "changed-source.json").write_text(json.dumps(identity))
        refused_source = subprocess.run([sys.executable, "-O", str(sequences.ROOT / "tests/sequences.py"),
                                         "--replay", str(root / "changed-source.json"), str(binary)],
                                        capture_output=True, timeout=30)
        require(refused_source.returncode == 2 and b"replay workspace differs" in refused_source.stderr,
                "replay silently changed source/oracle inputs")
        accepted = subprocess.run(replay_command + ["--allow-new-driver", str(baseline)], capture_output=True, timeout=30)
        require(accepted.returncode == 0, "explicit fixed-driver replay failed")
        shutil.rmtree(failure)
    print("sequence negative control: state-only mutation rejected; 299 operations reduced to 2")


if __name__ == "__main__":
    main()
