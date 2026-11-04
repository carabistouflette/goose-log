#!/usr/bin/env python3
"""Measure explicit allocation calls and runtime arena snapshots, not timings."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / ".build/alloc"
STDLIB = ROOT / ".toolchain/goose/stdlib"
PHASES = ("control", "init", "cold-plain", "warm-plain", "cold-record",
          "warm-record", "cold-filtered", "warm-filtered")
WRAPS = ("malloc", "calloc", "realloc", "free", "mmap", "mprotect", "munmap", "madvise")


def command(args):
    return subprocess.run(list(map(str, args)), cwd=ROOT, check=True,
                          capture_output=True, text=True, timeout=180).stdout.strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(goose):
    paths = ("logger.goose", "GOOSE_REVISION", "bench/alloc/probe.goose",
             "bench/alloc/driver.c", "bench/alloc/run.py")
    return dict(files={name: digest(ROOT / name) for name in paths},
                goose_version=command([goose, "version"]), goose_binary_sha256=digest(goose),
                stdlib={str(p.relative_to(STDLIB)): digest(p)
                        for p in sorted(STDLIB.rglob("*.goose"))},
                cc=command(["gcc", "--version"]).splitlines()[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--output", type=Path, default=BUILD / "results.json")
    parser.add_argument("--goose", type=Path, default=ROOT / ".toolchain/goose/build/goose")
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("this instrumentation requires Linux and GNU-compatible linker wrapping")
    if not 1 <= args.iterations <= 1000000:
        parser.error("iterations must be 1..1000000")
    goose = args.goose.resolve()
    frozen = inputs(goose)
    if not frozen["stdlib"]:
        raise SystemExit("missing pinned standard library; run make setup")
    source = command(["git", "rev-parse", "HEAD"])
    status = command(["git", "status", "--porcelain"])
    BUILD.mkdir(parents=True, exist_ok=True)
    command([goose, "--standalone", "--header", BUILD / "allocation_probe.h", "-o",
             BUILD / "allocation_probe.c", "bench/alloc/probe.goose", "-O2", "--stdlib", STDLIB])
    flags = ["-O2", "-std=c11", "-fno-builtin-malloc", "-fno-builtin-calloc",
             "-fno-builtin-realloc", "-fno-builtin-free"]
    command(["gcc", *flags, "-I", BUILD, "bench/alloc/driver.c", "-o", BUILD / "driver",
             *["-Wl,--wrap=" + name for name in WRAPS], "-lm", "-ldl", "-pthread"])
    binary_hash = digest(BUILD / "driver")
    records = []
    for phase in PHASES:
        result = subprocess.run([str(BUILD / "driver"), phase, str(args.iterations)],
                                cwd=ROOT, check=True, capture_output=True, text=True, timeout=180)
        if result.stderr:
            raise SystemExit(f"allocation probe emitted diagnostics: {result.stderr}")
        row = json.loads(result.stdout)
        if row["phase"] != phase:
            raise SystemExit("allocation probe phase mismatch")
        records.append(row)
        print(f"allocation phase {phase}: output and counters validated", flush=True)
    if (inputs(goose) != frozen or digest(BUILD / "driver") != binary_hash
            or command(["git", "rev-parse", "HEAD"]) != source
            or command(["git", "status", "--porcelain"]) != status):
        raise SystemExit("measurement inputs changed during the probe; rerun")
    output = dict(date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  source=source, dirty=bool(status), build_inputs=frozen,
                  flags=flags, linker_wraps=WRAPS, driver_sha256=binary_hash,
                  os=platform.system(), kernel=platform.release(), page_size=os.sysconf("SC_PAGESIZE"),
                  iterations=args.iterations,
                  measured_input=dict(bytes=4097, byte_value=255), records=records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"wrote {len(records)} allocation phases to {args.output}")


if __name__ == "__main__":
    main()
