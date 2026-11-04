// SPDX-License-Identifier: Apache-2.0
// This application owns the reusable scratch. Input lives in its C host.
import logger from "../..";

extern fn allocation_sink(line: const u8[:]) -> bool;
var scratch: u8[>..] = [];

export fn allocation_emit(profile: i32, message: const u8[:]) -> i32 {
    assert(profile >= 0 && profile <= 2);
    let config = log::Logger { minimum: if profile == 2 { log::Level.Off } else { log::Level.Trace }, color: true };
    var status = log::Status.Filtered;
    if profile == 1 {
        let fields = [log::Field { key: message, value: message }; 9];
        let record = log::Record { level: log::Level.Fatal, message: message,
            timestamp: message, target: message, file: message, line: 4294967295, fields: fields };
        status = log::emit_record(config, record, scratch, allocation_sink);
    } else {
        status = log::emit(config, log::Level.Fatal, message, scratch, allocation_sink);
    }
    if status == log::Status.Written { 1 }
    else if status == log::Status.Filtered { 0 }
    else { -1 }
}

export fn allocation_output() -> const u8[:] { scratch }
fn main() {}
