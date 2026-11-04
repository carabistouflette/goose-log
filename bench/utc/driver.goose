// SPDX-License-Identifier: Apache-2.0
// Optional consumer component measurements, with runtime fixtures and full-byte checksums.
import logger from "../..";
import time from "carabistouflette/goose-time@343887caeee0a1f4e2e536ff322fcafb454e11bd";
import utc from "../../examples/utc";
import binary;
import os;
import std;

const ITEMS = 8;
const LEVELS = [log::Level.Trace, log::Level.Debug, log::Level.Info, log::Level.Warn,
               log::Level.Error, log::Level.Fatal, log::Level.Off];
struct Work { sample: i64 = 0, message_start: i64 = 0, message_size: i64 = 0,
    timestamp_start: i64 = 0, timestamp_size: i64 = 0, plain_start: i64 = 0,
    plain_size: i64 = 0, record_start: i64 = 0, record_size: i64 = 0 }
struct Totals { elapsed_ns: i64 = 0, sinks: i64 = 0, clocks: i64 = 0, written: i64 = 0,
                filtered: i64 = 0, formatted: i64 = 0, bytes: i64 = 0, checksum: i64 = 0, last_ns: i64 = 0 }

fn number(text: const u8[:], maximum: i64) -> i64 {
    let value, ok = parse_int(text);
    assert(ok && value >= 0 && value <= maximum);
    value
}
fn blob(input: const u8[:], at: i64&) -> i64, i64 {
    let size, size_ok = binary::read_u32le(input, at);
    assert(size_ok); at += 4;
    let view, ok = binary::read_bytes(input, at, size);
    assert(ok); at += size;
    return at - size, size;
}
fn consume(bytes: const u8[:], result: Totals&) {
    result.bytes += bytes.len;
    result.checksum += bytes.len;
    for byte, i in bytes { result.checksum += byte * (i + 1); }
}
fn hex(bytes: const u8[:]) -> u8[>..] {
    let digits = "0123456789abcdef";
    var out: u8[>..] = [];
    for byte in bytes { out.push(digits[byte >> 4]); out.push(digits[byte & 15]); }
    out
}
// Stages: 0 plain, 1 preformatted, 2 format-only, 3 fixed adapter,
// 4 OS adapter, 5 filtered record, 6 filtered adapter, 7 OS clock-only.
// Stage dispatch, assertions, counters, and checksums are part of timed work.
fn phase(stage: i64, config: log::Logger, off: log::Logger, level: log::Level, items: const Work[:], input: const u8[:],
         count: i64, timestamp: u8[>..]&, scratch: u8[>..]&, samples: i64[:]) -> Totals {
    var result = Totals { .. };
    let start = clock_ns();
    for i in count {
        let item = items[i % items.len];
        let message = input[item.message_start..item.message_start + item.message_size];
        let stamp = input[item.timestamp_start..item.timestamp_start + item.timestamp_size];
        fn sink(line: const u8[:]) -> bool {
            result.sinks++;
            consume(line, result);
            true
        }
        fn sample() -> i64 {
            let value = if stage == 4 || stage == 7 { time_ns() } else { item.sample };
            result.clocks++; result.last_ns = value;
            samples[i] = value;
            value
        }
        if stage == 2 {
            timestamp.clear();
            assert(time::append_rfc3339(timestamp, time::from_unix_nanoseconds(item.sample)) == time::Error.None);
            result.formatted++;
            consume(timestamp, result);
        } else if stage == 7 {
            let value = sample();
            result.checksum += value % 1000000;
        } else {
            var status = log::Status.Filtered;
            if stage == 0 {
                let record = log::Record { level: level, message: message };
                status = log::emit_record(config, record, scratch, sink);
            } else if stage == 1 {
                let record = log::Record { level: level, message: message, timestamp: stamp };
                status = log::emit_record(config, record, scratch, sink);
            } else if stage == 3 || stage == 4 {
                status = utc_log::emit(config, level, message, timestamp, scratch, sample, sink);
            } else if stage == 5 {
                let record = log::Record { level: level, message: message, timestamp: stamp };
                status = log::emit_record(off, record, scratch, sink);
            } else {
                assert(stage == 6);
                status = utc_log::emit(off, level, message, timestamp, scratch, sample, sink);
            }
            if stage == 5 || stage == 6 {
                assert(status == log::Status.Filtered); result.filtered++;
            } else {
                assert(status == log::Status.Written); result.written++;
            }
        }
    }
    result.elapsed_ns = clock_ns() - start;
    result
}
fn main() {
    let argv = args();
    assert(argv.len == 7);
    let stage = number(argv[1], 7);
    let count = number(argv[3], 1000000);
    let warmup = number(argv[4], 1024);
    assert(count > 0);
    var input: u8[>..] = [];
    assert(read_file(argv[2], input));
    assert(input.len >= 4 && input[0] < 7 && input[1] < 7 && input[2] < 7 && input[3] <= 1);
    let config = log::Logger { minimum: LEVELS[input[0]], color: input[3] != 0 };
    let off = log::Logger { minimum: LEVELS[input[1]], color: input[3] != 0 };
    let level = LEVELS[input[2]];
    assert(log::enabled(config, level) && !log::enabled(off, level));
    var items: Work[ITEMS] = [Work { .. }; ITEMS];
    var at = 4;
    for i in ITEMS {
        let value, ok = binary::read_i64le(input, at);
        assert(ok); at += 8;
        let ms, ml = blob(input, at);
        let ts, tl = blob(input, at);
        let ps, pl = blob(input, at);
        let rs, rl = blob(input, at);
        items[i] = Work { value, ms, ml, ts, tl, ps, pl, rs, rl };
    }
    assert(at == input.len);
    var timestamp: u8[>..] = [];
    var scratch:   u8[>..] = [];
    // Validate every complete result against Python-created bytes outside timing.
    for item in items {
        let message = input[item.message_start..item.message_start + item.message_size];
        let expected_stamp = input[item.timestamp_start..item.timestamp_start + item.timestamp_size];
        let expected_plain = input[item.plain_start..item.plain_start + item.plain_size];
        let expected_record = input[item.record_start..item.record_start + item.record_size];
        fn sample() -> i64 { item.sample }
        var sinks = 0;
        let status = utc_log::emit(config, level, message, timestamp, scratch, sample) { line =>
            sinks++; assert(line == expected_record); true
        };
        assert(status == log::Status.Written && sinks == 1 && timestamp == expected_stamp);
        let record = log::Record { level: level, message: message };
        assert(log::render_record(config, record, scratch) && scratch == expected_plain);
    }
    timestamp.clear(); timestamp.append("stamp-sentinel");
    scratch.clear(); scratch.append("line-sentinel");
    var warm_samples: i64[>..] = []; warm_samples.resize(warmup, 0);
    let warmed = phase(stage, config, off, level, items, input, warmup, timestamp, scratch, warm_samples);
    var samples: i64[>..] = []; samples.resize(count, 0);
    let measured = phase(stage, config, off, level, items, input, count, timestamp, scratch, samples);
    if stage == 4 || stage == 7 {
        // Trace serialization and file I/O are outside timing; per-call stores are timed.
        var trace: u8[>..] = [];
        for value in samples {
            let bits = value as! u64;
            for j in 8 { trace.push(((bits >> (8 * j)) & 255) as! u8); }
        }
        assert(write_file(argv[5], trace));
    }
    // Complete final bytes are independently checked by Python too.
    let timestamp_hex = hex(timestamp);
    let line_hex = hex(scratch);
    print("{\"elapsed_ns\":", measured.elapsed_ns, ",\"iterations\":", count,
          ",\"sinks\":", measured.sinks, ",\"clocks\":", measured.clocks,
          ",\"written\":", measured.written, ",\"filtered\":", measured.filtered,
          ",\"formatted\":", measured.formatted, ",\"bytes\":", measured.bytes,
          ",\"checksum\":", measured.checksum, ",\"last_ns\":", measured.last_ns,
          ",\"timestamp_hex\":\"", timestamp_hex, "\",\"line_hex\":\"", line_hex, "\"}");
}
