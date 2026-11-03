// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import std;
import os;

fn benchmark(name: const u8[:], message: const u8[:], count: i64) {
    let config = log::Logger { .. };
    var scratch:  u8[>..] = [];
    var checksum: i64     = 0;
    for i in 1000 { log::render(config, log::Level.Info, message, scratch); }
    let start = clock_ns();
    for i in count {
        // Alternate severity and consume bytes, keeping the work observable.
        let level = if i % 2 == 0 { log::Level.Info } else { log::Level.Warn };
        assert(log::render(config, level, message, scratch));
        checksum += scratch.len + scratch[i % scratch.len];
    }
    let elapsed = clock_ns() - start;
    print(name, ": ", elapsed / (count as f64), " ns/line; checksum=", checksum);
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
    benchmark("printable", "request completed status=200 bytes=1234", count);
    var escaped: u8[>..] = [];
    for i in 256 { escaped.push(0xff); }
    benchmark("escaped-256", escaped, count);
    var oversized: u8[>..] = [];
    for i in 100000 { oversized.push(0xff); }
    benchmark("truncated-100k", oversized, count);
}
