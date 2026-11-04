// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import binary;
import os;
import std;

fn sequence_text(reader: binary::Reader&) -> const u8[:] {
    let size, ok = binary::read_u32le(reader);
    assert(ok);
    let bytes, bytes_ok = binary::read_bytes(reader, size);
    assert(bytes_ok);
    bytes
}

fn sequence_check(ok: bool, step: i64, check: const u8[:]) {
    if !ok { print("sequence failure step=", step, " check=", check); assert(false); }
}

fn sequence_status(status: log::Status) -> u8 {
    if status == log::Status.Filtered { 0 }
    else if status == log::Status.Written { 1 }
    else { assert(status == log::Status.SinkError); 2 }
}

fn main() {
    assert(arg_count() == 2);
    var path: u8[>..] = [];
    arg(1, path);
    var input: u8[>..] = [];
    assert(read_file(path, input));
    var reader = binary::reader(input);
    let levels = [log::Level.Trace, log::Level.Debug, log::Level.Info, log::Level.Warn,
        log::Level.Error, log::Level.Fatal, log::Level.Off];
    var scratch = str("sentinel");
    var retained = str("capture");
    var step: i64 = 0;
    while reader.pos < input.len {
        let frame_start = reader.pos;
        let header, header_ok = binary::read_bytes(reader, 10);
        assert(header_ok && header[0] < 7 && header[1] < 7 && header[2] < 7);
        let line, line_ok = binary::read_u32le(header, 6);
        assert(line_ok);
        let message = sequence_text(reader);
        let timestamp = sequence_text(reader);
        let target = sequence_text(reader);
        let file = sequence_text(reader);
        var fields: log::Field[>..] = [];
        for i in header[5] {
            let sensitive, ok = binary::read_u8(reader);
            assert(ok);
            let key = sequence_text(reader);
            let value = sequence_text(reader);
            fields.push(log::Field { key: key, value: value, sensitive: sensitive != 0 });
        }
        let expected, expected_ok = binary::read_bytes(reader, 3);
        assert(expected_ok);
        let expected_scratch = sequence_text(reader);
        let expected_retained = sequence_text(reader);
        let original_frame = str(input[frame_start..reader.pos]);
        let config = log::Logger { minimum: levels[header[1]], color: header[3] != 0 };
        let level = levels[header[2]];
        let record = log::Record { level: level, message: message, timestamp: timestamp,
            target: target, file: file, line: line, fields: fields };
        var builds = 0;
        var calls = 0;
        fn sink(text: const u8[:]) -> bool {
            calls += 1;
            sequence_check(builds == (if header[0] == 4 || header[0] == 5 { 1 } else { 0 }), step, "builder-before-sink");
            sequence_check(text == expected_scratch, step, "sink-bytes");
            retained.clear();
            retained.append(text);
            header[4] != 0
        }
        fn borrowed() -> const u8[:] { builds += 1; message }
        fn owned() -> u8[>..] { builds += 1; str(message) }
        var result: u8 = 0;
        if header[0] == 0 { result = if log::render(config, level, message, scratch) { 1 } else { 0 }; }
        else if header[0] == 1 { result = sequence_status(log::emit(config, level, message, scratch, sink)); }
        else if header[0] == 2 { result = if log::render_record(config, record, scratch) { 1 } else { 0 }; }
        else if header[0] == 3 { result = sequence_status(log::emit_record(config, record, scratch, sink)); }
        else if header[0] == 4 { result = sequence_status(log::emit_lazy(config, level, scratch, borrowed, sink)); }
        else if header[0] == 5 { result = sequence_status(log::emit_lazy(config, level, scratch, owned, sink)); }
        else { scratch.clear(); scratch.append(message); result = 3; }
        sequence_check(result == expected[0], step, "status");
        sequence_check(builds == expected[1] && calls == expected[2], step, "counts");
        sequence_check(scratch == expected_scratch, step, "scratch");
        var churn = str(message, target, file);
        sequence_check(churn.len == message.len + target.len + file.len, step, "churn");
        sequence_check(retained == expected_retained, step, "retained");
        sequence_check(input[frame_start..reader.pos] == original_frame, step, "input-preserved");
        step += 1;
    }
    print("sequence operations passed: ", step);
}
