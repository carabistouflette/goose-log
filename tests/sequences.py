#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Seeded mixed-operation state oracle; replay and bounded failure reduction."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import random
import re
import struct
import shutil
import subprocess
import sys
import tempfile
import time

from differential import oracle as plain_bytes
from records import expected as record_bytes

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".build/sequences"
SEEDS = (0x6005E, 0x5EC0AD, 0, 0xFFFFFFFF)


def workspace_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("logger.goose", "GOOSE_REVISION", "tests/sequences.goose",
                         "tests/sequences.py", "tests/differential.py", "tests/records.py")}


def driver_hashes(driver):
    hashes = {"driver": hashlib.sha256(driver.read_bytes()).hexdigest()}
    if driver == (ROOT / "tests/sequences_jit.sh").resolve():
        selected = os.environ.get("GOOSE", str(ROOT / ".toolchain/goose/build/goose"))
        compiler = Path(shutil.which(selected) or selected).resolve()
        hashes["jit_compiler"] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    return hashes


def operation(op=0, minimum=0, level=2, message=b"", **extra):
    return dict(op=op, minimum=minimum, level=level, message=message.hex(),
                color=extra.get("color", False), sink=extra.get("sink", True),
                line=extra.get("line", 0), timestamp=extra.get("timestamp", b"").hex(),
                target=extra.get("target", b"").hex(), file=extra.get("file", b"").hex(),
                fields=[(k.hex(), v.hex(), s) for k, v, s in extra.get("fields", [])])


def generate(seed, steps):
    rng = random.Random(seed)
    full = b"\xff" * 4097
    cases = [operation(2, message=full, level=0, color=True, line=4294967295,
                       timestamp=full, target=full, file=full, fields=[(full, full, False)] * 9),
             operation(0, minimum=6, message=b"filtered after maximum record"),
             operation(4, minimum=6), operation(5, sink=False, message=b"owned failure"),
             operation(6, message=b"caller prefill\x00\xff")]
    for op in range(6):
        for minimum in range(7):
            for level in range(7):
                cases.append(operation(op, minimum, level, bytes(range(256)),
                                       color=bool((minimum + op) % 2), sink=bool((level + op) % 2),
                                       fields=[(b'k"', b"value\n", True)]))
    sizes = (0, 1, 15, 16, 17, 63, 64, 65, 255, 256, 257, 511, 512, 4095, 4096, 4097, 8192)

    def data(cap):
        size = rng.choice((0, 1, cap - 1, cap, cap + 1, rng.randrange(cap + 2)))
        distribution = rng.randrange(4)
        if distribution == 0:
            return b"a" * size
        if distribution == 1:
            return b"\\" * size
        if distribution == 2:
            return b"\xff" * size
        return rng.randbytes(size)

    for index in range(steps):
        size = rng.choice(sizes)
        message = data(size) if size else b""
        # Force exact chosen boundaries as well as nearby random sizes.
        if index % 3 == 0:
            message = rng.randbytes(size)
        fields = [(data(64), data(256), bool(rng.randrange(2)))
                  for _ in range(rng.choice((0, 1, 7, 8, 9, 12)))]
        cases.append(operation(rng.randrange(7), rng.choice((0, 0, rng.randrange(7))),
                               rng.randrange(7), message, color=bool(rng.randrange(2)),
                               sink=bool(rng.randrange(2)), line=rng.choice((0, 1, 4294967295, rng.randrange(2**32))),
                               timestamp=data(64), target=data(64), file=data(256), fields=fields))
    return cases


def blob(data):
    return struct.pack("<I", len(data)) + data


def encode(cases):
    scratch, retained = b"sentinel", b"capture"
    wire = bytearray()
    for c in cases:
        op, minimum, level = c["op"], c["minimum"], c["level"]
        message, timestamp, target, file = (bytes.fromhex(c[k]) for k in ("message", "timestamp", "target", "file"))
        fields = [(bytes.fromhex(k), bytes.fromhex(v), s) for k, v, s in c["fields"]]
        accepted = minimum != 6 and level != 6 and level >= minimum
        calls = builds = 0
        if op == 6:
            scratch, result = message, 3
        elif not accepted:
            result = 0
        else:
            if op in (2, 3):
                scratch = record_bytes((minimum, level, c["color"], c["line"], message,
                                        timestamp, target, file, fields))
                bound = 28592
            else:
                scratch = plain_bytes(message, level, c["color"])
                bound = 16417
            if len(scratch) > bound:
                raise ValueError("independent oracle exceeded accepted output bound")
            calls = int(op in (1, 3, 4, 5))
            builds = int(op in (4, 5))
            if calls:
                retained = scratch
            result = 2 if calls and not c["sink"] else 1
        wire.extend(struct.pack("<BBBBBBI", op, minimum, level, c["color"], c["sink"], len(fields), c["line"]))
        wire.extend(b"".join(blob(text) for text in (message, timestamp, target, file)))
        for key, value, sensitive in fields:
            wire.extend(bytes([sensitive]) + blob(key) + blob(value))
        wire.extend(bytes([result, builds, calls]) + blob(scratch) + blob(retained))
    return bytes(wire)


