// SPDX-License-Identifier: Apache-2.0
import diagnostics from "../examples/cli";
import logger from "..";
import std;
import os;
root struct Parsed { value: u8[>..] }
fn checked(value: const u8[:]) -> u8[>..] {
    if value.len == 0 {
        diagnostics::write(diagnostics::Event.Failed, 0, 1);
        exit(1);
    }
    str(value)
}
fn load(value: const u8[:], parsed: Parsed&) { parsed.value = checked(value); }
fn main() {
    let argv = args();
    assert(argv.len == 4);
    // Terminal callbacks remain usable while caller data is built or borrowed.
    var parsed = Parsed { value: str("previous") };
    load("retained", parsed);
    let borrowed: const u8[:] = parsed.value;
    let copied = checked(borrowed);
    assert(copied == "retained" && parsed.value == "retained");
    assert(diagnostics::message(diagnostics::Event.ChildFailed, 18446744073709551615, 4294967295) ==
        "child_failed duration_ns=18446744073709551615 outcome=4294967295");
    assert(!diagnostics::active());
    assert(diagnostics::write(diagnostics::Event.Started));
    assert(!diagnostics::configure(""));
    assert(!diagnostics::write(diagnostics::Event.Started));
    assert(diagnostics::configure(argv[1], log::Level.Off));
    assert(!diagnostics::active());
    assert(diagnostics::write(diagnostics::Event.Started));
    assert(!file_exists(argv[1]));
    assert(diagnostics::configure(argv[1]));
    assert(diagnostics::active());
    assert(diagnostics::write(diagnostics::Event.Started));
    assert(diagnostics::configure(argv[3]));
    assert(!diagnostics::write(diagnostics::Event.Failed));
    assert(!diagnostics::active());
    assert(make_dir(argv[2]));
    assert(!diagnostics::write(diagnostics::Event.Failed));
    assert(!file_exists(argv[3]));
    assert(diagnostics::configure(argv[1]));
    assert(diagnostics::write(diagnostics::Event.Returned));
}
