// SPDX-License-Identifier: Apache-2.0
// Component probes for the real CLI helper; this is not Honk command latency.
import diagnostics from "../../examples/cli";
import logger from "../..";
import std;
import os;

const EVENTS = [diagnostics::Event.Started, diagnostics::Event.ItemCompleted,
    diagnostics::Event.Returned, diagnostics::Event.Failed, diagnostics::Event.ChildFailed];
const ITEMS = 64;
const MINIMUMS = [log::Level.Trace, log::Level.Debug, log::Level.Info, log::Level.Warn,
    log::Level.Error, log::Level.Fatal, log::Level.Off];
struct Work { event: diagnostics::Event, duration_ns: u64, outcome: u32 }
struct Totals { calls: i64 = 0, builders: i64 = 0, sinks: i64 = 0, bytes: i64 = 0, checksum: i64 = 0, successful_returns: i64 = -1 }

fn number(index: i64, maximum: i64) -> i64 {
    var text: u8[>..] = [];
    arg(index, text);
    let value, ok = parse_int(text);
    assert(ok && value >= 0 && value <= maximum);
    value
}

fn load(path: const u8[:], seed: i64, items: Work[:]) {
    var input: u8[>..] = [];
    assert(read_file(path, input));
    assert(input.len == 16 + ITEMS * 13 && input[..8] == "HNKBEN01");
    var recorded_seed: u64 = 0;
    for j in 8 { recorded_seed = (recorded_seed << 8) | input[8 + j]; }
    assert(recorded_seed == seed as u64);
    for i in ITEMS {
        let start = 16 + i * 13;
        let event = input[start] as i64;
        assert(event < EVENTS.len);
        var duration: u64 = 0;
        var outcome:  u32 = 0;
        for j in 8 { duration = (duration << 8) | input[start + 1 + j]; }
        for j in 4 { outcome = (outcome << 8) | input[start + 9 + j]; }
        items[i] = Work { event: EVENTS[event], duration_ns: duration, outcome: outcome };
    }
}

fn construct(items: const Work[:], count: i64) -> Totals {
    var result = Totals { calls: count };
    for i in count {
        let item = items[i % items.len];
        let text = diagnostics::message(item.event, item.duration_ns, item.outcome);
        result.builders += 1;
        result.bytes += text.len;
        result.checksum += text.len + text[i % text.len];
    }
    result
}

fn render(config: log::Logger, items: const Work[:], pool: const u8[:], starts: const i64[:], lengths: const i64[:],
          scratch: u8[>..]&, count: i64) -> Totals {
    var result = Totals { calls: count };
    for i in count {
        let index = i % items.len;
        let message = pool[starts[index]..starts[index] + lengths[index]];
        assert(log::render(config, diagnostics::level(items[index].event), message, scratch));
        result.bytes += scratch.len;
        result.checksum += scratch.len + scratch[i % scratch.len];
    }
    result
}

fn append(pool: const u8[:], starts: const i64[:], lengths: const i64[:], path: const u8[:], count: i64) -> Totals {
    var result = Totals { calls: count };
    for i in count {
        let index = i % starts.len;
        let line = pool[starts[index]..starts[index] + lengths[index]];
        assert(diagnostics::append(path, line));
        result.sinks += 1;
        result.bytes += line.len;
        result.checksum += line.len + line[i % line.len];
    }
    result
}

fn emit(config: log::Logger, items: const Work[:], path: const u8[:], scratch: u8[>..]&, count: i64, filtered: bool) -> Totals {
    var result = Totals { calls: count };
    for i in count {
        let item = items[i % items.len];
        fn build() -> u8[>..] {
            result.builders += 1;
            diagnostics::message(item.event, item.duration_ns, item.outcome)
        }
        let status = log::emit_lazy(config, diagnostics::level(item.event), scratch, build) { line =>
            result.sinks += 1;
            result.bytes += line.len;
            result.checksum += line.len + line[i % line.len];
            diagnostics::append(path, line)
        };
        assert(status == (if filtered { log::Status.Filtered } else { log::Status.Written }));
    }
    result
}

fn adapter(items: const Work[:], count: i64) -> Totals {
    var result = Totals { calls: count, builders: -1, sinks: -1, bytes: -1, checksum: -1, successful_returns: 0 };
    for i in count {
        let item = items[i % items.len];
        assert(diagnostics::write(item.event, item.duration_ns, item.outcome));
        result.successful_returns += 1;
    }
    result
}

