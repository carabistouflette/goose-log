// SPDX-License-Identifier: Apache-2.0
// A standalone lifecycle consumer for the Honk integration boundary.
import logger from "../..";
import diagnostics from ".";
import std;
import os;

fn usage() {
    write_stderr("usage: consumer COUNT [--log-file PATH] [--fail]\n");
    exit(2);
}

var started_ns: i64 = 0;

fn event(kind: diagnostics::Event, outcome: u32 = 0) {
    var duration: u64 = 0;
    if diagnostics::active() && kind != diagnostics::Event.Started {
        let elapsed = clock_ns() - started_ns;
        if elapsed > 0 { duration = elapsed as u64; }
    }
    if !diagnostics::write(kind, duration, outcome) {
        // Deliberately bypass the failed sink: no retry or recursive logging.
        write_stderr("diagnostic log failed\n");
        exit(1);
    }
}

fn main() {
    let argv = args();
    if argv.len < 2 { usage(); }
    let count, valid = parse_int(argv[1]);
    if !valid || count < 0 || count > 100000 { usage(); }
    var path: u8[>..] = [];
    var has_path = false;
    var fail = false;
    var at = 2;
    while at < argv.len {
        if argv[at] == "--log-file" && !has_path && at + 1 < argv.len {
            path = str(argv[at + 1]); has_path = true; at += 2;
        } else if argv[at] == "--fail" && !fail {
            fail = true; at += 1;
        } else { usage(); }
    }
    if has_path {
        if !diagnostics::configure(path) {
            write_stderr("invalid diagnostic configuration\n"); exit(2);
        }
        started_ns = clock_ns();
    }
    event(diagnostics::Event.Started);
    var checksum: i64 = 0;
    for i in count {
        checksum += i;
        event(diagnostics::Event.ItemCompleted);
    }
    if fail {
        event(diagnostics::Event.Failed, 7);
        write_stderr("requested operation failed\n"); exit(7);
    }
    print("{\"processed\":", count, ",\"checksum\":", checksum, "}");
    if !diagnostics::stdout_ok() {
        event(diagnostics::Event.Failed, 1);
        write_stderr("cannot write standard output\n"); exit(1);
    }
    event(diagnostics::Event.Returned);
}
