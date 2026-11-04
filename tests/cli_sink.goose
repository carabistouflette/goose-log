// SPDX-License-Identifier: Apache-2.0
import logger from "..";
import diagnostics from "../examples/cli";
import std;
import os;
fn main() {
    let argv = args();
    assert(argv.len == 3);
    let length, valid = parse_int(argv[2]);
    assert(valid && length >= 0 && length <= 16418);
    var line: u8[>..] = [];
    for i in length { line.push('x'); }
    if !diagnostics::append(argv[1], line) { exit(1); }
}
