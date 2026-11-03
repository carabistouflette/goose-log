#!/usr/bin/env python3
"""Verify capped/filtered reads with real page protection and a fault control."""
from pathlib import Path
import resource
import signal
import subprocess
import sys

# The expected fault must not create core files for the large reserved stacks.
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
for argument in sys.argv[1:]:
    driver = str(Path(argument).resolve())
    result = subprocess.run([driver, "fault-control"], capture_output=True,
                            text=True, timeout=30)
    # Goose may translate a fault inside its reserved region into a specific
    # runtime diagnostic rather than let the OS terminate with the raw signal.
    faulted = (result.returncode in (-signal.SIGSEGV, -signal.SIGBUS)
               or (result.returncode == 1
                   and "goose runtime error: data stack overflow:" in result.stderr))
    if (not faulted
            or "guard-page fault control\n" not in result.stderr):
        raise SystemExit(f"{argument}: guard did not fault as expected "
                         f"(exit {result.returncode})\n{result.stdout}{result.stderr}")
    result = subprocess.run([driver], capture_output=True, text=True, timeout=30)
    if (result.returncode != 0 or result.stdout != "guarded input tests passed\n"
            or result.stderr):
        raise SystemExit(f"{argument}: guarded reads failed "
                         f"(exit {result.returncode})\n{result.stdout}{result.stderr}")
    print(f"{argument}: fault control and guarded reads passed")
if len(sys.argv) < 2:
    raise SystemExit("usage: guarded.py DRIVER [DRIVER ...]")
