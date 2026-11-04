#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Separate real CLI message construction, rendering, and safe append costs."""
from pathlib import Path
import argparse
import collections
import datetime
import hashlib
import json
import os
import platform
import random
import shutil
import stat
import statistics
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / ".build/cli"
STDLIB = ROOT / ".toolchain/goose/stdlib"
STAGES = ("construction", "render", "append", "full", "adapter", "filtered")
NAMES = (b"started", b"item_completed", b"returned", b"failed", b"child_failed")
PREFIX = b"existing-log-prefix\n"
FILE_LIMIT = 16 * 1024 * 1024
WARMUP_LIMIT = 1024
FLAGS = {
    "goose": ["--standalone", "-O2", "--stdlib", "PINNED_STDLIB"],
    "generated_c": ["-O2", "-std=c11"],
    "sink_c": ["-O2", "-std=c11", "-Wall", "-Wextra", "-Werror"],
    "link": ["-lm", "-ldl", "-pthread"],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, cpu):
    try:
        result = subprocess.run(list(map(str, args)), cwd=ROOT, check=True,
                                capture_output=True, text=True, timeout=180,
                                preexec_fn=lambda: os.sched_setaffinity(0, {cpu}))
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"{Path(str(args[0])).name} failed:\n{error.stdout}{error.stderr}") from error
    return result.stdout.strip()


def inputs(goose, cpu):
    paths = ("logger.goose", "GOOSE_REVISION", "bench/cli/driver.goose", "bench/cli/run.py",
             "examples/cli/diagnostics.goose", "examples/cli/diagnostics.build", "examples/cli/log_sink.c")
    gcc = shutil.which("gcc")
    if not gcc:
        raise SystemExit("GCC is required")
    return dict(files={p: digest(ROOT / p) for p in paths}, flags=FLAGS,
                goose=command([goose, "version"], cpu), goose_binary_sha256=digest(goose),
                stdlib={str(p.relative_to(STDLIB)): digest(p)
                        for p in sorted(STDLIB.rglob("*.goose"))},
                gcc=command([gcc, "--version"], cpu).splitlines()[0],
                gcc_binary_sha256=digest(Path(gcc)))


def build(goose, cpu):
    command([goose, "--standalone", "-o", BUILD / "driver.c",
             "bench/cli/driver.goose", "-O2", "--stdlib", STDLIB], cpu)
    command(["gcc", *FLAGS["generated_c"], "-c", BUILD / "driver.c", "-o", BUILD / "driver.o"], cpu)
    command(["gcc", *FLAGS["sink_c"], "-c", "examples/cli/log_sink.c", "-o", BUILD / "log_sink.o"], cpu)
    command(["gcc", BUILD / "driver.o", BUILD / "log_sink.o", *FLAGS["link"], "-o", BUILD / "driver"], cpu)


def fixture(seed):
    rng = random.Random(seed)
    records = []
    for i in range(64):
        duration = rng.randrange(10**12)
        outcome = rng.randrange(2**32)
        if i == 0:
            duration, outcome = 0, 0
        elif i == 1:
            duration, outcome = 2**64 - 1, 2**32 - 1
        records.append((i % len(NAMES), duration, outcome))
    data = b"HNKBEN01" + seed.to_bytes(8, "big")
    data += b"".join(struct.pack(">BQI", *r) for r in records)
    messages = [NAMES[event] + b" duration_ns=" + str(duration).encode("ascii")
                + b" outcome=" + str(outcome).encode("ascii") for event, duration, outcome in records]
    lines = [(b"[ERROR] " if event >= 3 else b"[INFO] ") + message + b"\n"
             for (event, _, _), message in zip(records, messages)]
    return data, messages, lines


def totals(stage, count, messages, lines):
    if stage == "adapter":
        return dict(calls=count, builders=None, sinks=None, bytes=None, checksum=None, successful_returns=count)
    if stage == "filtered":
        return dict(calls=count, builders=0, sinks=0, bytes=0, checksum=0, successful_returns=None)
    values = messages if stage == "construction" else lines
    return dict(calls=count, successful_returns=None, builders=count if stage in ("construction", "full") else 0,
                sinks=count if stage in ("append", "full") else 0,
                bytes=sum(len(values[i % 64]) for i in range(count)),
                checksum=sum(len(values[i % 64]) + values[i % 64][i % len(values[i % 64])]
                             for i in range(count)))


