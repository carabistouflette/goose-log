// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import os;

fn main() {
    let config = log::Logger { .. };
    var scratch: u8[>..] = [];
    let status = log::emit(config, log::Level.Info, "Hello, Goose!", scratch) { line =>
        write_stderr(line);
        // Goose's write_stderr does not report I/O failures.
        true
    };
    if status == log::Status.SinkError { exit(1); }
}
