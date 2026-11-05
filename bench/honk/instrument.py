#!/usr/bin/env python3
"""Separate whole-process heap and path-filtered delayed-write experiments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

import run as profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--honk-source", type=Path, required=True)
    parser.add_argument("--goose", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--heaptrack-preload", type=Path, default=Path("/usr/lib/heaptrack/libheaptrack_preload.so"))
    parser.add_argument("--heaptrack-interpret", type=Path, default=Path("/usr/lib/heaptrack/libexec/heaptrack_interpret"))
    args = parser.parse_args()
    reference = json.loads(args.profile.read_text())
    reference_hash = profile.digest(args.profile)
    source, goose = args.honk_source.resolve(), args.goose.resolve()
    binary = source / ".build/honk"
    require = profile.require
    require(profile.git(source, "rev-parse", "HEAD") == reference["honk_revision"], "source mismatch")
    require(profile.digest(binary) == reference["honk_sha256"]
            and profile.digest(goose) == reference["goose_sha256"], "executable mismatch")
    require(profile.digest(Path(profile.__file__)) == reference["harness_sha256"], "profile harness mismatch")
    require(not profile.git(source, "status", "--porcelain")
            and not profile.git(profile.ROOT, "status", "--porcelain"), "clean sources required")
    frozen = (profile.git(profile.ROOT, "rev-parse", "HEAD"), profile.digest(Path(__file__)))
    os.sched_setaffinity(0, {reference["cpu"]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    require(not args.output.exists(), "output already exists")
    tools = (profile.digest(args.heaptrack_preload), profile.digest(args.heaptrack_interpret))
    rows = []
    with tempfile.TemporaryDirectory(prefix="honk-instrument-", dir=args.output.parent) as directory:
        work = Path(directory).resolve()
        (work / "src").mkdir()
        manifest = b'[package]\nname="profile_fixture"\nversion="0.1.0"\nkind="bin"\nentry="src/main.goose"\n'
        main_source = b'fn main() { print("fixture"); }\n'
        (work / "Honk.toml").write_bytes(manifest)
        (work / "src/main.goose").write_bytes(main_source)
        require(hashlib.sha256(manifest).hexdigest() == reference["manifest_sha256"]
                and hashlib.sha256(main_source).hexdigest() == reference["main_source_sha256"], "fixture mismatch")
        env = {"PATH": "/usr/bin:/bin", "HOME": str(work), "HONK_HOME": str(work / "cache"),
               "GOOSE": str(goose), "LANG": "C", "LC_ALL": "C"}
        base = [str(binary), "metadata"]
        baseline = subprocess.run(base, cwd=work, env=env, capture_output=True, timeout=30)
        require(baseline.returncode == 0 and baseline.stderr == b"", "baseline failed")
        for index in range(3):
            for mode, enabled in (("heap", False), ("heap", True), ("trace", False),
                                  ("trace", True), ("delayed", False), ("delayed", True),
                                  ("late_failure", True)):
                require((work / "Honk.toml").read_bytes() == manifest
                        and (work / "src/main.goose").read_bytes() == main_source, "fixture changed")
                log, trace = work / "events.log", work / "tool.log"
                log.write_bytes(profile.PREFIX)
                log.chmod(0o600)
                identity = profile.file_state(log)[:2]
                child_env = dict(env)
                if mode == "heap":
                    wrapper = []
                    child_env.update(LD_PRELOAD=str(args.heaptrack_preload.resolve()), DUMP_HEAPTRACK_OUTPUT=str(trace))
                else:
                    wrapper = ["strace", "-qq", "-P", str(log), "-e", "trace=write", "-o", str(trace)]
                    if mode == "delayed":
                        wrapper += ["-e", "inject=write:delay_enter=1ms"]
                    if mode == "late_failure":
                        wrapper += ["-e", "inject=write:error=ENOSPC:when=2"]
                command = wrapper + base + (["--log-file", "events.log"] if enabled else [])
                start = time.perf_counter_ns()
                result = subprocess.run(command, cwd=work, env=child_env, capture_output=True, timeout=120)
                elapsed = time.perf_counter_ns() - start
                expected = (1, baseline.stdout, profile.FAILURE) if mode == "late_failure" else (0, baseline.stdout, b"")
                require((result.returncode, result.stdout, result.stderr) == expected,
                        "instrumented command failed or changed output")
                require(profile.file_state(log)[:2] == identity, "file identity changed")
                data = profile.read_log(log)[1]
                if mode == "late_failure":
                    require(data == profile.PREFIX + b"[INFO] started duration_ns=0 outcome=0\n", "late failure changed committed prefix")
                elif enabled:
                    profile.check_events(data, 1)
                else:
                    require(data == profile.PREFIX, "disabled path wrote log")
                if mode == "heap":
                    interpreted = work / "interpreted"
                    with trace.open("rb") as raw, interpreted.open("wb") as output:
                        subprocess.run([str(args.heaptrack_interpret.resolve())], stdin=raw, stdout=output, stderr=subprocess.PIPE, check=True, timeout=60, env=env)
                    text = subprocess.check_output(["heaptrack_print", "-f", str(interpreted), "-p", "0", "-a", "0", "-T", "0"], text=True, env=env, timeout=60)
                    interpreted.unlink()
                else:
                    text = trace.read_text()
                row = dict(index=index, mode=mode, enabled=enabled, elapsed_ns=elapsed)
                if mode == "heap":
                    match = re.search(r"calls to allocation functions: (\d+)", text)
                    temporary = re.search(r"temporary memory allocations: (\d+)", text)
                    peak = re.search(r"peak heap memory consumption: ([^\n]+)", text)
                    require(match is not None and temporary is not None and peak is not None, "invalid heap tool output")
                    row.update(allocation_calls=int(match[1]), temporary_allocations=int(temporary[1]),
                               peak_heap_display=peak[1], summary_excerpts=[match[0], temporary[0], peak[0]])
                else:
                    lines = text.splitlines()
                    require(len(lines) == (2 if enabled else 0)
                            and all(line.startswith("write(") for line in lines), "unexpected traced writes")
                    delayed = text.count("(DELAYED)")
                    require(delayed == (2 if mode == "delayed" and enabled else 0), "wrong delayed write count")
                    row.update(trace=lines, delayed_writes=delayed)
                    if mode == "late_failure":
                        require(text.count("ENOSPC") == 1 and text.count("(INJECTED)") == 1, "wrong late failure injection")
                        row["failure_after_started"] = "passed"
                rows.append(row)
                log.unlink()
                trace.unlink()
        require((work / "Honk.toml").read_bytes() == manifest
                and (work / "src/main.goose").read_bytes() == main_source, "fixture changed")
    require(frozen == (profile.git(profile.ROOT, "rev-parse", "HEAD"), profile.digest(Path(__file__))), "instrument changed")
    require(not profile.git(source, "status", "--porcelain")
            and not profile.git(profile.ROOT, "status", "--porcelain"), "source changed")
    require(profile.git(source, "rev-parse", "HEAD") == reference["honk_revision"]
            and profile.digest(binary) == reference["honk_sha256"]
            and profile.digest(goose) == reference["goose_sha256"]
            and profile.digest(Path(profile.__file__)) == reference["harness_sha256"], "inputs changed")
    require(tools == (profile.digest(args.heaptrack_preload), profile.digest(args.heaptrack_interpret)), "instrument tools changed")
    require(reference_hash == profile.digest(args.profile), "reference profile changed")
    report = dict(instrument_revision=frozen[0], instrument_sha256=frozen[1],
                  reference_profile_sha256=reference_hash, honk_sha256=reference["honk_sha256"],
                  heaptrack_tool_sha256=tools,
                  heaptrack_version=subprocess.check_output(["heaptrack", "--version"], text=True).strip(),
                  strace_version=subprocess.check_output(["strace", "--version"], text=True).splitlines()[0],
                  samples=rows)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print("validated", len(rows), "separate instrumented samples")


if __name__ == "__main__":
    main()
