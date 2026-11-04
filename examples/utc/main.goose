// SPDX-License-Identifier: Apache-2.0
import logger from "../..";
import time from "carabistouflette/goose-time@343887caeee0a1f4e2e536ff322fcafb454e11bd";
import utc from ".";
import os;

fn sample_wall_clock() -> i64 { time_ns() }
fn main() {
    let config = log::Logger { .. };
    var timestamp: u8[>..] = [];
    var scratch:   u8[>..] = [];
    let status = utc_log::emit(config, log::Level.Info, "application started", timestamp, scratch, sample_wall_clock) { line =>
        write_stderr(line);
        // write_stderr has no error result; this example cannot check delivery.
        true
    };
    if status == log::Status.SinkError { exit(1); }
}
