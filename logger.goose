// SPDX-License-Identifier: Apache-2.0
namespace log;

enum Level { Trace, Debug, Info, Warn, Error, Fatal, Off }
enum Status { Filtered, Written, SinkError }

struct Logger {
    minimum: Level = Level.Info,
    color:   bool  = false,
}

const MAX_MESSAGE_BYTES = 4096;
// Largest label (8), color + reset (9), escaped payload (4 per byte),
// truncation suffix (15), and final newline (1).
const MAX_LINE_BYTES = 8 + 9 + 4 * MAX_MESSAGE_BYTES + 15 + 1;

fn enabled(logger: Logger, level: Level) -> bool {
    if level == Level.Off || logger.minimum == Level.Off { return false; }
    if logger.minimum == Level.Trace { return true; }
    if logger.minimum == Level.Debug { return level != Level.Trace; }
    if logger.minimum == Level.Info { return level != Level.Trace && level != Level.Debug; }
    if logger.minimum == Level.Warn { return level == Level.Warn || level == Level.Error || level == Level.Fatal; }
    if logger.minimum == Level.Error { return level == Level.Error || level == Level.Fatal; }
    level == Level.Fatal
}

fn level_name(level: Level) -> const u8[:] {
    if level == Level.Trace { return "TRACE"; }
    if level == Level.Debug { return "DEBUG"; }
    if level == Level.Info { return "INFO"; }
    if level == Level.Warn { return "WARN"; }
    if level == Level.Error { return "ERROR"; }
    if level == Level.Fatal { return "FATAL"; }
    "OFF"
}

fn name_matches(text: const u8[:], name: const u8[:]) -> bool {
    if text.len != name.len { return false; }
    for i in name.len {
        var c = text[i];
        if c >= 'a' && c <= 'z' { c -= 32; }
        if c != name[i] { return false; }
    }
    true
}

// Exact ASCII names only; reject oversized input before reading its bytes.
fn parse_level(text: const u8[:]) -> Level, bool {
    if text.len > 5 { return Level.Off, false; }
    if name_matches(text, "TRACE") { return Level.Trace, true; }
    if name_matches(text, "DEBUG") { return Level.Debug, true; }
    if name_matches(text, "INFO") { return Level.Info, true; }
    if name_matches(text, "WARN") { return Level.Warn, true; }
    if name_matches(text, "ERROR") { return Level.Error, true; }
    if name_matches(text, "FATAL") { return Level.Fatal, true; }
    if name_matches(text, "OFF") { return Level.Off, true; }
    return Level.Off, false;
}

// Replaces out only when enabled. Input must not borrow from out.
// All non-printable/non-ASCII bytes are escaped, as is backslash itself.
fn render(logger: Logger, level: Level, message: const u8[:], out: u8[>..]&) -> bool {
    if !enabled(logger, level) { return false; }
    out.clear();
    if logger.color {
        if level == Level.Trace { out.append("\x1b[94m"); }
        else if level == Level.Debug { out.append("\x1b[36m"); }
        else if level == Level.Info { out.append("\x1b[32m"); }
        else if level == Level.Warn { out.append("\x1b[33m"); }
        else if level == Level.Error { out.append("\x1b[31m"); }
        else { out.append("\x1b[35m"); }
    }
    out.push('[');
    out.append(level_name(level));
    out.push(']');
    if logger.color { out.append("\x1b[0m"); }
    out.push(' ');
    let hex = "0123456789abcdef";
    let count = if message.len < MAX_MESSAGE_BYTES { message.len } else { MAX_MESSAGE_BYTES };
    for c in message[..count] {
        if c == '\\' { out.append("\\\\"); }
        else if c >= 0x20 && c <= 0x7e { out.push(c); }
        else {
            out.append("\\x");
            out.push(hex[(c >> 4) as i64]);
            out.push(hex[(c & 15) as i64]);
        }
    }
    if message.len > MAX_MESSAGE_BYTES { out.append("... [truncated]"); }
    out.push('\n');
    true
}

// The sink borrows one complete line synchronously and reports success.
// A failed sink may already have written bytes: there is no retry/rollback.
fn emit<F>(logger: Logger, level: Level, message: const u8[:], out: u8[>..]&) -> Status {
    if !render(logger, level, message, out) { return Status.Filtered; }
    let line:    const u8[:] = out;
    let success: bool        = F(line);
    if success { Status.Written } else { Status.SinkError }
}

// Build() is evaluated once only when enabled, before Sink(line). It may
// return owned bytes or a borrowed slice; Goose checks the resulting lifetime.
// Builder work is application code and is outside the formatter's byte cap.
fn emit_lazy<Build, Sink>(logger: Logger, level: Level, out: u8[>..]&) -> Status {
    if !enabled(logger, level) { return Status.Filtered; }
    let message = Build();
    emit(logger, level, message, out, Sink)
}
