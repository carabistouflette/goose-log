#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay retained smoke evidence and require rejection of deliberate corruptions."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("utc_measure", ROOT / "bench/utc/run.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)
FIELDS = {"elapsed_ns", "iterations", "sinks", "clocks", "written", "filtered",
          "formatted", "bytes", "checksum", "last_ns", "timestamp_hex", "line_hex"}


def load_items(path):
    data = path.read_bytes()
    at = 4
    items = []
    for _ in range(8):
        ns, = struct.unpack_from("<q", data, at)
        at += 8
        item = {"ns": ns}
        for key in ("message", "timestamp", "plain", "record"):
            size, = struct.unpack_from("<I", data, at)
            at += 4
            item[key] = data[at:at + size]
            at += size
        items.append(item)
    if at != len(data):
        raise ValueError("invalid retained fixture length")
    return items


class VerificationControls(unittest.TestCase):
    def test_replay_all_retained_smoke_rows(self):
        base = ROOT / "bench/utc/results/smoke"
        fixtures = {p.stem: load_items(p) for p in (base / "fixtures").glob("*.bin")}
        rows = [json.loads(line) for line in (base / "rounds.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 32)
        for captured in rows:
            with self.subTest(fixture=captured["fixture"], stage=captured["stage"], round=captured["round"]):
                row = {key: captured[key] for key in FIELDS}
                trace = gzip.decompress((base / captured["trace"]).read_bytes()) if "trace" in captured else b""
                if trace:
                    self.assertEqual(measure.digest(trace), captured["trace_sha256"])
                stage = measure.STAGES.index(captured["stage"])
                measure.verify(row, stage, fixtures[captured["fixture"]], row["iterations"], trace)
                for field in ("checksum", "clocks", "line_hex"):
                    bad = copy.deepcopy(row)
                    bad[field] = ("00" + bad[field][2:]) if field == "line_hex" else bad[field] + 1
                    with self.subTest(corruption=field), self.assertRaises(SystemExit):
                        measure.verify(bad, stage, fixtures[captured["fixture"]], row["iterations"], trace)

    def test_compiler_advertised_revision(self):
        pin = (ROOT / "GOOSE_REVISION").read_text().strip()
        for revision in (pin[:7], pin):
            measure.verify_compiler_version(f"goose {revision} (runtime example)", pin)
        for version in ("goose deadbee (runtime example)", "goose ead", "invalid"):
            with self.subTest(version=version), self.assertRaises(SystemExit):
                measure.verify_compiler_version(version, pin)


if __name__ == "__main__":
    unittest.main()
