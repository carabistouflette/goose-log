#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the optional UTC adapter's alias and callback type constraints."""
from pathlib import Path
import subprocess
import sys
import tempfile

compiler = Path(sys.argv[1]).resolve()
root = Path(__file__).resolve().parents[1]
header = '''import std;
import logger from "../..";
import time from "carabistouflette/goose-time@343887caeee0a1f4e2e536ff322fcafb454e11bd";
import utc from "../../examples/utc";
fn main() {
    let config = log::Logger { .. };
    var timestamp: u8[>..] = [];
    var scratch: u8[>..] = [];
    fn good_clock() -> i64 { 0 }
    fn good_sink(line: const u8[:]) -> bool { line.len > 0 }
'''
cases = {
    "shared-buffers": ('''
        utc_log::emit(config, log::Level.Info, "event", scratch, scratch, good_clock, good_sink);
    ''', ("shrinks", "may refer", "cannot clear")),
    "message-borrows-timestamp": ('''
        timestamp.append("message");
        let message: const u8[:] = timestamp;
        utc_log::emit(config, log::Level.Info, message, timestamp, scratch, good_clock, good_sink);
    ''', ("shrinks", "may refer", "cannot clear")),
    "message-borrows-line": ('''
        scratch.append("message");
        let message: const u8[:] = scratch;
        utc_log::emit(config, log::Level.Info, message, timestamp, scratch, good_clock, good_sink);
    ''', ("shrinks", "may refer", "cannot clear")),
    "floating-clock": ('''
        fn wrong_clock() -> f64 { 0.0 }
        utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, wrong_clock, good_sink);
    ''', ("i64", "f64")),
    "boolean-clock": ('''
        fn wrong_clock() -> bool { true }
        utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, wrong_clock, good_sink);
    ''', ("i64", "bool")),
    "optional-clock": ('''
        fn wrong_clock() -> i64? { null }
        utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, wrong_clock, good_sink);
    ''', ("i64", "i64?")),
    "typed-timestamp-clock": ('''
        fn wrong_clock() -> time::Timestamp { time::Timestamp { .. } }
        utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, wrong_clock, good_sink);
    ''', ("i64", "Timestamp")),
    "optional-sink": ('''
        fn wrong_sink(line: const u8[:]) -> bool? { null }
        utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, good_clock, wrong_sink);
    ''', ("bool", "bool?")),
    "integer-sink": ('''
        fn wrong_sink(line: const u8[:]) -> i64 { 1 }
        utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, good_clock, wrong_sink);
    ''', ("bool", "i64")),
    "sink-mutation": ('''
        utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, good_clock) { line =>
            line[0] = 'X';
            true
        };
    ''', ("read-only", "cannot assign")),
    "sink-line-buffer-alias": ('''
        utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, good_clock) { line =>
            scratch.clear();
            assert(line.len > 0);
            true
        };
    ''', ("shrinks", "may refer", "cannot clear")),
}
control = '''
    let result = utc_log::emit(config, log::Level.Info, "event", timestamp, scratch, good_clock, good_sink);
    assert(result == log::Status.Written);
'''
(root / ".build").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="utc-ownership-", dir=root / ".build") as tmp:
    for name, (body, fragments) in {"valid-control": (control, ()), **cases}.items():
        source = Path(tmp) / f"{name}.goose"
        source.write_text(header + body + "\n}\n", encoding="utf-8")
        result = subprocess.run([str(compiler), "check", str(source)],
                                capture_output=True, text=True, timeout=60)
        diagnostics = result.stdout + result.stderr
        if name == "valid-control":
            if result.returncode:
                raise SystemExit(f"positive control failed\n{diagnostics}")
            print("UTC positive control: accepted")
            continue
        if result.returncode != 1 or "error:" not in diagnostics:
            raise SystemExit(f"{name}: expected compiler rejection, got {result.returncode}\n{diagnostics}")
        # Alias diagnostics vary with the path that first loses provenance.
        alias_case = name in {"shared-buffers", "message-borrows-timestamp", "message-borrows-line", "sink-line-buffer-alias"}
        correct_reason = any(fragment in diagnostics for fragment in fragments) if alias_case else all(fragment in diagnostics for fragment in fragments)
        if not correct_reason:
            raise SystemExit(f"{name}: rejected for an unexpected reason\n{diagnostics}")
        print(f"UTC {name}: rejected")
