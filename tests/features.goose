// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import std;
var default_level: log::Level;

fn main() {
    assert(default_level == log::Level.Debug);
    let levels = [log::Level.Trace, log::Level.Debug, log::Level.Info, log::Level.Warn,
        log::Level.Error, log::Level.Fatal, log::Level.Off];
    let names = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "OFF"];
    let mixed = ["tRaCe", "debug", "Info", "wArN", "error", "Fatal", "off"];
    for level, i in levels {
        assert(log::level_name(level) == names[i]);
        let parsed, ok = log::parse_level(names[i]);
        assert(ok && parsed == level);
        let alternate, alternate_ok = log::parse_level(mixed[i]);
        assert(alternate_ok && alternate == level);
    }
    let invalid = ["", " INFO", "INFO ", "warning", "critical", "ERR", "\x00INFO", "inf\xff"];
    for text in invalid {
        let parsed, ok = log::parse_level(text);
        assert(!ok && parsed == log::Level.Off);
    }
    var huge: u8[>..] = [];
    for i in 100000 { huge.push('a'); }
    let unknown, unknown_ok = log::parse_level(huge);
    assert(!unknown_ok && unknown == log::Level.Off);

    let config = log::Logger { .. };
    var scratch = str("sentinel");
    var builds = 0;
    var calls = 0;
    fn build_message() -> u8[>..] {
        builds += 1;
        str("value=", 42)
    }
    let filtered = log::emit_lazy(config, log::Level.Debug, scratch, build_message) { line =>
        calls += 1;
        true
    };
    assert(filtered == log::Status.Filtered && builds == 0 && calls == 0 && scratch == "sentinel");
    let accepted = log::emit_lazy(config, log::Level.Info, scratch, build_message) { line =>
        calls += 1;
        assert(line == "[INFO] value=42\n");
        true
    };
    assert(accepted == log::Status.Written && builds == 1 && calls == 1);
    let failed = log::emit_lazy(config, log::Level.Fatal, scratch, build_message) { line =>
        calls += 1;
        assert(line == "[FATAL] value=42\n");
        false
    };
    assert(failed == log::Status.SinkError && builds == 2 && calls == 2);
    assert(scratch == "[FATAL] value=42\n");
    // Fatal is a severity; execution continues. Borrowed builder results work.
    fn borrowed() -> const u8[:] { "borrowed" }
    let borrowed_status = log::emit_lazy(config, log::Level.Warn, scratch, borrowed) { line =>
        assert(line == "[WARN] borrowed\n");
        true
    };
    assert(borrowed_status == log::Status.Written);
    let empty_record = log::Record { .. };
    assert(log::render_record(config, empty_record, scratch));
    assert(scratch == "[INFO] \n");
    let fields = [log::Field { key: "user\"", value: "a\\b\n" },
        log::Field { key: "password", value: "do-not-output", sensitive: true }];
    let record = log::Record { level: log::Level.Info, message: "done\n",
        timestamp: "2026-11-04Z", target: "net\"", file: "app.goose", line: 42, fields: fields };
    let record_status = log::emit_record(config, record, scratch) { line =>
        assert(line == "[INFO] timestamp=\"2026-11-04Z\" target=\"net\\\"\" file=\"app.goose\" line=42 \"user\\\"\"=\"a\\\\b\\x0a\" \"password\"=\"***\" done\\x0a\n");
        false
    };
    assert(record_status == log::Status.SinkError);
    let disabled = log::Logger { minimum: log::Level.Off };
    let before = str(scratch);
    var record_calls = 0;
    let record_filtered = log::emit_record(disabled, record, scratch) { line => record_calls += 1; true };
    assert(record_filtered == log::Status.Filtered && record_calls == 0 && scratch == before);
    huge.clear();
    for i in 4097 { huge.push(0xff); }
    let maximum_fields = [log::Field { key: huge, value: huge }; 9];
    let maximum = log::Record { level: log::Level.Trace, message: huge,
        timestamp: huge, target: huge, file: huge, line: 4294967295, fields: maximum_fields };
    let trace = log::Logger { minimum: log::Level.Trace, color: true };
    assert(log::render_record(trace, maximum, scratch));
    assert(scratch.len == log::MAX_RECORD_LINE_BYTES && scratch.len == 28592);
    assert(scratch[scratch.len - 16..] == "... [truncated]\n");
    print("feature tests passed");
}