def run(driver, cases, path, timeout=90):
    path.write_bytes(encode(cases))
    result = subprocess.run([str(driver), str(path)], capture_output=True, timeout=timeout)
    good = result.returncode == 0 and not result.stderr and result.stdout == f"sequence operations passed: {len(cases)}\n".encode()
    match = re.search(rb"sequence failure step=\d+ check=([a-z-]+)", result.stdout)
    # Only explicit driver checks are reducible, never a parser error/timeout.
    signature = match[1].decode() if result.returncode and match else None
    return good, signature, result


def reduce_failure(driver, cases, signature, path, budget=64):
    remaining = list(cases)
    granularity = 2
    attempts = 0
    deadline = time.monotonic() + 20
    while len(remaining) >= 2 and attempts < budget and time.monotonic() < deadline:
        chunk = (len(remaining) + granularity - 1) // granularity
        changed = False
        for start in range(0, len(remaining), chunk):
            trial = remaining[:start] + remaining[start + chunk:]
            if not trial:
                continue
            attempts += 1
            try:
                good, found, _ = run(driver, trial, path, timeout=min(5, max(0.01, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                good, found = False, None
            if not good and found == signature:
                remaining = trial
                granularity = max(2, granularity - 1)
                changed = True
                break
            if attempts >= budget or time.monotonic() >= deadline:
                break
        if not changed:
            if granularity >= len(remaining):
                break
            granularity = min(len(remaining), granularity * 2)
    return remaining, attempts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drivers", nargs="+", type=Path)
    parser.add_argument("--seed", action="append", type=lambda s: int(s, 0))
    parser.add_argument("--steps", type=int, default=256, help="random steps after 299 fixed transitions per seed")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--minimize", action="store_true")
    parser.add_argument("--allow-new-driver", action="store_true", help="explicitly replay changed binaries or workspace sources")
    args = parser.parse_args()
    if not 0 <= args.steps <= 10000:
        parser.error("steps must be 0..10000")
    CACHE.mkdir(parents=True, exist_ok=True)
    drivers = [path.resolve() for path in args.drivers]
    for driver in drivers:
        if not driver.is_file():
            parser.error(f"driver is not a file: {driver}")
    replay = json.loads(args.replay.read_text()) if args.replay else None
    if replay and "driver_sha256" in replay and not args.allow_new_driver:
        for driver in drivers:
            if driver_hashes(driver) != replay.get("executables", {"driver": replay["driver_sha256"]}):
                parser.error("replay binary differs; use --allow-new-driver to test a rebuilt/fixed driver")
        if replay.get("sources", workspace_hashes()) != workspace_hashes():
            parser.error("replay workspace differs; use --allow-new-driver to test changed sources/oracles")
    seeds = args.seed if args.seed is not None else SEEDS
    batches = ((str(seed), generate(seed, args.steps)) for seed in seeds) if replay is None else [(str(args.replay), replay["cases"])]
    for seed, cases in batches:
        with tempfile.TemporaryDirectory(prefix="run-", dir=CACHE) as tmp:
            fixture = Path(tmp) / "sequence.bin"
            for driver in drivers:
                executables = driver_hashes(driver)
                timed_out = False
                try:
                    good, signature, result = run(driver, cases, fixture)
                except subprocess.TimeoutExpired as error:
                    good, signature, result, timed_out = False, None, error, True
                if driver_hashes(driver) != executables:
                    raise SystemExit("driver or JIT compiler changed during execution; rerun without concurrent builds")
                if not good:
                    failure = Path(tempfile.mkdtemp(prefix="failure-", dir=CACHE))
                    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
                    payload = dict(seed=seed, driver=str(driver), cases=cases, argv=sys.argv,
                                   timed_out=timed_out, returncode=getattr(result, "returncode", None),
                                   commit=git.stdout.strip() if git.returncode == 0 else None,
                                   driver_sha256=executables["driver"], executables=executables,
                                   sources=workspace_hashes())
                    (failure / "original.json").write_text(json.dumps(payload, indent=2) + "\n")
                    (failure / "original.bin").write_bytes(encode(cases))
                    if result is not None:
                        (failure / "stdout.bin").write_bytes(result.stdout or b"")
                        (failure / "stderr.bin").write_bytes(result.stderr or b"")
                    if args.minimize and signature:
                        reduced, attempts = reduce_failure(driver, cases, signature, fixture)
                        try:
                            confirmed, found, _ = run(driver, reduced, fixture, timeout=5)
                        except subprocess.TimeoutExpired:
                            confirmed, found = False, None
                        if not confirmed and found == signature:
                            payload.update(cases=reduced, signature=signature, attempts=attempts)
                            (failure / "reduced.json").write_text(json.dumps(payload, indent=2) + "\n")
                            (failure / "reduced.bin").write_bytes(encode(reduced))
                        else:
                            (failure / "reduction-unconfirmed.txt").write_text("Reduced check did not repeat; replay original.json.\n")
                    raise SystemExit(f"sequence failed: seed={seed}, driver={driver}, artifacts={failure}")
                print(f"sequence seed={seed}: {len(cases)} operations passed by {driver.name}; fixture_sha256={hashlib.sha256(fixture.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
