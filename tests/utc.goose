// SPDX-License-Identifier: Apache-2.0
import std;
import logger from "..";
import time from "carabistouflette/goose-time@343887caeee0a1f4e2e536ff322fcafb454e11bd";
import utc from "../examples/utc";

// Consumer numeric/text formatting hooks must not influence UTC output.
fn format(out: u8[>..]&, value: i64) { out.append("hostile integer"); }
fn format(out: u8[>..]&, value: const u8[:]) { out.append("hostile text"); }

fn filtering_and_levels() {
    // Severity order is explicit, independent of the core enum representation.
    let levels = [log::Level.Trace, log::Level.Debug, log::Level.Info,
                  log::Level.Warn, log::Level.Error, log::Level.Fatal, log::Level.Off];
    let names = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "OFF"];
    let colors = ["\x1b[94m", "\x1b[36m", "\x1b[32m", "\x1b[33m", "\x1b[31m", "\x1b[35m", ""];
    for color in [false, true] {
        for minimum, mi in levels {
            for level, li in levels {
                let config = log::Logger { minimum, color };
                var timestamp: u8[>..] = []; timestamp.append("old timestamp\0\xff");
                var scratch:   u8[>..] = []; scratch.append("old line\0\xff");
                var clocks = 0;
                var sinks = 0;
                let enabled = mi < 6 && li < 6 && li >= mi;
                let successful = (mi + li) % 2 == 0;
                var expected: u8[>..] = [];
                if color { expected.append(colors[li]); }
                expected.push('['); expected.append(names[li]); expected.push(']');
                if color { expected.append("\x1b[0m"); }
                expected.append(" timestamp=\"1970-01-01T00:00:00Z\" event\n");
                fn clock() -> i64 {
                    clocks++;
                    // Acquisition precedes replacement of either caller buffer.
                    assert(timestamp == "old timestamp\0\xff" && scratch == "old line\0\xff");
                    0
                }
                fn sink(line: const u8[:]) -> bool {
                    sinks++;
                    assert(line == expected);
                    successful
                }
                let result = utc_log::emit(config, level, "event", timestamp, scratch, clock, sink);
                if !enabled {
                    assert(result == log::Status.Filtered && clocks == 0 && sinks == 0);
                    assert(timestamp == "old timestamp\0\xff" && scratch == "old line\0\xff");
                } else {
                    assert(clocks == 1 && sinks == 1);
                    assert(result == (if successful { log::Status.Written } else { log::Status.SinkError }));
                    assert(timestamp == "1970-01-01T00:00:00Z" && scratch == expected);
                    assert(scratch.len <= log::MAX_RECORD_LINE_BYTES);
                }
            }
        }
    }
}
struct Fixture { sample: i64, expected: const u8[:] }
fn timestamps_and_reuse() {
    let fixtures = [
        Fixture { -9223372036854775808, "1677-09-21T00:12:43.145224192Z" },
        Fixture { 9223372036854775807, "2262-04-11T23:47:16.854775807Z" },
        Fixture { -1, "1969-12-31T23:59:59.999999999Z" },
        Fixture { -1000000000, "1969-12-31T23:59:59Z" },
        Fixture { 1, "1970-01-01T00:00:00.000000001Z" },
        Fixture { 123400000, "1970-01-01T00:00:00.1234Z" },
        Fixture { 0, "1970-01-01T00:00:00Z" },
    ];
    let config = log::Logger { minimum: log::Level.Trace };
    var timestamp: u8[>..] = []; timestamp.resize(500, 't');
    var scratch:   u8[>..] = []; scratch.resize(1000, 's');
    var clocks = 0;
    var sinks = 0;
    for fixture, i in fixtures {
        var expected: u8[>..] = []; expected.append("[INFO] timestamp=\"");
        expected.append(fixture.expected); expected.append("\" payload\n");
        fn clock() -> i64 { clocks++; fixture.sample }
        fn sink(line: const u8[:]) -> bool { sinks++; assert(line == expected); false }
        let result = utc_log::emit(config, log::Level.Info, "payload", timestamp, scratch, clock, sink);
        assert(result == log::Status.SinkError && clocks == i + 1 && sinks == i + 1);
        assert(timestamp == fixture.expected && scratch == expected);
        assert(timestamp.len >= 20 && timestamp.len <= 30);
    }
}
fn hostile_messages() {
    let config = log::Logger { .. };
    var timestamp: u8[>..] = [];
    var scratch:   u8[>..] = [];
    var message:   u8[>..] = [];
    for i in 256 { message.push(i as! u8); }
    fn clock() -> i64 { 0 }
    var calls = 0;
    fn sink(line: const u8[:]) -> bool { calls++; true }
    assert(utc_log::emit(config, log::Level.Info, message, timestamp, scratch, clock, sink) == log::Status.Written);
    assert(calls == 1);
    assert(scratch == "[INFO] timestamp=\"1970-01-01T00:00:00Z\" \\x00\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\x09\\x0a\\x0b\\x0c\\x0d\\x0e\\x0f\\x10\\x11\\x12\\x13\\x14\\x15\\x16\\x17\\x18\\x19\\x1a\\x1b\\x1c\\x1d\\x1e\\x1f !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\\\]^_`abcdefghijklmnopqrstuvwxyz{|}~\\x7f\\x80\\x81\\x82\\x83\\x84\\x85\\x86\\x87\\x88\\x89\\x8a\\x8b\\x8c\\x8d\\x8e\\x8f\\x90\\x91\\x92\\x93\\x94\\x95\\x96\\x97\\x98\\x99\\x9a\\x9b\\x9c\\x9d\\x9e\\x9f\\xa0\\xa1\\xa2\\xa3\\xa4\\xa5\\xa6\\xa7\\xa8\\xa9\\xaa\\xab\\xac\\xad\\xae\\xaf\\xb0\\xb1\\xb2\\xb3\\xb4\\xb5\\xb6\\xb7\\xb8\\xb9\\xba\\xbb\\xbc\\xbd\\xbe\\xbf\\xc0\\xc1\\xc2\\xc3\\xc4\\xc5\\xc6\\xc7\\xc8\\xc9\\xca\\xcb\\xcc\\xcd\\xce\\xcf\\xd0\\xd1\\xd2\\xd3\\xd4\\xd5\\xd6\\xd7\\xd8\\xd9\\xda\\xdb\\xdc\\xdd\\xde\\xdf\\xe0\\xe1\\xe2\\xe3\\xe4\\xe5\\xe6\\xe7\\xe8\\xe9\\xea\\xeb\\xec\\xed\\xee\\xef\\xf0\\xf1\\xf2\\xf3\\xf4\\xf5\\xf6\\xf7\\xf8\\xf9\\xfa\\xfb\\xfc\\xfd\\xfe\\xff\n");
    for length in [4095, 4096, 4097, 8192] {
        message.clear(); message.resize(length, 'a');
        calls = 0;
        assert(utc_log::emit(config, log::Level.Info, message, timestamp, scratch, clock, sink) == log::Status.Written);
        assert(calls == 1 && timestamp == "1970-01-01T00:00:00Z");
        let prefix = "[INFO] timestamp=\"1970-01-01T00:00:00Z\" ";
        assert(scratch[..prefix.len] == prefix);
        let count = if length > 4096 { 4096 } else { length };
        for byte in scratch[prefix.len..prefix.len + count] { assert(byte == 'a'); }
        assert(scratch[prefix.len + count..] == (if length > 4096 { "... [truncated]\n" } else { "\n" }));
        assert(scratch.len <= log::MAX_RECORD_LINE_BYTES);
    }
    message.clear(); message.resize(4097, 0xff);
    calls = 0;
    assert(utc_log::emit(config, log::Level.Info, message, timestamp, scratch, clock, sink) == log::Status.Written);
    assert(calls == 1);
    let unsafe_prefix = "[INFO] timestamp=\"1970-01-01T00:00:00Z\" ";
    assert(scratch[..unsafe_prefix.len] == unsafe_prefix);
    for i in 4096 { assert(scratch[unsafe_prefix.len + i * 4..unsafe_prefix.len + (i + 1) * 4] == "\\xff"); }
    assert(scratch[unsafe_prefix.len + 4096 * 4..] == "... [truncated]\n");
    assert(scratch.len <= log::MAX_RECORD_LINE_BYTES);
    message.clear();
    assert(utc_log::emit(config, log::Level.Info, message, timestamp, scratch, clock, sink) == log::Status.Written);
    assert(scratch == "[INFO] timestamp=\"1970-01-01T00:00:00Z\" \n");
}
fn main() {
    filtering_and_levels();
    timestamps_and_reuse();
    hostile_messages();
}
