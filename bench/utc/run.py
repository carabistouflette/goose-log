#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Optional UTC consumer measurements with runtime inputs and independent bytes."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import statistics
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TIME_REVISION = "343887caeee0a1f4e2e536ff322fcafb454e11bd"
STAGES = ("plain_record", "preformatted_record", "format_only", "adapter_fixed",
          "adapter_os", "filtered_record", "filtered_adapter", "clock_only")
SOURCES = ("logger.goose", "GOOSE_REVISION", "examples/utc/utc.goose",
           "bench/utc/driver.goose", "bench/utc/run.py")
SEED = 3339


def digest(data):
    return hashlib.sha256(data).hexdigest()


def command(argv, *, env=None, cpu=None):
    result = subprocess.run([str(x) for x in argv], cwd=ROOT, env=env, text=True,
                            capture_output=True, timeout=180,
                            preexec_fn=(lambda: os.sched_setaffinity(0, {cpu})) if cpu is not None else None)
    if result.returncode:
        raise SystemExit(f"command failed ({result.returncode}): {argv}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def timestamp(ns):
    seconds, fraction = divmod(ns, 1_000_000_000)
    value = dt.datetime(1970, 1, 1) + dt.timedelta(seconds=seconds)
    text = (f"{value.year:04}-{value.month:02}-{value.day:02}T"
            f"{value.hour:02}:{value.minute:02}:{value.second:02}")
    if fraction:
        text += f".{fraction:09}".rstrip("0")
    return (text + "Z").encode("ascii")


def line(message, stamp=b""):
    prefix = b"[INFO] " + (b'timestamp="' + stamp + b'" ' if stamp else b"")
    escaped = b"".join(b"\\\\" if c == 92 else bytes([c]) if 32 <= c <= 126
                       else f"\\x{c:02x}".encode("ascii") for c in message[:4096])
    return prefix + escaped + (b"... [truncated]" if len(message) > 4096 else b"") + b"\n"


def checksum(data):
    return len(data) + sum((i + 1) * byte for i, byte in enumerate(data))


def fixture(name, rng):
    samples = [-(1 << 63), -1, 0, 1, 1_000_000_000, 951_827_696_123_400_000,
               1_793_813_400_123_456_789, (1 << 63) - 1]
    items = []
    data = bytearray((2, 6, 2, 0))
    for i, ns in enumerate(samples):
        if i in (3, 6):
            ns += rng.randrange(1_000_000)
        message = (f"item={i} outcome={rng.randrange(10000)} ready".encode("ascii") if name == "ascii"
                   else b"record\x00\xff\n\t\\\x1b payload=" + str(rng.randrange(10000)).encode("ascii"))
        stamp = timestamp(ns)
        plain, record = line(message), line(message, stamp)
        data.extend(struct.pack("<q", ns))
        for blob in (message, stamp, plain, record):
            data.extend(struct.pack("<I", len(blob)))
            data.extend(blob)
        items.append(dict(ns=ns, message=message, timestamp=stamp, plain=plain, record=record))
    return bytes(data), items


def total_cycle(blobs, count):
    whole, tail = divmod(count, len(blobs))
    return (whole * sum(len(x) for x in blobs) + sum(len(x) for x in blobs[:tail]),
            whole * sum(checksum(x) for x in blobs) + sum(checksum(x) for x in blobs[:tail]))


def verify(row, stage, items, count, trace):
    required = {"elapsed_ns", "iterations", "sinks", "clocks", "written", "filtered",
                "formatted", "bytes", "checksum", "last_ns", "timestamp_hex", "line_hex"}
    if set(row) != required or row["iterations"] != count or row["elapsed_ns"] <= 0:
        raise SystemExit(f"invalid benchmark result: {row}")
    sinks = count if stage in (0, 1, 3, 4) else 0
    expected = dict(sinks=sinks, clocks=count if stage in (3, 4, 7) else 0,
                    written=sinks, filtered=count if stage in (5, 6) else 0,
                    formatted=count if stage == 2 else 0)
    for field, value in expected.items():
        if row[field] != value:
            raise SystemExit(f"{STAGES[stage]} incorrect {field}: {row[field]} != {value}")
    last = items[(count - 1) % len(items)]
    final_stamp, final_line = b"stamp-sentinel", b"line-sentinel"
    if stage in (0, 1, 2, 3):
        key = "plain" if stage == 0 else "timestamp" if stage == 2 else "record"
        byte_count, wanted_checksum = total_cycle([item[key] for item in items], count)
        if stage in (2, 3):
            final_stamp = last["timestamp"]
        if stage != 2:
            final_line = last[key]
    elif stage in (4, 7):
        if len(trace) != count * 8:
            raise SystemExit("incomplete OS sample trace")
        samples = [entry[0] for entry in struct.iter_unpack("<q", trace)]
        if row["last_ns"] != samples[-1]:
            raise SystemExit("last OS sample mismatch")
        byte_count = wanted_checksum = 0
        if stage == 4:
            for i, sample in enumerate(samples):
                output = line(items[i % len(items)]["message"], timestamp(sample))
                byte_count += len(output)
                wanted_checksum += checksum(output)
            final_stamp = timestamp(samples[-1])
            final_line = line(last["message"], final_stamp)
        else:
            wanted_checksum = sum(sample % 1_000_000 for sample in samples)
    else:
        byte_count = wanted_checksum = 0
    if row["bytes"] != byte_count or row["checksum"] != wanted_checksum:
        raise SystemExit(f"{STAGES[stage]} independent full-byte checksum/count mismatch")
    if bytes.fromhex(row["timestamp_hex"]) != final_stamp or bytes.fromhex(row["line_hex"]) != final_line:
        raise SystemExit(f"{STAGES[stage]} independent complete final-byte mismatch")
    if stage == 3 and row["last_ns"] != last["ns"]:
        raise SystemExit("fixed clock last sample mismatch")
    if stage not in (3, 4, 7) and row["last_ns"] != 0:
        raise SystemExit("unexpected sampled clock")


def snapshot(goose, compiler_root):
    result = {name: digest((ROOT / name).read_bytes()) for name in SOURCES}
    result["compiler_binary"] = digest(goose.read_bytes())
    for directory in ("stdlib", "src/runtime"):
        for path in sorted((compiler_root / directory).rglob("*")):
            if path.is_file():
                result["compiler/" + path.relative_to(compiler_root).as_posix()] = digest(path.read_bytes())
    return result


def dependency_snapshot(cache):
    candidates = list(cache.rglob("time.goose"))
    if len(candidates) != 1:
        raise SystemExit(f"expected one isolated time dependency checkout, got {len(candidates)}")
    directory = candidates[0].parent
    revision = command(["git", "-C", directory, "rev-parse", "HEAD"])
    dirty = command(["git", "-C", directory, "status", "--porcelain"])
    if revision != TIME_REVISION or dirty:
        raise SystemExit("time dependency checkout is modified or has the wrong revision")
    return {"revision": revision,
            "files": {name: digest((directory / name).read_bytes())
                      for name in ("time.goose", "detail.goose", "GOOSE_REVISION")}}


def verify_compiler_version(version, revision):
    # Goose advertises a short revision; also retain the exact executable hash.
    match = re.match(r"\Agoose ([0-9a-f]{7,40})(?:\s|$)", version)
    if match is None or not revision.startswith(match[1]):
        raise SystemExit("compiler executable advertised revision does not match GOOSE_REVISION")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goose", default=os.environ.get("GOOSE", str(ROOT / ".toolchain/goose/build/goose")))
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--iterations", type=int, default=100000)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=64)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--build-cpu", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true", help="Exploration only; dirty state recorded")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--retain-traces", action="store_true", help="Retain compressed full OS traces; smoke always retains")
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("this optional measurement tool currently validates Linux affinity only")
    available = sorted(os.sched_getaffinity(0))
    cpu = available[0] if args.cpu is None else args.cpu
    build_cpu = available[-1] if args.build_cpu is None else args.build_cpu
    if cpu not in available or build_cpu not in available:
        parser.error("CPU must be available in the current affinity mask")
    if not 1 <= args.iterations <= 1000000 or not 1 <= args.rounds <= 25 or not 0 <= args.warmup <= 1024:
        parser.error("iterations 1..1000000, rounds 1..25, warmup 0..1024 required")
    if args.smoke:
        args.iterations = min(args.iterations, 64)
        args.rounds = min(args.rounds, 2)
    output = args.output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("output directory must be absent or empty; existing evidence is never overwritten")
    goose = Path(shutil.which(args.goose) or args.goose).resolve()
    compiler_root = goose.parents[1]
    source = command(["git", "rev-parse", "HEAD"])
    dirty = command(["git", "status", "--porcelain"])
    if dirty and not (args.allow_dirty or args.smoke):
        parser.error("source tree is dirty; commit first or explicitly use --allow-dirty")
    compiler_revision = command(["git", "-C", compiler_root, "rev-parse", "HEAD"])
    if compiler_revision != (ROOT / "GOOSE_REVISION").read_text().strip():
        parser.error("compiler source checkout does not match GOOSE_REVISION")
    compiler_version = command([goose, "version"])
    verify_compiler_version(compiler_version, compiler_revision)
    before = snapshot(goose, compiler_root)
    output.mkdir(parents=True, exist_ok=True)
    cache = ROOT / ".build/utc/cache"
    build = ROOT / ".build/utc/build"
    build.mkdir(parents=True, exist_ok=True)
    executable = build / ("driver-" + output.name)
    env = os.environ.copy()
    cleared = ("GOOSE_CC", "GOOSE_STDLIB", "CFLAGS", "CPPFLAGS", "CXXFLAGS", "LDFLAGS")
    for name in cleared:
        env.pop(name, None)
    env.update(GOOSE_HOME=str(cache), LC_ALL="C")
    flags = ["--cc", args.cc, "-O2", "--standalone"]
    command([goose, "build", "bench/utc/driver.goose", *flags, "-o", executable], env=env, cpu=build_cpu)
    dependency = dependency_snapshot(cache)
    binary_hash = digest(executable.read_bytes())
    metadata = dict(schema=1, created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    source_commit=source, source_dirty=bool(dirty), source_status=dirty,
                    source_hashes=before, dependency=dependency, compiler_revision=compiler_revision,
                    compiler_version=compiler_version,
                    compiler_tracked_status=command(["git", "-C", compiler_root, "status", "--porcelain", "--untracked-files=no"]),
                    cc=args.cc, cc_version=command([args.cc, "--version"]), flags=flags,
                    cleared_environment=list(cleared), executable_sha256=binary_hash,
                    platform=platform.platform(), machine=platform.machine(),
                    cpu_model=next((entry.split(":", 1)[1].strip() for entry in Path("/proc/cpuinfo").read_text().splitlines() if entry.startswith("model name")), "unknown"),
                    affinity=available, measurement_cpu=cpu, build_cpu=build_cpu, python=platform.python_version(),
                    iterations=args.iterations, rounds=args.rounds, warmup=args.warmup, seed=SEED, smoke=args.smoke,
                    retain_traces=args.retain_traces or args.smoke, validation="pending",
                    limitations=["Shared host; CPU frequency/turbo and thermal state uncontrolled; no isolated core.",
                    "Loop/indexing, runtime stage dispatch, counters, status checks and full-byte checksums are timed.",
                    "Clock stages include per-sample trace stores; serialization and verification are outside timing.",
                    "Without --retain-traces full OS traces are independently checked then discarded; trace hashes and all batch results remain.",
                    "Batch averages are not individual-call latency distributions; stages cannot be subtracted as an exact decomposition."])
    def save_metadata():
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    save_metadata()
    rng = random.Random(SEED)
    cases = {}
    (output / "fixtures").mkdir()
    (output / "traces").mkdir()
    for name in ("ascii", "escaped"):
        data, items = fixture(name, rng)
        path = output / "fixtures" / (name + ".bin")
        path.write_bytes(data)
        cases[name] = (path, items)
    metadata["fixtures"] = {name: {"sha256": digest(path.read_bytes()), "items": len(items),
                                   "message_lengths": [len(item["message"]) for item in items],
                                   "timestamp_lengths": [len(item["timestamp"]) for item in items]}
                            for name, (path, items) in cases.items()}
    rows = []
    try:
        with (output / "rounds.jsonl").open("x") as raw:
            for round_index in range(args.rounds):
                order = [(name, stage) for name in cases for stage in range(len(STAGES))]
                rng.shuffle(order)
                for name, stage in order:
                    path, items = cases[name]
                    trace = output / "sample-trace.tmp"
                    stdout = command([executable, stage, path, args.iterations, args.warmup, trace, 0], env=env, cpu=cpu)
                    row = json.loads(stdout)
                    trace_bytes = trace.read_bytes() if trace.exists() else b""
                    verify(row, stage, items, args.iterations, trace_bytes)
                    if trace_bytes:
                        row.update(trace_sha256=digest(trace_bytes))
                        if metadata["retain_traces"]:
                            relative = f"traces/{name}-{round_index}-{STAGES[stage]}.i64le.gz"
                            (output / relative).write_bytes(gzip.compress(trace_bytes, mtime=0))
                            row.update(trace=relative)
                        trace.unlink()
                    row.update(fixture=name, stage=STAGES[stage], round=round_index,
                               ns_per_call=row["elapsed_ns"] / args.iterations)
                    rows.append(row)
                    raw.write(json.dumps(row, sort_keys=True) + "\n")
                    raw.flush()
        if snapshot(goose, compiler_root) != before or dependency_snapshot(cache) != dependency or digest(executable.read_bytes()) != binary_hash:
            raise SystemExit("measured source/compiler/dependency/executable changed during measurement")
        metadata["validation"] = "passed"
    finally:
        save_metadata()
    summary = {}
    for name in cases:
        summary[name] = {}
        for stage in STAGES:
            values = [row["ns_per_call"] for row in rows if row["fixture"] == name and row["stage"] == stage]
            summary[name][stage] = {"median_ns_per_call": statistics.median(values),
                                    "min_ns_per_call": min(values), "max_ns_per_call": max(values)}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"validated {len(rows)} stage samples; raw rounds, runtime fixtures and provenance: {output}")


if __name__ == "__main__":
    main()
