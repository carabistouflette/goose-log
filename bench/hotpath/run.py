#!/usr/bin/env python3
"""Paired native callers with runtime fixtures and independent exact-byte checks."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import platform
import random
import statistics
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".build/hotpath/paired"
LABELS = (b"TRACE", b"DEBUG", b"INFO", b"WARN", b"ERROR", b"FATAL")


def command(args):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    if result.returncode:
        raise SystemExit(f"command failed: {args}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def expected(message, minimum=2, level=2):
    if minimum == 6 or level == 6 or level < minimum:
        return b"sentinel", False
    body = b"".join(b"\\\\" if c == 92 else bytes([c]) if 32 <= c <= 126
                    else f"\\x{c:02x}".encode() for c in message[:4096])
    suffix = b"... [truncated]" if len(message) > 4096 else b""
    return b"[" + LABELS[level] + b"] " + body + suffix + b"\n", True


def fixture(name, message, minimum=2, level=2, secondary=None):
    secondary = level if secondary is None else secondary
    output, accepted = expected(message, minimum, level)
    if expected(message, minimum, secondary) != (output, accepted):
        raise SystemExit("fixture levels must have identical expected output/status")
    data = struct.pack("<BBBBIIB", minimum, level, 0, secondary,
                       len(message), len(output), int(accepted)) + message + output
    path = CACHE / (name + ".bin")
    path.write_bytes(data)
    return dict(path=path, output=output, accepted=accepted, sha256=digest(data),
                message_bytes=len(message), minimum=minimum, level=level, secondary_level=secondary)


def invoke(binary, case, iterations, cpu):
    result = subprocess.run([str(binary), str(case["path"]), str(iterations)],
                            capture_output=True, text=True, timeout=60, check=True,
                            preexec_fn=lambda: os.sched_setaffinity(0, {cpu}))
    if result.stderr:
        raise SystemExit(f"unexpected driver diagnostics: {result.stderr}")
    row = json.loads(result.stdout)
    output = case["output"]
    full, tail = divmod(iterations, len(output))
    checksum = (full * (len(output) ** 2 + sum(output))
                + tail * len(output) + sum(output[:tail])) if case["accepted"] else 0
    calls = iterations if case["accepted"] else 0
    if (set(row) != {"elapsed_ns", "iterations", "calls", "checksum"}
            or row["iterations"] != iterations or row["calls"] != calls
            or row["checksum"] != checksum or row["elapsed_ns"] <= 0):
        raise SystemExit(f"incomplete or incorrect native result: {row}")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="full immutable baseline commit")
    parser.add_argument("--iterations", type=int, default=1000000)
    parser.add_argument("--rounds", type=int, default=9)
    parser.add_argument("--cpu", type=int, default=3)
    parser.add_argument("--build-cpu", type=int, default=5)
    parser.add_argument("--output", type=Path, default=CACHE / "results.json")
    parser.add_argument("--allow-dirty", action="store_true", help="exploration only; recorded in output")
    parser.add_argument("--smoke", action="store_true", help="correctness only, no useful timing")
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("this measurement runner currently requires Linux affinity support")
    available = os.sched_getaffinity(0)
    if args.cpu not in available or args.build_cpu not in available:
        parser.error("measurement/build CPU must be in the current affinity mask")
    if not 1 <= args.iterations <= 10000000 or not 1 <= args.rounds <= 25:
        parser.error("iterations must be 1..10000000; rounds must be 1..25")
    if len(args.baseline) != 40 or any(c not in "0123456789abcdef" for c in args.baseline):
        parser.error("baseline must be a full lowercase commit hash")
    os.sched_setaffinity(0, {args.build_cpu})
    goose = ROOT / ".toolchain/goose/build/goose"
    stdlib = ROOT / ".toolchain/goose/stdlib"
    source = command(["git", "rev-parse", "HEAD"])
    status = command(["git", "status", "--porcelain"])
    if status and not args.allow_dirty:
        raise SystemExit("source is dirty; commit before measuring, or use --allow-dirty for exploration")
    baseline = subprocess.check_output(["git", "show", args.baseline + ":logger.goose"], cwd=ROOT)
    baseline_compiler = command(["git", "show", args.baseline + ":GOOSE_REVISION"])
    library = (ROOT / "logger.goose").read_bytes()
    driver = (ROOT / "bench/hotpath/driver.goose").read_bytes()

    def inputs():
        return dict(library=digest((ROOT / "logger.goose").read_bytes()),
                    driver=digest((ROOT / "bench/hotpath/driver.goose").read_bytes()),
                    runner=digest(Path(__file__).read_bytes()),
                    compiler=digest(goose.read_bytes()),
                    compiler_revision=(ROOT / "GOOSE_REVISION").read_text().strip(),
                    stdlib={str(p.relative_to(stdlib)): digest(p.read_bytes())
                            for p in sorted(stdlib.rglob("*.goose"))})

    provenance = inputs()
    if not provenance["stdlib"]:
        raise SystemExit("missing pinned standard library; run make setup")
    if command(["git", "-C", ROOT / ".toolchain/goose", "rev-parse", "HEAD"]) != provenance["compiler_revision"]:
        raise SystemExit("compiler checkout does not match GOOSE_REVISION")
    binaries = {}
    for variant, contents in (("baseline", baseline), ("candidate", library)):
        directory = CACHE / variant
        (directory / "bench/hotpath").mkdir(parents=True, exist_ok=True)
        (directory / "logger.goose").write_bytes(contents)
        (directory / "bench/hotpath/driver.goose").write_bytes(driver)
        binary = directory / "driver"
        command([goose, "build", directory / "bench/hotpath/driver.goose", "-O2",
                 "--cc", "gcc", "--stdlib", stdlib, "-o", binary])
        binaries[variant] = binary
    hashes = {name: digest(path.read_bytes()) for name, path in binaries.items()}
    # Validate every named severity/minimum pair independently before timing.
    for minimum in range(7):
        for level in range(7):
            case = fixture("preflight", b"runtime threshold", minimum, level)
            for binary in binaries.values():
                invoke(binary, case, 1, args.cpu)
    messages = {"empty": b"", "short39": b"request completed status=200 bytes=1234"}
    messages.update({f"ascii{n}": b"a" * n for n in
                     (1, 15, 16, 17, 31, 32, 33, 64, 128, 256, 511, 512, 4096)})
    messages.update({"unsafe-first39": b"\xff" + b"a" * 38,
                     "unsafe-second39": b"a\xff" + b"a" * 37,
                     "unsafe-middle39": b"a" * 19 + b"\xff" + b"a" * 19,
                     "unsafe-last39": b"a" * 38 + b"\xff",
                     "escaped39": b"\xff" * 39, "backslashes39": b"\\" * 39,
                     "mixed39": bytes(range(39)), "mixed4096": bytes(range(256)) * 16,
                     "escaped4096": b"\xff" * 4096, "backslashes4096": b"\\" * 4096,
                     "oversized65536": b"a" * 65536})
    cases = {name: fixture(name, message) for name, message in messages.items()}
    for minimum, level in ((4, 1), (4, 2), (6, 5), (2, 0), (2, 1), (5, 4)):
        name = f"filtered-{minimum}-{level}"
        cases[name] = fixture(name, b"ignored", minimum, level)
    cases["filtered-mixed"] = fixture("filtered-mixed", b"ignored", 4, 1, 2)
    records = []
    rng = random.Random(0x6005E)
    rounds = 1 if args.smoke else args.rounds
    for round_number in range(rounds):
        order = list(cases)
        rng.shuffle(order)
        for name in order:
            variants = list(binaries)
            rng.shuffle(variants)
            case = cases[name]
            count = 10 if args.smoke else (args.iterations if case["message_bytes"] < 512
                                          else max(1000, args.iterations // 100))
            if not args.smoke and not case["accepted"]:
                count = min(10000000, args.iterations * 10)
            for variant in variants:
                row = invoke(binaries[variant], case, count, args.cpu)
                records.append(dict(round=round_number, variant=variant, case=name, **row))
        print(f"native round {round_number + 1}/{rounds}: exact output/counters/checksums passed", flush=True)
    if (inputs() != provenance or command(["git", "rev-parse", "HEAD"]) != source
            or command(["git", "status", "--porcelain"]) != status
            or any(digest(case["path"].read_bytes()) != case["sha256"] for case in cases.values())
            or {name: digest(path.read_bytes()) for name, path in binaries.items()} != hashes):
        raise SystemExit("source/compiler/stdlib/binary changed during measurement; discard this run")
    summary = []
    for case in cases:
        for variant in binaries:
            values = [r["elapsed_ns"] / r["iterations"] for r in records
                      if r["case"] == case and r["variant"] == variant]
            summary.append(dict(case=case, variant=variant, median_ns=statistics.median(values),
                                min_ns=min(values), max_ns=max(values)))
    cpu = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
               if line.startswith("model name"))
    result = dict(date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  source=source, dirty=bool(status), baseline=args.baseline,
                  baseline_original_compiler=baseline_compiler,
                  baseline_library_sha256=digest(baseline), build_inputs=provenance,
                  binaries=hashes, flags="Goose -O2, GCC -O2, no LTO/sanitizers",
                  goose=command([goose, "version"]), gcc=command(["gcc", "--version"]).splitlines()[0],
                  cpu=args.cpu, build_cpu=args.build_cpu, cpu_model=cpu, kernel=platform.release(),
                  rounds=rounds, iterations=args.iterations, warmup_calls=1000, smoke=args.smoke,
                  seed="0x6005e", fixtures={name: {k: v for k, v in case.items()
                      if k not in ("path", "output")} for name, case in cases.items()},
                  records=records, summary=summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {len(records)} checked samples to {args.output}")


if __name__ == "__main__":
    main()
