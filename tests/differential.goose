// SPDX-License-Identifier: Apache-2.0
// Batched public-API driver for the independent Python byte oracle.
import logger from "..";
import binary;
import os;
import std;

fn main() {
    assert(arg_count() == 2);
    var path: u8[>..] = [];
    arg(1, path);
    var fixtures: u8[>..] = [];
    assert(read_file(path, fixtures));
    var reader = binary::reader(fixtures);
    let levels = [log::Level.Debug, log::Level.Info, log::Level.Warn, log::Level.Error, log::Level.Off];
    var rendered = str("sentinel");
    var emitted = str("sentinel");
    var cases = 0;
    while reader.pos < fixtures.len {
        let header, header_ok = binary::read_bytes(reader, 13);
        assert(header_ok && header[0] < 5 && header[1] < 5);
        let input_size, input_ok = binary::read_u32le(header, 4);
        let expected_size, expected_ok = binary::read_u32le(header, 8);
        assert(input_ok && expected_ok);
        let message, message_ok = binary::read_bytes(reader, input_size);
        let expected, bytes_ok = binary::read_bytes(reader, expected_size);
        assert(message_ok && bytes_ok);
        let config = log::Logger { minimum: levels[header[0] as i64], color: header[2] != 0 };
        let level = levels[header[1] as i64];
        let accepted = header[12] != 0;
        assert(log::enabled(config, level) == accepted);
        assert(log::render(config, level, message, rendered) == accepted);
        if rendered != expected { print("render mismatch at case ", cases); assert(false); }
        var calls = 0;
        let status = log::emit(config, level, message, emitted) { line =>
            calls += 1;
            assert(line == expected);
            header[3] != 0
        };
        let expected_status = if header[12] == 0 { log::Status.Filtered }
            else if header[12] == 1 { log::Status.Written } else { log::Status.SinkError };
        assert(status == expected_status);
        assert(calls == (if accepted { 1 } else { 0 }));
        if emitted != expected { print("emit mismatch at case ", cases); assert(false); }
        assert(emitted.len <= 16417);
        cases += 1;
    }
    print("differential cases passed: ", cases);
}