fn phase(config: log::Logger, stage: const u8[:], items: const Work[:], messages: const u8[:], message_starts: const i64[:],
         message_lengths: const i64[:], lines: const u8[:], line_starts: const i64[:],
         line_lengths: const i64[:], path: const u8[:], scratch: u8[>..]&, count: i64) -> Totals {
    if stage == "construction" { return construct(items, count); }
    if stage == "render" { return render(config, items, messages, message_starts, message_lengths, scratch, count); }
    if stage == "append" { return append(lines, line_starts, line_lengths, path, count); }
    if stage == "full" { return emit(config, items, path, scratch, count, false); }
    if stage == "adapter" { return adapter(items, count); }
    assert(stage == "filtered");
    emit(config, items, path, scratch, count, true)
}

fn field(out: u8[>..]&, name: const u8[:], value: i64) {
    out.append(",\""); out.append(name); out.append("\":");
    if value < 0 { out.append("null"); }
    else { out.append(str(value)); }
}

fn main() {
    assert(arg_count() == 8);
    var stage: u8[>..] = []; arg(1, stage);
    assert(stage == "construction" || stage == "render" || stage == "append" || stage == "full" || stage == "adapter" || stage == "filtered");
    var fixture: u8[>..] = []; arg(2, fixture);
    let count = number(3, 1000000);
    let warmup = number(4, 1024);
    assert(count > 0);
    var path: u8[>..] = []; arg(5, path);
    let seed = number(6, 2147483647);
    let minimum = number(7, 6);
    let config = log::Logger { minimum: MINIMUMS[minimum] };
    assert(diagnostics::configure(path, config.minimum));
    var items: Work[ITEMS] = [Work { .. }; ITEMS];
    load(fixture, seed, items);
    var messages:        u8[>..]    = [];
    var lines:           u8[>..]    = [];
    var message_starts:  i64[ITEMS] = [0; ITEMS];
    var message_lengths: i64[ITEMS] = [0; ITEMS];
    var line_starts:     i64[ITEMS] = [0; ITEMS];
    var line_lengths:    i64[ITEMS] = [0; ITEMS];
    var scratch:         u8[>..]    = [];
    let setup_config = log::Logger { minimum: log::Level.Info };
    for i in ITEMS {
        let item = items[i];
        let message = diagnostics::message(item.event, item.duration_ns, item.outcome);
        message_starts[i] = messages.len;
        message_lengths[i] = message.len;
        messages.append(message);
        assert(log::render(setup_config, diagnostics::level(item.event), message, scratch));
        line_starts[i] = lines.len;
        line_lengths[i] = scratch.len;
        lines.append(scratch);
    }
    // Validate all 64 constructed/rendered values independently in the host.
    // These safe appends are setup I/O, outside every timed stage.
    let proof = str(path, ".proof");
    assert(diagnostics::append(proof, messages));
    assert(diagnostics::append(proof, lines));
    // Leave a real rendered line in scratch; disabled calls must preserve it.
    let saved = str(scratch);
    let warmed = phase(config, stage, items, messages, message_starts, message_lengths, lines,
                       line_starts, line_lengths, path, scratch, warmup);
    let start = clock_ns();
    let result = phase(config, stage, items, messages, message_starts, message_lengths, lines,
                       line_starts, line_lengths, path, scratch, count);
    let elapsed = clock_ns() - start;
    if stage == "filtered" { assert(scratch == saved); }
    if stage == "render" || stage == "full" {
        let last = (count - 1) % ITEMS;
        assert(scratch == lines[line_starts[last]..line_starts[last] + line_lengths[last]]);
    }
    var json = str("{\"elapsed_ns\":", elapsed, ",\"minimum\":", minimum);
    field(json, "calls", result.calls);
    field(json, "builders", result.builders);
    field(json, "sinks", result.sinks);
    field(json, "bytes", result.bytes);
    field(json, "checksum", result.checksum);
    field(json, "successful_returns", result.successful_returns);
    field(json, "warmup_calls", warmed.calls);
    field(json, "warmup_builders", warmed.builders);
    field(json, "warmup_sinks", warmed.sinks);
    field(json, "warmup_bytes", warmed.bytes);
    field(json, "warmup_checksum", warmed.checksum);
    field(json, "warmup_successful_returns", warmed.successful_returns);
    json.push('}');
    print(json);
}
