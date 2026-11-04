// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import binary;
import os;

fn read_text(reader: binary::Reader&) -> const u8[:] {
    let size, ok = binary::read_u32le(reader);
    assert(ok);
    let text, text_ok = binary::read_bytes(reader, size);
    assert(text_ok);
    text
}

fn main() {
    var path: u8[>..] = [];
    arg(1, path);
    var data: u8[>..] = [];
    assert(read_file(path, data));
    var reader = binary::reader(data);
    let header, ok = binary::read_bytes(reader, 8);
    assert(ok && header[0] < 7 && header[1] < 7);
    let line, line_ok = binary::read_u32le(header, 3);
    assert(line_ok);
    let message = read_text(reader);
    let timestamp = read_text(reader);
    let target = read_text(reader);
    let file = read_text(reader);
    var fields: log::Field[>..] = [];
    for i in header[7] {
        let sensitive, sensitive_ok = binary::read_u8(reader);
        assert(sensitive_ok);
        let key = read_text(reader);
        let value = read_text(reader);
        fields.push(log::Field { key: key, value: value, sensitive: sensitive != 0 });
    }
    assert(reader.pos == data.len);
    let levels = [log::Level.Trace, log::Level.Debug, log::Level.Info, log::Level.Warn,
        log::Level.Error, log::Level.Fatal, log::Level.Off];
    let config = log::Logger { minimum: levels[header[0]], color: header[2] != 0 };
    let record = log::Record { level: levels[header[1]], message: message, timestamp: timestamp,
        target: target, file: file, line: line, fields: fields };
    var scratch = str("sentinel");
    let accepted = log::render_record(config, record, scratch);
    assert(accepted == (header[0] != 6 && header[1] != 6 && header[1] >= header[0]));
    assert(scratch.len <= 28592);
    write_stdout(scratch);
}
