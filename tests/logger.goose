// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import std;

fn main() {
    let levels = [log::Level.Debug, log::Level.Info, log::Level.Warn, log::Level.Error, log::Level.Off];
    let labels = ["[DEBUG] ", "[INFO] ", "[WARN] ", "[ERROR] "];
    let colors = ["\x1b[36m", "\x1b[32m", "\x1b[33m", "\x1b[31m"];
    var scratch: u8[>..] = [];
    for minimum, mi in levels {
        let config = log::Logger { minimum: minimum };
        for level, li in levels {
            let expected = li < 4 && li >= mi;
            assert(log::enabled(config, level) == expected);
            scratch.clear(); scratch.append("sentinel");
            let rendered = log::render(config, level, "message", scratch);
            assert(rendered == expected);
            if expected { assert(scratch == str(labels[li], "message\n")); }
            else { assert(scratch == "sentinel"); }
            var calls = 0;
            let status = log::emit(config, level, "message", scratch) { line =>
                calls += 1;
                assert(line == str(labels[li], "message\n"));
                true
            };
            assert(calls == (if expected { 1 } else { 0 }));
            assert(status == (if expected { log::Status.Written } else { log::Status.Filtered }));
            if !expected { assert(scratch == "sentinel"); }
        }
    }
    let config = log::Logger { .. };
    assert(!log::enabled(config, log::Level.Debug));
    assert(log::render(config, log::Level.Info, "", scratch));
    assert(scratch == "[INFO] \n");
    assert(log::render(config, log::Level.Warn, "A\r\n\t\x00\x1b\\\x7f\xff😀", scratch));
    assert(scratch == "[WARN] A\\x0d\\x0a\\x09\\x00\\x1b\\\\\\x7f\\xff\\xf0\\x9f\\x98\\x80\n");
    for i in 4 {
        let colored = log::Logger { minimum: log::Level.Debug, color: true };
        assert(log::render(colored, levels[i], "\x1b[31m\n", scratch));
        let label = labels[i];
        assert(scratch == str(colors[i], label[..label.len - 1], "\x1b[0m \\x1b[31m\\x0a\n"));
    }
    var input: u8[>..] = [];
    for i in 4095 { input.push('a'); }
    assert(log::render(config, log::Level.Info, input, scratch));
    assert(scratch == str("[INFO] ", input, "\n"));
    input.push('b');
    assert(log::render(config, log::Level.Info, input, scratch));
    assert(scratch == str("[INFO] ", input, "\n"));
    input.push('c');
    assert(log::render(config, log::Level.Info, input, scratch));
    assert(scratch == str("[INFO] ", input[..4096], "... [truncated]\n"));
    input.clear();
    for i in 100000 { input.push(0xff); }
    let colored = log::Logger { minimum: log::Level.Debug, color: true };
    assert(log::render(colored, log::Level.Debug, input, scratch));
    assert(scratch.len == log::MAX_LINE_BYTES);
    var worst = str("\x1b[36m[DEBUG]\x1b[0m ");
    for i in 4096 { worst.append("\\xff"); }
    worst.append("... [truncated]\n");
    assert(scratch == worst);
    assert(log::render(config, log::Level.Error, "short", scratch));
    assert(scratch == "[ERROR] short\n");
    var calls = 0;
    var saved: u8[>..] = [];
    let failure = log::emit(config, log::Level.Error, "failed", scratch) { line =>
        calls += 1;
        saved.append(line);
        false
    };
    assert(failure == log::Status.SinkError && calls == 1);
    assert(saved == "[ERROR] failed\n" && scratch == saved);
    // A retained copy survives reuse; the sink only receives a borrowed view.
    assert(log::render(config, log::Level.Info, "next", scratch));
    assert(saved == "[ERROR] failed\n" && scratch == "[INFO] next\n");
    // Nested sinks use independent storage and report status independently.
    var nested: u8[>..] = [];
    var outer_calls = 0;
    var inner_calls = 0;
    let outer_status = log::emit(config, log::Level.Info, "outer", scratch) { outer_line =>
        outer_calls += 1;
        assert(outer_line == "[INFO] outer\n");
        let inner_status = log::emit(config, log::Level.Error, "inner", nested) { inner_line =>
            inner_calls += 1;
            assert(inner_line == "[ERROR] inner\n");
            assert(outer_line == "[INFO] outer\n");
            false
        };
        assert(inner_status == log::Status.SinkError);
        assert(outer_line == "[INFO] outer\n");
        true
    };
    assert(outer_status == log::Status.Written && outer_calls == 1 && inner_calls == 1);
    assert(scratch == "[INFO] outer\n" && nested == "[ERROR] inner\n");
    var every_byte: u8[>..] = [];
    for i in 256 { every_byte.push(i as u8); }
    assert(log::render(config, log::Level.Info, every_byte, scratch));
    assert(scratch == "[INFO] \\x00\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\x09\\x0a\\x0b\\x0c\\x0d\\x0e\\x0f\\x10\\x11\\x12\\x13\\x14\\x15\\x16\\x17\\x18\\x19\\x1a\\x1b\\x1c\\x1d\\x1e\\x1f !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\\\]^_`abcdefghijklmnopqrstuvwxyz{|}~\\x7f\\x80\\x81\\x82\\x83\\x84\\x85\\x86\\x87\\x88\\x89\\x8a\\x8b\\x8c\\x8d\\x8e\\x8f\\x90\\x91\\x92\\x93\\x94\\x95\\x96\\x97\\x98\\x99\\x9a\\x9b\\x9c\\x9d\\x9e\\x9f\\xa0\\xa1\\xa2\\xa3\\xa4\\xa5\\xa6\\xa7\\xa8\\xa9\\xaa\\xab\\xac\\xad\\xae\\xaf\\xb0\\xb1\\xb2\\xb3\\xb4\\xb5\\xb6\\xb7\\xb8\\xb9\\xba\\xbb\\xbc\\xbd\\xbe\\xbf\\xc0\\xc1\\xc2\\xc3\\xc4\\xc5\\xc6\\xc7\\xc8\\xc9\\xca\\xcb\\xcc\\xcd\\xce\\xcf\\xd0\\xd1\\xd2\\xd3\\xd4\\xd5\\xd6\\xd7\\xd8\\xd9\\xda\\xdb\\xdc\\xdd\\xde\\xdf\\xe0\\xe1\\xe2\\xe3\\xe4\\xe5\\xe6\\xe7\\xe8\\xe9\\xea\\xeb\\xec\\xed\\xee\\xef\\xf0\\xf1\\xf2\\xf3\\xf4\\xf5\\xf6\\xf7\\xf8\\xf9\\xfa\\xfb\\xfc\\xfd\\xfe\\xff\n");
    for c, i in scratch {
        assert((c >= 0x20 && c <= 0x7e) || (c == '\n' && i == scratch.len - 1));
    }
    print("logger tests passed");
}
