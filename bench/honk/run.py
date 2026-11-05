#!/usr/bin/env python3
"""Paired whole-Honk metadata commands; trusted, separately built native binary."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import stat
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
PREFIX = b"prefix\n"
EVENT = re.compile(rb"\[INFO\] (started|returned) duration_ns=([0-9]+) outcome=0\n")
CAP = 16 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise SystemExit(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_state(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_uid == os.geteuid() and info.st_nlink == 1, "invalid private file")
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink, info.st_size, digest(path))


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def check_events(data, count):
    require(data.startswith(PREFIX), "log prefix changed")
    payload = data[len(PREFIX):]
    rows = list(EVENT.finditer(payload))
    require(b"".join(row.group() for row in rows) == payload, "invalid diagnostic bytes")
    require(len(rows) == 2 * count, "wrong event count")
    for index, row in enumerate(rows):
        require(row[1] == (b"started" if index % 2 == 0 else b"returned"), "event order changed")
        duration = int(row[2])
        require(duration <= 2**64 - 1 and (index % 2 == 1 or duration == 0), "invalid duration")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--honk-source", type=Path, required=True)
    parser.add_argument("--honk-revision", required=True)
    parser.add_argument("--goose", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--rounds", type=int, default=9)
    parser.add_argument("--calls", type=int, default=32)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(platform.system() == "Linux", "Linux file policy and affinity required")
    require(re.fullmatch(r"[0-9a-f]{40}", args.honk_revision), "full Honk revision required")
    require(1 <= args.rounds <= 25 and 1 <= args.calls <= 128, "rounds 1..25; calls 1..128")
    require(args.cpu in os.sched_getaffinity(0), "CPU unavailable")
    source = args.honk_source.resolve()
    binary = source / ".build/honk"
    goose = args.goose.resolve()
    require(git(source, "rev-parse", "HEAD") == args.honk_revision, "Honk revision mismatch")
    require(not git(source, "status", "--porcelain"), "Honk source must be clean")
    require(not git(ROOT, "status", "--porcelain"), "profile source must be committed and clean")
    harness = (git(ROOT, "rev-parse", "HEAD"), digest(Path(__file__)))
    before = (digest(binary), digest(goose), git(source, "rev-parse", "HEAD^{tree}"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    require(not args.output.exists(), "output already exists")
    os.sched_setaffinity(0, {args.cpu})
    samples = []
    with tempfile.TemporaryDirectory(prefix="honk-profile-", dir=args.output.parent) as temporary:
        work = Path(temporary).resolve()
        (work / "src").mkdir()
        manifest = b'[package]\nname="profile_fixture"\nversion="0.1.0"\nkind="bin"\nentry="src/main.goose"\n'
        (work / "Honk.toml").write_bytes(manifest)
        main_source = b'fn main() { print("fixture"); }\n'
        (work / "src/main.goose").write_bytes(main_source)

        def check_fixture():
            require((work / "Honk.toml").read_bytes() == manifest
                    and (work / "src/main.goose").read_bytes() == main_source, "fixture changed")
        env = {"PATH": "/usr/bin:/bin", "HOME": str(work), "HONK_HOME": str(work / "cache"),
               "GOOSE": str(goose), "LANG": "C", "LC_ALL": "C", "HONK_SECRET": "private-marker"}

        def invoke(enabled):
            return subprocess.run([str(binary), "metadata", *(["--log-file", "events.log"] if enabled else [])],
                                  cwd=work, env=env, capture_output=True, timeout=30)

        baseline = invoke(False)
        require(baseline.returncode == 0 and baseline.stderr == b"", "baseline metadata failed")
        require(json.loads(baseline.stdout)["name"] == "profile_fixture", "wrong metadata fixture")
        log = work / "events.log"
        require(not log.exists(), "disabled command created a log")
        # Warm both paths once; setup and validation are outside batch timing.
        warm = invoke(True)
        require((warm.returncode, warm.stdout, warm.stderr) == (0, baseline.stdout, b""), "warmup changed output")
        check_events(PREFIX + log.read_bytes(), 1)
        file_state(log)
        log.unlink()
        order = random.Random(0x6005E)
        for round_index in range(args.rounds):
            stages = [False, True]
            order.shuffle(stages)
            for enabled in stages:
                check_fixture()
                log.write_bytes(PREFIX)
                log.chmod(0o600)
                identity = file_state(log)[:2]
                start = time.perf_counter_ns()
                results = [invoke(enabled) for _ in range(args.calls)]
                elapsed = time.perf_counter_ns() - start
                check_fixture()
                require(all((r.returncode, r.stdout, r.stderr) == (0, baseline.stdout, b"") for r in results),
                        "command status/stdout/stderr changed")
                require(file_state(log)[:2] == identity, "file identity changed")
                data = log.read_bytes()
                if enabled:
                    check_events(data, args.calls)
                else:
                    require(data == PREFIX, "disabled command touched log bytes")
                samples.append(dict(round=round_index, enabled=enabled, calls=args.calls,
                                    elapsed_ns=elapsed, ns_per_command=elapsed / args.calls,
                                    file_bytes=len(data), file_sha256=hashlib.sha256(data).hexdigest()))
                log.unlink()
        # Failures are acceptance checks, not latency measurements or a slow-disk model.
        log.write_bytes(PREFIX)
        log.chmod(0o600)
        busy_state = file_state(log)
        with log.open("r+b") as locked:
            fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
            failed = invoke(True)
        require((failed.returncode, failed.stdout, failed.stderr) == (1, b"", b"diagnostic log failed\n"),
                "busy sink failure policy changed")
        require(log.read_bytes() == PREFIX, "busy sink modified file")
        require(file_state(log) == busy_state, "busy sink changed file identity or bytes")
        with log.open("r+b") as full:
            full.truncate(CAP)
        full_state = file_state(log)
        failed = invoke(True)
        require((failed.returncode, failed.stdout, failed.stderr) == (1, b"", b"diagnostic log failed\n"),
                "full sink failure policy changed")
        require(log.stat().st_size == CAP, "full sink grew")
        require(file_state(log) == full_state, "full sink changed file identity or bytes")
        check_fixture()
        filesystem = subprocess.check_output(["stat", "-f", "-c", "%T", str(work)], text=True).strip()
    require(before == (digest(binary), digest(goose), git(source, "rev-parse", "HEAD^{tree}")), "inputs changed")
    require(git(source, "rev-parse", "HEAD") == args.honk_revision, "Honk HEAD changed")
    require(harness == (git(ROOT, "rev-parse", "HEAD"), digest(Path(__file__))), "harness changed")
    require(not git(source, "status", "--porcelain") and not git(ROOT, "status", "--porcelain"), "source changed")
    report = dict(schema=1, measured_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  harness_revision=harness[0], harness_sha256=harness[1], honk_revision=args.honk_revision,
                  honk_tree=before[2], honk_sha256=before[0], goose_sha256=before[1],
                  goose_version=subprocess.check_output([str(goose), "version"], text=True).strip(),
                  platform=platform.platform(), architecture=platform.machine(), python=platform.python_version(),
                  libc=platform.libc_ver(),
                  cpu=args.cpu, page_size=os.sysconf("SC_PAGE_SIZE"), filesystem=filesystem,
                  manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                  main_source_sha256=hashlib.sha256(main_source).hexdigest(),
                  stdout_sha256=hashlib.sha256(baseline.stdout).hexdigest(),
                  validation={"busy_lock": "passed", "full_file": "passed"}, samples=samples,
                  summaries={str(enabled): dict(median_ns=statistics.median(s["ns_per_command"] for s in samples if s["enabled"] == enabled),
                                               min_ns=min(s["ns_per_command"] for s in samples if s["enabled"] == enabled),
                                               max_ns=max(s["ns_per_command"] for s in samples if s["enabled"] == enabled))
                             for enabled in (False, True)})
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print("validated", len(samples), "batches; output written")


if __name__ == "__main__":
    main()
