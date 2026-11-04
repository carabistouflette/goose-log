// SPDX-License-Identifier: Apache-2.0
// Application-owned append adapter. The path is explicit, and every enabled
// call opens and closes it. A failure may follow partial output; no rollback,
// durable flush, or atomicity between concurrent writers is promised.
import logger from "..";
import os;

fn main() {
    if arg_count() != 2 {
        write_stderr("usage: file PATH\n");
        exit(2);
    }
    var path: u8[>..] = [];
    arg(1, path);
    let config = log::Logger { .. };
    var scratch: u8[>..] = [];
    let status = log::emit(config, log::Level.Info, "Hello, file!", scratch) { line =>
        append_file(path, line)
    };
    if status == log::Status.SinkError {
        write_stderr("file sink failed\n");
        exit(1);
    }
}
