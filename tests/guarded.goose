// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import os;
import std;

extern fn guarded_offset(data: const u8[:], readable: i64) -> i64;
extern fn guarded_restore(data: const u8[:], readable: i64);
extern fn guarded_touch(data: const u8[:]) -> u8;

fn main() {
    var backing: u8[>..] = [];
    for i in 1048576 { backing.push(0xff); }
    var scratch = str("sentinel");
    let config = log::Logger { .. };
    if arg_count() > 1 {
        let offset = guarded_offset(backing, 0);
        write_stderr("guard-page fault control\n");
        // The runner requires a protected-memory fault, not any failing exit.
        print(guarded_touch(backing[offset..]));
        guarded_restore(backing, 0);
        assert(false);
    }
    // The filtered message starts on inaccessible memory. Neither scanning
    // nor calling the sink is permitted, and existing scratch must survive.
    let filtered_offset = guarded_offset(backing, 0);
    assert(!log::render(config, log::Level.Debug, backing[filtered_offset..], scratch));
    var calls = 0;
    let filtered = log::emit(config, log::Level.Debug, backing[filtered_offset..], scratch) { line =>
        calls += 1;
        true
    };
    guarded_restore(backing, 0);
    assert(filtered == log::Status.Filtered && calls == 0 && scratch == "sentinel");

    // The first byte beyond the documented cap starts an inaccessible page.
    let offset = guarded_offset(backing, 4096);
    assert(log::render(config, log::Level.Info, backing[offset..], scratch));
    let status = log::emit(config, log::Level.Info, backing[offset..], scratch) { line =>
        calls += 1;
        assert(line.len == 7 + 4096 * 4 + 15 + 1);
        true
    };
    guarded_restore(backing, 4096);
    assert(status == log::Status.Written && calls == 1);
    var expected = str("[INFO] ");
    for i in 4096 { expected.append("\\xff"); }
    expected.append("... [truncated]\n");
    assert(scratch == expected);
    print("guarded input tests passed");
}
