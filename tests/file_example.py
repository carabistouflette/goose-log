#!/usr/bin/env python3
"""Exercise the real append adapter and its error status using explicit paths."""
from pathlib import Path
import subprocess
import sys
import tempfile


def run(binary, *args):
    return subprocess.run([str(binary), *map(str, args)], capture_output=True,
                          timeout=30)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: file_example.py FILE_EXAMPLE_BINARY")
    binary = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="goose-log-file-") as temporary:
        root = Path(temporary)
        output = root / "output.log"
        output.write_bytes(b"existing\n")
        for _ in range(2):
            result = run(binary, output)
            assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")
        assert output.read_bytes() == b"existing\n" + 2 * b"[INFO] Hello, file!\n"
        for bad_path in (root, root / "missing" / "output.log"):
            result = run(binary, bad_path)
            assert (result.returncode, result.stdout, result.stderr) == (
                1, b"", b"file sink failed\n")
        result = run(binary)
        assert (result.returncode, result.stdout, result.stderr) == (
            2, b"", b"usage: file PATH\n")
        # Linux's full device opens successfully but rejects output, covering
        # a failure after opening (usually reported by stdio during close).
        if sys.platform.startswith("linux") and Path("/dev/full").exists():
            result = run(binary, "/dev/full")
            assert (result.returncode, result.stdout, result.stderr) == (
                1, b"", b"file sink failed\n")
    print("file example: append, open failures, usage and available full-device checks passed")


if __name__ == "__main__":
    main()
