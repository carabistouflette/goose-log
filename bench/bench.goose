// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import std;
import os;

const SAMPLES = 7;

fn report(name: const u8[:], times: f64[:], checksum: i64) {
    sort(times);
    print(name, ": median=", times[times.len / 2], " ns/call; min=", times[0],
          "; max=", times[times.len - 1], "; checksum=", checksum);
}

fn benchmark(name: const u8[:], message: const u8[:], count: i64) {
    let config = log::Logger { .. };
    var scratch:  u8[>..] = [];
    var checksum: i64     = 0;
    for i in 1000 { log::render(config, log::Level.Info, message, scratch); }
    var times: f64[SAMPLES] = [0.0; SAMPLES];
    for sample in SAMPLES {
        let start = clock_ns();
        for i in count {
            // Alternate severity and consume bytes, keeping the work observable.
            let level = if i % 2 == 0 { log::Level.Info } else { log::Level.Warn };
            assert(log::render(config, level, message, scratch));
            checksum += scratch.len + scratch[i % scratch.len];
        }
        times[sample] = (clock_ns() - start) / (count as f64);
    }
    report(name, times, checksum);
}

fn benchmark_emit(message: const u8[:], count: i64) {
    let config = log::Logger { .. };
    var scratch: u8[>..] = [];
    for i in 1000 { log::emit(config, log::Level.Info, message, scratch) { line => true }; }
    var checksum: i64          = 0;
    var calls:    i64          = 0;
    var times:    f64[SAMPLES] = [0.0; SAMPLES];
    for sample in SAMPLES {
        let start = clock_ns();
        for i in count {
            let status = log::emit(config, log::Level.Info, message, scratch) { line =>
                calls += 1;
                checksum += line.len + line[i % line.len];
                true
            };
            assert(status == log::Status.Written);
        }
        times[sample] = (clock_ns() - start) / (count as f64);
    }
    assert(calls == SAMPLES * count);
    report("emit-printable", times, checksum);
}

// Runtime threshold prevents the native optimizer from assuming rejection.
// With the default Error threshold, all Debug/Info calls are filtered.
fn benchmark_filter(minimum: log::Level, count: i64) {
    let config = log::Logger { minimum: minimum };
    var scratch = str("sentinel");
    var checksum: i64          = 0;
    var times:    f64[SAMPLES] = [0.0; SAMPLES];
    for sample in SAMPLES {
        let start = clock_ns();
        for i in count {
            let level = if i % 2 == 0 { log::Level.Debug } else { log::Level.Info };
            let rendered = log::render(config, level, "filtered", scratch);
            checksum += scratch.len + (if rendered { 1 } else { 0 });
        }
        times[sample] = (clock_ns() - start) / (count as f64);
    }
    report("threshold (default: filtered)", times, checksum);
}

fn main() {
    var count: i64 = 100000;
    if arg_count() > 1 {
        var argument: u8[>..] = [];
        arg(1, argument);
        let parsed, ok = parse_int(argument);
        assert(ok && parsed > 0 && parsed <= 10000000);
        count = parsed;
    }
    var minimum = log::Level.Error;
    if arg_count() > 2 {
        var argument: u8[>..] = [];
        arg(2, argument);
        let parsed, ok = parse_int(argument);
        assert(ok && parsed >= 0 && parsed <= 4);
        let levels = [log::Level.Debug, log::Level.Info, log::Level.Warn, log::Level.Error, log::Level.Off];
        minimum = levels[parsed];
    }
    benchmark_filter(minimum, count);
    benchmark("empty", "", count);
    benchmark("printable", "request completed status=200 bytes=1234", count);
    benchmark_emit("request completed status=200 bytes=1234", count);
    var printable:   u8[>..] = [];
    var backslashes: u8[>..] = [];
    var mixed:       u8[>..] = [];
    for i in 4096 {
        printable.push('a');
        backslashes.push('\\');
        mixed.push((i % 256) as u8);
    }
    benchmark("printable-4096", printable, count);
    benchmark("backslashes-4096", backslashes, count);
    benchmark("mixed-4096", mixed, count);
    var escaped: u8[>..] = [];
    for i in 256 { escaped.push(0xff); }
    benchmark("escaped-256", escaped, count);
    var oversized: u8[>..] = [];
    for i in 100000 { oversized.push(0xff); }
    benchmark("truncated-100k", oversized, count);
}
