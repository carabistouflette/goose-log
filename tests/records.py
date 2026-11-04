#!/usr/bin/env python3
"""Independent byte oracle for bounded metadata and explicit sensitive fields."""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
NAMES = (b"TRACE", b"DEBUG", b"INFO", b"WARN", b"ERROR", b"FATAL")
COLORS = (b"\x1b[94m", b"\x1b[36m", b"\x1b[32m", b"\x1b[33m", b"\x1b[31m", b"\x1b[35m")


def escaped(data, cap, quoted=False):
    parts = []
    for value in data[:cap]:
        if value == 92 or (quoted and value == 34):
            parts.append(b"\\" + bytes([value]))
        elif 32 <= value <= 126:
            parts.append(bytes([value]))
        else:
            parts.append(f"\\x{value:02x}".encode("ascii"))
    if len(data) > cap:
        parts.append(b"... [truncated]")
    result = b"".join(parts)
    return b'"' + result + b'"' if quoted else result


def expected(case):
    minimum, level, color, line, message, timestamp, target, file, fields = case
    if level == 6 or minimum == 6 or level < minimum:
        return b"sentinel"
    out = (COLORS[level] if color else b"") + b"[" + NAMES[level] + b"]"
    out += (b"\x1b[0m" if color else b"") + b" "
    for name, text, cap in ((b"timestamp", timestamp, 64), (b"target", target, 64), (b"file", file, 256)):
        if text:
            out += name + b"=" + escaped(text, cap, True) + b" "
    if line:
        out += b"line=" + str(line).encode("ascii") + b" "
    for key, value, sensitive in fields[:8]:
        out += escaped(key, 64, True) + b"="
        out += b'"***"' if sensitive else escaped(value, 256, True)
        out += b" "
    if len(fields) > 8:
        out += b"[fields truncated] "
    return out + escaped(message, 4096) + b"\n"


def blob(text):
    return struct.pack("<I", len(text)) + text


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: records.py DRIVER [DRIVER ...]")
    rng = random.Random(0x5EC0AD)
    cases = []
    all_bytes = bytes(range(256))
    for minimum in range(7):
        for level in range(7):
            cases.append((minimum, level, bool(level % 2), 42, all_bytes,
                          all_bytes, all_bytes, all_bytes, [(all_bytes, all_bytes, False)]))
    for size in (0, 1, 63, 64, 65, 255, 256, 257, 4095, 4096, 4097):
        data = b"\xff" * size
        cases.append((0, 0, True, 4294967295, data, data, data, data, [(data, data, False)] * 9))
    for _ in range(100):
        values = [rng.randbytes(rng.choice((0, 5, 64, 65, 256, 257, 4097))) for _ in range(4)]
        fields = [(rng.randbytes(rng.randrange(100)), rng.randbytes(rng.randrange(300)),
                   bool(rng.randrange(2))) for _ in range(rng.randrange(12))]
        cases.append((0, rng.randrange(6), bool(rng.randrange(2)), rng.randrange(2**32),
                      *values, fields))
    with tempfile.TemporaryDirectory(prefix="records-", dir=ROOT / ".build") as tmp:
        source = Path(tmp) / "case.bin"
        for index, case in enumerate(cases):
            minimum, level, color, line, message, timestamp, target, file, fields = case
            wire = struct.pack("<BBBIB", minimum, level, color, line, len(fields))
            wire += b"".join(blob(text) for text in (message, timestamp, target, file))
            for key, value, sensitive in fields:
                wire += bytes([sensitive]) + blob(key) + blob(value)
            source.write_bytes(wire)
            oracle = expected(case)
            if len(oracle) > 28592:
                raise SystemExit("oracle output exceeded the documented bound")
            for driver in sys.argv[1:]:
                result = subprocess.run([str(Path(driver).resolve()), str(source)],
                                        capture_output=True, timeout=30)
                if result.returncode or result.stderr or result.stdout != oracle:
                    raise SystemExit(f"{driver}: record case {index} failed, exit={result.returncode}, "
                                     f"stderr={result.stderr!r}, got={result.stdout!r}, expected={oracle!r}")
    print(f"record oracle: {len(cases)} cases per driver passed; seed=0x5ec0ad")


if __name__ == "__main__":
    main()
