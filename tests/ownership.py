#!/usr/bin/env python3
"""The pinned compiler must reject input/output aliasing and sink mutation."""
from pathlib import Path
import subprocess
import sys
import tempfile

compiler = Path(sys.argv[1]).resolve()
root = Path(__file__).resolve().parent.parent
cases = {
    "optional-sink-result": '''
    fn bad_sink(line: const u8[:]) -> bool? { null }
    var scratch: u8[>..] = [];
    log::emit(config, log::Level.Info, "message", scratch, bad_sink);
    ''',
    "message-limit-mutation": '''
    fn change(value: i64&) { value = 100000; }
    change(log::MAX_MESSAGE_BYTES);
    ''',
    "line-limit-mutation": '''
    fn change(value: i64&) { value = 1; }
    change(log::MAX_LINE_BYTES);
    ''',
    "input-alias": '''
    var scratch = str("input");
    let message: const u8[:] = scratch;
    log::render(config, log::Level.Info, message, scratch);
    ''',
    "emit-alias": '''
    var scratch = str("input");
    let message: const u8[:] = scratch;
    log::emit(config, log::Level.Info, message, scratch) { line => true };
    ''',
    "sink-mutation": '''
    var scratch: u8[>..] = [];
    log::emit(config, log::Level.Info, "message", scratch) { line =>
        line[0] = 'X';
        true
    };
    ''',
    "sink-alias": '''
    var scratch: u8[>..] = [];
    log::emit(config, log::Level.Info, "message", scratch) { line =>
        scratch.clear();
        print(line);
        true
    };
    ''',
}
control = '''
    var scratch: u8[>..] = [];
    log::render(config, log::Level.Info, "message", scratch);
    let status = log::emit(config, log::Level.Info, "message", scratch) { line =>
        assert(line == "[INFO] message\\n");
        true
    };
    assert(status == log::Status.Written);
'''
expected_errors = {
    "optional-sink-result": ("bool", "bool?"),
    "message-limit-mutation": ("cannot write through this reference", "non-writable provenance"),
    "line-limit-mutation": ("cannot write through this reference", "non-writable provenance"),
    "input-alias": ("cannot clear", "reference or slice"),
    "emit-alias": ("cannot clear", "reference or slice"),
    "sink-mutation": ("cannot assign through this path", "read-only"),
    "sink-alias": ("shrinks scratch while line is still used", "may refer into scratch"),
}
with tempfile.TemporaryDirectory(prefix="ownership-", dir=root / ".build") as tmp:
    for name, body in {"valid-control": control, **cases}.items():
        source = Path(tmp) / f"{name}.goose"
        source.write_text('import logger from "../..";\nimport std;\n'
                          'fn main() {\nlet config = log::Logger { .. };\n'
                          + body + '\n}\n')
        result = subprocess.run([str(compiler), "check", str(source)],
                                capture_output=True, text=True, timeout=30)
        diagnostics = result.stdout + result.stderr
        if name == "valid-control":
            if result.returncode != 0:
                raise SystemExit(f"positive control failed\n{diagnostics}")
            print("positive control: accepted")
            continue
        if result.returncode != 1 or "error:" not in diagnostics:
            raise SystemExit(f"{name}: expected compiler rejection, got "
                             f"{result.returncode}\n{diagnostics}")
        if not all(fragment in diagnostics for fragment in expected_errors[name]):
            raise SystemExit(f"{name}: rejected for an unexpected reason\n{diagnostics}")
        print(f"{name}: rejected")
