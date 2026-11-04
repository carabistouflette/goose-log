// SPDX-License-Identifier: Apache-2.0
// C-host bridge only: logger state and storage belong to this benchmark app.
import logger from "../..";
import emit from "../../.build/compare/goose-logger";

extern fn comparison_sink(line: const u8[:]) -> bool;
const levels = [log::Level.Trace, log::Level.Debug, log::Level.Info, log::Level.Warn,
    log::Level.Error, log::Level.Fatal, log::Level.Off];
var config = log::Logger { .. };
var scratch:        u8[>..] = [];
var record_scratch: u8[>..] = [];
var timestamp:      u8[>..] = [];

export fn comparison_set_minimum(minimum: i32) {
    assert(minimum >= 0 && minimum < 7);
    config.minimum = levels[minimum];
}

export fn comparison_goose_log(level: i32, message: const u8[:]) -> bool {
    assert(level >= 0 && level < 6);
    let status = log::emit(config, levels[level], message, scratch, comparison_sink);
    status == log::Status.Written
}

// Equivalent logical record profile, with different native wire formats.
// Both adapters use the SAME upstream timestamp formatter/redactor here.
export fn comparison_macho_record(message: const u8[:]) -> const u8[:] {
    record_scratch.clear();
    emit::record(record_scratch, 1700000000000000000, levels::Level.Info, "app.goose", 42, message);
    record_scratch.push('\n');
    record_scratch
}

export fn comparison_goose_record(message: const u8[:]) -> const u8[:] {
    timestamp.clear();
    emit::stamp(timestamp, 1700000000000000000);
    let clean = sanitize::text(message);
    let record = log::Record { message: clean, timestamp: timestamp, file: "app.goose", line: 42 };
    log::render_record(config, record, record_scratch);
    record_scratch
}

fn main() {}