def repeated_size(values, count):
    cycles, remainder = divmod(count, len(values))
    return cycles * sum(map(len, values)) + sum(map(len, values[:remainder]))


def output_bytes(stage, count, warmup, lines):
    if stage not in ("append", "full", "adapter"):
        return PREFIX
    return PREFIX + b"".join(lines[i % 64] for n in (warmup, count) for i in range(n))


def create_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, "wb") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(data)
    return path.stat().st_ino


def verify_file(path, expected, inode):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid() or info.st_nlink != 1 or info.st_ino != inode):
            raise SystemExit("profile output file metadata changed")
        actual = source.read(FILE_LIMIT + 1)
    if actual != expected:
        raise SystemExit("profile output differs from independent complete-byte oracle")
    return dict(file_bytes=len(actual), file_sha256=hashlib.sha256(actual).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--seed", type=int, default=0x6005E)
    parser.add_argument("--cpu", type=int, default=0)
    parser.add_argument("--build-cpu", type=int, default=3)
    parser.add_argument("--smoke", action="store_true", help="small dirty-tree validation; not publication data")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--goose", type=Path, default=ROOT / ".toolchain/goose/build/goose")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    args.iterations = args.iterations if args.iterations is not None else (16 if args.smoke else 20000)
    args.rounds = args.rounds if args.rounds is not None else (1 if args.smoke else 9)
    args.warmup = args.warmup if args.warmup is not None else (8 if args.smoke else 64)
    args.output = args.output or BUILD / ("smoke.json" if args.smoke else "results.json")
    if platform.system() != "Linux":
        parser.error("the shared application sink and affinity require Linux")
    if not 1 <= args.iterations <= 1000000 or not 1 <= args.rounds <= 25:
        parser.error("iterations must be 1..1000000 and rounds 1..25")
    if not 0 <= args.warmup <= WARMUP_LIMIT or not 0 <= args.seed <= 2147483647:
        parser.error("warmup must be 0..1024 and seed 0..2147483647")
    if args.smoke and (args.iterations > 64 or args.rounds > 2 or args.warmup > 64):
        parser.error("smoke validation is limited to 64 iterations/warmups and two rounds")
    available = os.sched_getaffinity(0)
    if args.cpu not in available or (not args.no_build and args.build_cpu not in available):
        parser.error("choose measurement/build CPUs in the process's available affinity set")
    # Pin validation/oracle work too. Build children explicitly move to build_cpu.
    os.sched_setaffinity(0, {args.cpu})
    goose = args.goose.resolve()
    source = command(["git", "rev-parse", "HEAD"], args.cpu)
    status = command(["git", "status", "--porcelain"], args.cpu)
    if status and not args.smoke:
        raise SystemExit("publication measurements require a clean source tree; use --smoke for validation")
    frozen = inputs(goose, args.cpu)
    if not frozen["stdlib"]:
        raise SystemExit("missing pinned standard library; run make setup")
    BUILD.mkdir(parents=True, exist_ok=True)
    manifest = BUILD / "build.json"
    if not args.no_build:
        build(goose, args.build_cpu)
        if frozen != inputs(goose, args.cpu):
            raise SystemExit("profile inputs changed during build; rerun")
        manifest.write_text(json.dumps(dict(inputs=frozen, driver_sha256=digest(BUILD / "driver"),
                                            build_cpu=args.build_cpu), indent=2) + "\n")
    if not manifest.exists():
        raise SystemExit("missing profile build manifest; rerun without --no-build")
    recorded = json.loads(manifest.read_text())
    if recorded["inputs"] != frozen or recorded["driver_sha256"] != digest(BUILD / "driver"):
        raise SystemExit("profile binary is stale or modified; rerun without --no-build")
    data, messages, lines = fixture(args.seed)
    fixture_path = BUILD / "events.bin"
    fixture_path.write_bytes(data)
    if len(PREFIX) + repeated_size(lines, args.warmup) + repeated_size(lines, args.iterations) > FILE_LIMIT:
        raise SystemExit("warmup plus measured output and existing prefix exceed the 16 MiB file cap")
    expectations = {stage: (totals(stage, args.iterations, messages, lines),
                            totals(stage, args.warmup, messages, lines),
                            output_bytes(stage, args.iterations, args.warmup, lines)) for stage in STAGES}
    proof_bytes = b"".join(messages) + b"".join(lines)
    records = []
    order_rng = random.Random(args.seed ^ 0x434C49)
    for round_number in range(args.rounds):
        order = list(STAGES)
        order_rng.shuffle(order)
        for stage in order:
            expected, warmed, file_bytes = expectations[stage]
            with tempfile.TemporaryDirectory(prefix="profile-", dir=BUILD) as directory:
                path = Path(directory) / "delivery.log"
                proof = Path(str(path) + ".proof")
                inode = create_private(path, PREFIX)
                proof_inode = create_private(proof, b"")
                relative = path.relative_to(ROOT)
                completed = subprocess.run([str(BUILD / "driver"), stage, str(fixture_path),
                    str(args.iterations), str(args.warmup), str(relative), str(args.seed),
                    "6" if stage == "filtered" else "2"],
                    cwd=ROOT, check=True, capture_output=True, text=True, timeout=180)
                if completed.stderr:
                    raise SystemExit(f"profile driver emitted diagnostics: {completed.stderr}")
                measured = json.loads(completed.stdout)
                if measured.get("minimum") != (6 if stage == "filtered" else 2):
                    raise SystemExit("profile minimum does not match the selected workload")
                for name, value in expected.items():
                    if measured.get(name) != value:
                        raise SystemExit(f"{stage}: {name} differs from independent oracle")
                for name, value in warmed.items():
                    if measured.get("warmup_" + name) != value:
                        raise SystemExit(f"{stage}: warmup {name} differs from independent oracle")
                if not isinstance(measured.get("elapsed_ns"), int) or measured["elapsed_ns"] < 0:
                    raise SystemExit("invalid elapsed nanoseconds")
                verified = verify_file(path, file_bytes, inode)
                proof_verified = verify_file(proof, proof_bytes, proof_inode)
                records.append(dict(round=round_number, stage=stage, path_components=len(relative.parts),
                                    **measured, **verified, proof_sha256=proof_verified["file_sha256"],
                                    validated_measured_file_bytes=repeated_size(lines, args.iterations)
                                    if stage in ("append", "full", "adapter") else 0))
        print(f"CLI profile round {round_number + 1}/{args.rounds}: all bytes and counters validated", flush=True)
    if (frozen != inputs(goose, args.cpu) or digest(BUILD / "driver") != recorded["driver_sha256"]
            or digest(fixture_path) != hashlib.sha256(data).hexdigest()
            or command(["git", "rev-parse", "HEAD"], args.cpu) != source
            or command(["git", "status", "--porcelain"], args.cpu) != status):
        raise SystemExit("source, compiler, standard library, fixture, or driver changed during profiling")
    groups = collections.defaultdict(list)
    for row in records:
        groups[row["stage"]].append(row["elapsed_ns"] / row["calls"])
    summary = [dict(stage=stage, median_ns=statistics.median(values), min_ns=min(values), max_ns=max(values))
               for stage, values in sorted(groups.items())]
    result = dict(date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), source=source,
                  dirty=bool(status), smoke=args.smoke, scope="CLI helper component pipelines, not whole-command latency",
                  build_inputs=frozen, driver_sha256=recorded["driver_sha256"],
                  goose_revision=(ROOT / "GOOSE_REVISION").read_text().strip(),
                  os=platform.system(), kernel=platform.release(), architecture=platform.machine(),
                  libc=platform.libc_ver(), page_size=os.sysconf("SC_PAGESIZE"),
                  filesystem=command(["stat", "-f", "-c", "%T", BUILD], args.cpu),
                  filesystem_block_size=os.statvfs(BUILD).f_bsize,
                  cpu_model=next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                                 if line.startswith("model name")),
                  cpu=args.cpu, build_cpu=recorded["build_cpu"], iterations=args.iterations, rounds=args.rounds,
                  warmup=args.warmup, seed=args.seed, file_limit=FILE_LIMIT,
                  fixture=dict(format="HNKBEN01 + big-endian u64 seed + 64 records of >BQI", bytes=len(data),
                               sha256=hashlib.sha256(data).hexdigest(), hex=data.hex()),
                  prefix=dict(bytes=len(PREFIX), sha256=hashlib.sha256(PREFIX).hexdigest()),
                  records=records, summary=summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {len(records)} validated CLI component samples to {args.output}")


if __name__ == "__main__":
    main()
