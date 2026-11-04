#!/usr/bin/env python3
"""Exercise the real setup script against local Git and a recorded build tool."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def require(condition, message):
    # Unlike an assert statement, this remains active under python -O.
    if not condition:
        raise AssertionError(message)


def git(directory, *args):
    return subprocess.run(
        ["git", "-C", str(directory), *args], check=True,
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()


def main():
    with tempfile.TemporaryDirectory(prefix="setup-", dir=ROOT / ".build") as tmp:
        base = Path(tmp)
        origin = base / "origin"
        origin.mkdir()
        git(origin, "init", "-b", "main")
        (origin / "compiler.txt").write_text("pinned source\n")
        (origin / ".gitignore").write_text("build/\n")
        git(origin, "add", ".")
        git(origin, "-c", "user.name=Setup Test", "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-m", "test fixture")
        pin = git(origin, "rev-parse", "HEAD")
        (origin / "compiler.txt").write_text("newer source\n")
        git(origin, "add", "compiler.txt")
        git(origin, "-c", "user.name=Setup Test", "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-m", "newer fixture")
        tip = git(origin, "rev-parse", "HEAD")
        for case in ("clean", "modified", "staged", "untracked", "invalid-pin",
                     "assume-unchanged", "skip-worktree"):
            project = base / case
            scripts = project / "scripts"
            scripts.mkdir(parents=True)
            installer = scripts / "setup-goose.sh"
            shutil.copy2(ROOT / "scripts/setup-goose.sh", installer)
            (project / "GOOSE_REVISION").write_text(pin + "\n")
            toolchain = project / ".toolchain/goose"
            toolchain.parent.mkdir()
            git(project, "clone", str(origin), str(toolchain))
            require(git(toolchain, "rev-parse", "HEAD") == tip,
                    f"{case}: clone did not start at the newer commit")
            if case not in ("clean", "invalid-pin"):
                # Dirty-cache cases must reproduce edits surviving a checkout
                # of the same pin, rather than an unrelated checkout conflict.
                git(toolchain, "checkout", "--detach", pin)
            before_head = git(toolchain, "rev-parse", "HEAD")
            # Ignored build artifacts must not make an otherwise clean cache fail.
            (toolchain / "build").mkdir()
            (toolchain / "build/cache").write_text("existing build output\n")
            source = toolchain / "compiler.txt"
            if case in ("modified", "staged"):
                source.write_text("local compiler patch\n")
                if case == "staged":
                    git(toolchain, "add", "compiler.txt")
            if case == "untracked":
                (toolchain / "extra.h").write_text("local source\n")
            if case == "invalid-pin":
                (project / "GOOSE_REVISION").write_text("main\n")
            if case in ("assume-unchanged", "skip-worktree"):
                git(toolchain, "update-index", "--" + case, "compiler.txt")
                source.write_text("hidden local compiler patch\n")
                require(not git(toolchain, "status", "--porcelain"),
                        f"{case}: fixture did not hide changes")
            before = source.read_bytes()
            marker = project / "build-calls"
            tools = project / "tools"
            tools.mkdir()
            cmake = tools / "cmake"
            cmake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$SETUP_MARKER"\n')
            cmake.chmod(0o700)
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
                       SETUP_MARKER=str(marker))
            result = subprocess.run([str(installer)], cwd=project, env=env,
                                    capture_output=True, text=True, timeout=30)
            if case == "clean":
                require(result.returncode == 0, result.stderr)
                require(git(toolchain, "rev-parse", "HEAD") == pin,
                        "clean: failed to check out the older requested pin")
                require(source.read_text() == "pinned source\n", "clean: built wrong source")
                calls = marker.read_text().splitlines()
                require(len(calls) == 2 and calls[0].startswith("-S "),
                        "clean: configure not invoked exactly once")
                require(calls[1].startswith("--build "), "clean: build not invoked")
            else:
                require(source.read_bytes() == before, f"{case}: source was discarded")
                require(git(toolchain, "rev-parse", "HEAD") == before_head,
                        f"{case}: moved HEAD before refusing unsafe input")
                expected = "Compiler source is modified"
                if case == "invalid-pin":
                    expected = "GOOSE_REVISION must contain"
                if case in ("assume-unchanged", "skip-worktree"):
                    expected = "Compiler index hides source checks"
                require(result.returncode == 1 and expected in result.stderr,
                        f"{case}: unexpected exit {result.returncode}\n{result.stderr}")
                require(not marker.exists(), f"{case}: reached CMake on unsafe source")
                if case == "untracked":
                    require((toolchain / "extra.h").read_text() == "local source\n",
                            "untracked: source was discarded")
            print(f"setup {case}: passed")


if __name__ == "__main__":
    main()
