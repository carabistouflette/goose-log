#!/usr/bin/env python3
"""Negative controls for the application-profile diagnostic oracle."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("honk_profile", Path(__file__).resolve().parents[1] / "bench/honk/run.py")
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class DiagnosticOracle(unittest.TestCase):
    def test_valid_and_repeated(self):
        pair = b"[INFO] started duration_ns=0 outcome=0\n[INFO] returned duration_ns=18446744073709551615 outcome=0\n"
        profile.check_events(profile.PREFIX + pair, 1)
        profile.check_events(profile.PREFIX + pair * 32, 32)

    def test_corrupt_records_rejected(self):
        pair = b"[INFO] started duration_ns=0 outcome=0\n[INFO] returned duration_ns=3 outcome=0\n"
        corruptions = [pair, profile.PREFIX, profile.PREFIX + pair + b"private-marker",
                       profile.PREFIX + pair.replace(b"returned", b"started"),
                       profile.PREFIX + pair.replace(b"duration_ns=0", b"duration_ns=1"),
                       profile.PREFIX + pair.replace(b"outcome=0", b"outcome=1"),
                       profile.PREFIX + pair.replace(b"duration_ns=3", b"duration_ns=18446744073709551616"),
                       profile.PREFIX + pair * 2]
        for corrupted in corruptions:
            with self.subTest(data=corrupted):
                with self.assertRaises(SystemExit):
                    profile.check_events(corrupted, 1)

    def test_symlink_policy_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.write_bytes(profile.PREFIX)
            target.chmod(0o600)
            link = Path(directory) / "link"
            link.symlink_to(target)
            profile.file_state(target)
            with self.assertRaises(SystemExit):
                profile.file_state(link)


if __name__ == "__main__":
    unittest.main()
