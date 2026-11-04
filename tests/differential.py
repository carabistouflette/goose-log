#!/usr/bin/env python3
"""Deterministic binary-input oracle, independent of Goose formatting code."""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
LABELS = (b"TRACE", b"DEBUG", b"INFO", b"WARN", b"ERROR", b"FATAL")
COLORS = (b"\x1b[94m", b"\x1b[36m", b"\x1b[32m", b"\x1b[33m", b"\x1b[31m", b"\x1b[35m")
ESCAPES = tuple(
    b"\\\\" if value == 92 else
    bytes([value]) if 32 <= value < 127 else
    f"\\x{value:02x}".encode("ascii")
    for value in range(256)
)


def oracle(message, level, color):
    label = b"[" + LABELS[level] + b"]"
    if color:
        label = COLORS[level] + label + b"\x1b[0m"
    payload = b"".join(ESCAPES[value] for value in message[:4096])
    suffix = b"... [truncated]" if len(message) > 4096 else b""
    result = label + b" " + payload + suffix + b"\n"
    assert len(result) <= 16417
    # Removing our trusted color sequences leaves exactly one raw control: LF.
    plain = result
    if color:
        plain = plain[len(COLORS[level]):].replace(b"\x1b[0m", b"", 1)
    assert plain.endswith(b"\n")
    assert all(32 <= value < 127 for value in plain[:-1])
    return result


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: differential.py DRIVER [DRIVER ...]")
    rng = random.Random(0x6005E)
    cases = []
    for minimum in range(7):
        for level in range(7):
            for color in (False, True):
                for sink_ok in (False, True):
                    cases.append((minimum, level, color, sink_ok, bytes(range(256))))
    # Exercise every cap boundary across distributions and output modes.
    for size in (0, 1, 2, 4095, 4096, 4097, 8192, 1048576):
        for value in (0, 27, 65, 92, 127, 255):
            for color in (False, True):
                cases.append((0, 0, color, True, bytes([value]) * size))
    for _ in range(1500):
        size = rng.choice((rng.randrange(8193), 0, 4095, 4096, 4097))
        message = rng.randbytes(size)
        cases.append((rng.randrange(7), rng.randrange(7),
                      bool(rng.randrange(2)), bool(rng.randrange(2)), message))
    rng.shuffle(cases)
    previous = b"sentinel"
    fixtures = bytearray()
    for minimum, level, color, sink_ok, message in cases:
        accepted = level != 6 and minimum != 6 and level >= minimum
        if accepted:
            previous = oracle(message, level, color)
        status = (1 if sink_ok else 2) if accepted else 0
        fixtures.extend(struct.pack("<BBBBIIB", minimum, level, color, sink_ok,
                                    len(message), len(previous), status))
        fixtures.extend(message)
        fixtures.extend(previous)
    with tempfile.TemporaryDirectory(prefix="differential-", dir=ROOT / ".build") as tmp:
        source = Path(tmp) / "cases.bin"
        source.write_bytes(fixtures)
        for driver in sys.argv[1:]:
            result = subprocess.run([str(Path(driver).resolve()), str(source)],
                                    capture_output=True, text=True, timeout=60)
            expected = f"differential cases passed: {len(cases)}\n"
            if result.returncode != 0 or result.stdout != expected or result.stderr:
                raise SystemExit(f"{driver}: incomplete or failed oracle run "
                                 f"(exit {result.returncode})\n"
                                 f"stdout: {result.stdout}\nstderr: {result.stderr}")
            print(result.stdout, end="")
    print(f"independent oracle: {len(cases)} cases per driver; seed=0x6005e")


if __name__ == "__main__":
    main()
