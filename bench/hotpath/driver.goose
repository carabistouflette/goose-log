// SPDX-License-Identifier: Apache-2.0
// Native Goose caller: message, configuration, and expected bytes load before timing.
import logger from "../..";
import binary;
import os;
import std;

fn main() {
    assert(arg_count() == 3);
    var path: u8[>..] = [];
    arg(1, path);
    var input: u8[>..] = [];
    assert(read_file(path, input));
    var reader = binary::reader(input);
    let header, header_ok = binary::read_bytes(reader, 13);
    assert(header_ok && header[0] < 7 && header[1] < 7 && header[3] < 7);
    let message_size, message_ok = binary::read_u32le(header, 4);
    let expected_size, expected_ok = binary::read_u32le(header, 8);
    assert(message_ok && expected_ok);
    let message, body_ok = binary::read_bytes(reader, message_size);
    let expected, output_ok = binary::read_bytes(reader, expected_size);
    assert(body_ok && output_ok && reader.pos == input.len);
    let levels = [log::Level.Trace, log::Level.Debug, log::Level.Info, log::Level.Warn,
        log::Level.Error, log::Level.Fatal, log::Level.Off];
    let config = log::Logger { minimum: levels[header[0] as i64], color: header[2] != 0 };
    let accepted = header[12] != 0;
    var argument: u8[>..] = [];
    arg(2, argument);
    let count, count_ok = parse_int(argument);
    assert(count_ok && count > 0 && count <= 10000000);
    var scratch = str("sentinel");
    // Check full output/status and warm the same scratch used by timed calls.
    for i in 1000 {
        let level = levels[header[1 + 2 * (i % 2)] as i64];
        var calls = 0;
        let status = log::emit(config, level, message, scratch) { line =>
            calls += 1;
            assert(line == expected);
            true
        };
        assert(calls == (if accepted { 1 } else { 0 }));
        assert(status == (if accepted { log::Status.Written } else { log::Status.Filtered }));
        assert(scratch == expected);
    }
    var checksum: i64 = 0;
    var calls:    i64 = 0;
    var written:  i64 = 0;
    var filtered: i64 = 0;
    let start = clock_ns();
    for i in count {
        let level = levels[header[1 + 2 * (i % 2)] as i64];
        let status = log::emit(config, level, message, scratch) { line =>
            calls += 1;
            checksum += line.len + line[i % line.len];
            true
        };
        written += if status == log::Status.Written { 1 } else { 0 };
        filtered += if status == log::Status.Filtered { 1 } else { 0 };
    }
    let elapsed = clock_ns() - start;
    assert(scratch == expected && calls == (if accepted { count } else { 0 }));
    assert(written == calls);
    assert(filtered == count - calls);
    print("{\"elapsed_ns\":", elapsed, ",\"iterations\":", count,
          ",\"calls\":", calls, ",\"checksum\":", checksum, "}");
}
