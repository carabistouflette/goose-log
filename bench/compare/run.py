#!/usr/bin/env python3
"""Pinned, validated, shuffled synchronous comparisons; no third-party vendoring."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".build/compare"
STDLIB = ROOT / ".toolchain/goose/stdlib"
PINS = {
    "logc": ("https://github.com/rxi/log.c.git", "f9ea34994bd58ed342d2245cd4110bb5c6790153"),
    "spdlog": ("https://github.com/gabime/spdlog.git", "79524ddd08a4ec981b7fea76afd08ee05f83755d"),
    "goose-logger": ("https://github.com/Macho0x/goose-logger.git", "50695a3df0eb5a1048a4b183538d59f43f5eb279"),
}


def command(args, **kwargs):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True, timeout=180, **kwargs).stdout.strip()


def sources(build):
    for name, (url, pin) in PINS.items():
        directory = CACHE / name
        if not directory.exists():
            if not build:
                raise SystemExit("missing comparison sources; rerun without --no-build")
            directory.mkdir()
            command(["git", "-C", directory, "init"])
            command(["git", "-C", directory, "remote", "add", "origin", url])
        if command(["git", "-C", directory, "remote", "get-url", "origin"]) != url:
            raise SystemExit(f"{name}: unexpected origin URL")
        if command(["git", "-C", directory, "status", "--porcelain"]):
            raise SystemExit(f"{name}: source checkout has local changes")
        if build:
            command(["git", "-C", directory, "fetch", "--depth", "1", "origin", pin])
            command(["git", "-C", directory, "checkout", "--detach", pin])
        if command(["git", "-C", directory, "rev-parse", "HEAD"]) != pin:
            raise SystemExit(f"{name}: checkout does not match comparison pin")


def build(goose):
    command([goose, "--standalone", "--header", CACHE / "goose_adapter.h", "-o",
             CACHE / "goose_adapter.c", "bench/compare/goose_adapter.goose", "-O2", "--stdlib", STDLIB])
    command(["gcc", "-O2", "-std=c99", "-I", CACHE / "logc/src", "-c",
             CACHE / "logc/src/log.c", "-o", CACHE / "logc.o"])
    command(["gcc", "-O2", "-c", CACHE / "goose_adapter.c", "-o", CACHE / "goose_adapter.o"])
    command(["g++", "-O2", "-std=c++17", "-I", CACHE, "-I", CACHE / "logc/src",
             "-I", CACHE / "spdlog/include", "bench/compare/driver.cpp", CACHE / "goose_adapter.o",
             CACHE / "logc.o", "-lm", "-pthread", "-ldl", "-o", CACHE / "driver"])


def build_inputs(goose):
    paths = ("logger.goose", "GOOSE_REVISION", "bench/compare/goose_adapter.goose",
             "bench/compare/driver.cpp", "bench/compare/run.py")
    return dict(files={path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
                dependencies=PINS, goose=command([goose, "version"]),
                goose_binary_sha256=hashlib.sha256(goose.read_bytes()).hexdigest(),
                stdlib={str(path.relative_to(STDLIB)): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sorted(STDLIB.rglob("*.goose"))},
                gcc=command(["gcc", "--version"]).splitlines()[0],
                gxx=command(["g++", "--version"]).splitlines()[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100000)
    parser.add_argument("--rounds", type=int, default=9)
    parser.add_argument("--cpu", type=int, default=0)
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--output", type=Path, default=CACHE / "results.json")
    parser.add_argument("--goose", type=Path, default=ROOT / ".toolchain/goose/build/goose")
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("this comparison runner currently requires Linux")
    if not 1 <= args.iterations <= 10000000 or not 1 <= args.rounds <= 25:
        parser.error("iterations must be 1..10000000; rounds must be 1..25")
    if args.cpu < 0 or args.cpu >= (os.cpu_count() or 1):
        parser.error("invalid CPU")
    CACHE.mkdir(parents=True, exist_ok=True)
    sources(not args.no_build)
    start_source = command(["git", "rev-parse", "HEAD"])
    start_status = command(["git", "status", "--porcelain"])
    inputs = build_inputs(args.goose.resolve())
    if not inputs["stdlib"]:
        raise SystemExit("missing pinned standard library; run make setup")
    manifest = CACHE / "build.json"
    if not args.no_build:
        build(args.goose.resolve())
        if inputs != build_inputs(args.goose.resolve()):
            raise SystemExit("benchmark inputs changed while building; rerun")
        manifest.write_text(json.dumps(dict(inputs=inputs,
            driver_sha256=hashlib.sha256((CACHE / "driver").read_bytes()).hexdigest()), indent=2) + "\n")
    if not manifest.exists():
        raise SystemExit("missing build manifest; rerun without --no-build")
    recorded = json.loads(manifest.read_text())
    # JSON serializes the dependency tuples as lists; normalize before comparison.
    if (recorded["inputs"] != json.loads(json.dumps(inputs))
            or recorded["driver_sha256"] != hashlib.sha256((CACHE / "driver").read_bytes()).hexdigest()):
        raise SystemExit("comparison binary is stale or modified; rerun without --no-build")
    fixtures = {
        "empty": b"", "short": b"request completed status=200 bytes=1234",
        "ascii512": b"a" * 512, "ascii4096": b"a" * 4096,
        "policy-hit": b"password=not-a-real-secret",
    }
    for name, data in fixtures.items():
        (CACHE / (name + ".txt")).write_bytes(data)
    adapters = ("goose-log", "log.c", "spdlog", "spdlog-supplied-time")
    jobs = [(adapter, case, 2, 2, args.iterations) for adapter in adapters
            for case in ("empty", "short", "ascii512", "ascii4096")]
    jobs += [(adapter, "short", 4, 1, args.iterations) for adapter in adapters]
    jobs += [(adapter, case, 2, 2, min(args.iterations, 1000))
             for adapter in ("macho-record", "goose-record+policy") for case in ("short", "policy-hit")]
    def invoke(adapter, case, minimum, level, count):
        result = subprocess.run([str(x) for x in (CACHE / "driver", adapter,
            CACHE / (case + ".txt"), count, minimum, level)], check=True, capture_output=True,
            text=True, timeout=180, preexec_fn=lambda: os.sched_setaffinity(0, {args.cpu}))
        if result.stderr:
            raise SystemExit(f"comparison driver emitted diagnostics: {result.stderr}")
        return json.loads(result.stdout)
    # Untimed, exhaustive shared-profile threshold/severity validation.
    for adapter in adapters:
        for minimum in range(7):
            for level in range(6):
                invoke(adapter, "short", minimum, level, 1)
    records = []
    rng = random.Random(0x6005E)
    for round_number in range(args.rounds):
        order = list(jobs)
        rng.shuffle(order)
        for adapter, case, minimum, level, count in order:
            measured = invoke(adapter, case, minimum, level, count)
            records.append(dict(round=round_number, adapter=adapter, case=case,
                                minimum=minimum, level=level, **measured))
        print(f"comparison round {round_number + 1}/{args.rounds}: all outputs/checksums validated", flush=True)
    if (command(["git", "rev-parse", "HEAD"]) != start_source
            or command(["git", "status", "--porcelain"]) != start_status
            or build_inputs(args.goose.resolve()) != inputs
            or hashlib.sha256((CACHE / "driver").read_bytes()).hexdigest() != recorded["driver_sha256"]):
        raise SystemExit("source, compiler, standard library, or driver changed during measurement; rerun")
    groups = {}
    for row in records:
        key = (row["adapter"], row["case"], row["minimum"], row["level"])
        groups.setdefault(key, []).append(row["elapsed_ns"] / row["iterations"])
    summary = [dict(adapter=k[0], case=k[1], minimum=k[2], level=k[3],
                    median_ns=statistics.median(v), min_ns=min(v), max_ns=max(v))
               for k, v in sorted(groups.items())]
    cpu = next((x.split(":", 1)[1].strip() for x in Path("/proc/cpuinfo").read_text().splitlines()
                if x.startswith("model name")), None)
    result = dict(date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  source=start_source,
                  dirty=bool(start_status),
                  goose_revision=(ROOT / "GOOSE_REVISION").read_text().strip(),
                  goose_version=command([args.goose.resolve(), "version"]),
                  compiler=command(["gcc", "--version"]).splitlines()[0],
                  cpp_compiler=command(["g++", "--version"]).splitlines()[0],
                  cpu_model=cpu, architecture=platform.machine(), cpu=args.cpu, os=platform.system(), kernel=platform.release(),
                  rounds=args.rounds, iterations=args.iterations, warmup_calls=1000,
                  seed="0x6005e", dependencies={k: dict(url=v[0], commit=v[1]) for k, v in PINS.items()},
                  fixtures={k: dict(bytes=len(v), sha256=hashlib.sha256(v).hexdigest()) for k, v in fixtures.items()},
                  driver_sha256=hashlib.sha256((CACHE / "driver").read_bytes()).hexdigest(),
                  build_inputs=inputs,
                  records=records, summary=summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {len(records)} validated samples to {args.output}")


if __name__ == "__main__":
    main()
