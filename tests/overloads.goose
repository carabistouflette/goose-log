// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import std;

// A caller's exact overload must not affect the logger's input bound.
fn min(a: i64, b: i64) -> i64 { a }

fn main() {
    let config = log::Logger { .. };
    var message: u8[>..] = [];
    for i in 5000 { message.push(0xff); }
    var scratch: u8[>..] = [];
    assert(log::render(config, log::Level.Info, message, scratch));
    assert(scratch.len == 7 + 4096 * 4 + 15 + 1);
    assert(scratch[scratch.len - 16..] == "... [truncated]\n");
    assert(log::render(config, log::Level.Info, "abc", scratch));
    assert(scratch == "[INFO] abc\n");
    assert(log::render(config, log::Level.Info, "request completed\xff status=200 bytes=1234", scratch));
    assert(scratch == "[INFO] request completed\\xff status=200 bytes=1234\n");
    print("overload isolation tests passed");
}
