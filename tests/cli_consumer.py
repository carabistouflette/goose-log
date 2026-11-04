#!/usr/bin/env python3
"""Real filesystem and lifecycle checks for the application-owned reference."""
from pathlib import Path
import fcntl
import json
import os
import re
import resource
import signal
import stat
import subprocess
import sys
import tempfile
import unittest

CONSUMER, SINK, STATE = [str(Path(p).resolve()) for p in sys.argv[1:4]]
CAP = 16 * 1024 * 1024
EVENT = re.compile(rb"\[(INFO|ERROR)\] (started|item_completed|returned|failed|child_failed) duration_ns=([0-9]+) outcome=([0-9]+)\n")


class ReferenceCLI(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="goose-log-cli-")
        self.root = Path(self.temporary.name)
        self.log = self.root / "application.log"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, count, *extra, **kwargs):
        return subprocess.run([CONSUMER, str(count), *map(str, extra)], cwd=self.root,
                              capture_output=True, timeout=30, **kwargs)

    def sink(self, path, size):
        result = subprocess.run([SINK, str(path), str(size)], cwd=self.root,
                                capture_output=True, timeout=10)
        self.assertEqual((result.stdout, result.stderr), (b"", b""))
        return result

    def private_file(self, data=b"prefix\n"):
        self.log.write_bytes(data)
        self.log.chmod(0o600)

    def events(self, prefix=b""):
        data = self.log.read_bytes()
        self.assertTrue(data.startswith(prefix))
        data = data[len(prefix):]
        rows = EVENT.findall(data)
        self.assertEqual(b"".join(m.group() for m in EVENT.finditer(data)), data)
        return rows

    def test_disabled_is_side_effect_free(self):
        result = self.run_cli(3)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertEqual(json.loads(result.stdout), {"processed": 3, "checksum": 3})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_sustained_append_privacy_and_stdout(self):
        self.private_file()
        expected = self.run_cli(10000)
        result = self.run_cli(10000, "--log-file", self.log,
                              env={**os.environ, "HONK_SECRET": "private-example-value"})
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected.stdout, b""))
        rows = self.events(b"prefix\n")
        self.assertEqual(len(rows), 10002)
        self.assertEqual(rows[0][1], b"started")
        self.assertEqual(rows[-1][1], b"returned")
        self.assertTrue(all(row[1] == b"item_completed" for row in rows[1:-1]))
        self.assertTrue(all(row[0] == b"INFO" and row[3] == b"0" for row in rows))
        self.assertNotIn(b"private-example-value", self.log.read_bytes())
        self.assertNotIn(str(self.log).encode(), self.log.read_bytes())

    def test_requested_failure_has_no_returned_event(self):
        result = self.run_cli(2, "--log-file", self.log, "--fail")
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (7, b"", b"requested operation failed\n"))
        rows = self.events()
        self.assertEqual(rows[-1][0:2], (b"ERROR", b"failed"))
        self.assertEqual(rows[-1][3], b"7")
        self.assertNotIn(b"returned", self.log.read_bytes())

    def test_private_creation_under_restrictive_umask(self):
        result = self.run_cli(0, "--log-file", self.log, umask=0o777)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)

    def test_invalid_file_destinations(self):
        target = self.root / "target"
        target.write_bytes(b"untouched")
        final_link = self.root / "link"
        final_link.symlink_to(target)
        directory_link = self.root / "directory-link"
        directory_link.symlink_to(self.root, target_is_directory=True)
        fifo = self.root / "fifo"
        os.mkfifo(fifo, 0o600)
        for path in (self.root, self.root / "missing" / "out", final_link,
                     directory_link / "new.log", fifo):
            with self.subTest(path=path.name):
                result = self.run_cli(0, "--log-file", path)
                self.assertEqual((result.returncode, result.stderr), (1, b"diagnostic log failed\n"))
        self.assertEqual(target.read_bytes(), b"untouched")
        self.assertFalse((self.root / "new.log").exists())

    def test_existing_mode_and_hardlink_rejected(self):
        self.private_file()
        self.log.chmod(0o644)
        self.assertEqual(self.sink(self.log, 1).returncode, 1)
        self.log.chmod(0o600)
        os.link(self.log, self.root / "hardlink")
        self.assertEqual(self.sink(self.log, 1).returncode, 1)
        self.assertEqual(self.log.read_bytes(), b"prefix\n")

    def test_busy_file_rejected_without_writes(self):
        self.private_file()
        with self.log.open("r+b") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.sink(self.log, 1).returncode, 1)
        self.assertEqual(self.log.read_bytes(), b"prefix\n")

    def test_line_and_file_caps(self):
        for size in (0, 16418):
            self.assertEqual(self.sink(self.log, size).returncode, 1)
            self.assertFalse(self.log.exists())
        self.assertEqual(self.sink(self.log, 16417).returncode, 0)
        self.assertEqual(self.log.read_bytes(), b"x" * 16417)
        with self.log.open("r+b") as handle:
            handle.truncate(CAP - 1)
        self.assertEqual(self.sink(self.log, 1).returncode, 0)
        self.assertEqual(self.log.stat().st_size, CAP)
        self.assertEqual(self.sink(self.log, 1).returncode, 1)
        self.assertEqual(self.log.stat().st_size, CAP)

    def test_real_partial_write_failure_is_not_retried(self):
        def limit():
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (16, 16))
        result = self.run_cli(0, "--log-file", self.log, preexec_fn=limit)
        self.assertEqual((result.returncode, result.stderr), (1, b"diagnostic log failed\n"))
        self.assertEqual(self.log.stat().st_size, 16)
        self.assertNotIn(b"\n", self.log.read_bytes())

    def test_configuration_filter_and_sticky_failure(self):
        delayed = self.root / "delayed"
        result = subprocess.run([STATE, str(self.log), str(delayed), str(delayed / "out")],
                                capture_output=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertFalse((delayed / "out").exists())
        self.assertEqual([row[1] for row in self.events()], [b"started", b"returned"])

    def test_standard_output_failure_never_logs_returned(self):
        with open("/dev/full", "wb") as output:
            result = subprocess.run([CONSUMER, "0", "--log-file", str(self.log)],
                                    stdout=output, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual((result.returncode, result.stderr), (1, b"cannot write standard output\n"))
        self.assertEqual([row[1] for row in self.events()], [b"started", b"failed"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
