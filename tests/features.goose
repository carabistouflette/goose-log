// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import std;

fn main() {
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
    print("feature tests passed");
}
