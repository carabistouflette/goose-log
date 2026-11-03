// SPDX-License-Identifier: Apache-2.0
namespace log;

enum Level { Debug, Info, Warn, Error, Off }
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
    if logger.minimum == Level.Debug { return true; }
    if logger.minimum == Level.Info { return level != Level.Debug; }
    if logger.minimum == Level.Warn { return level == Level.Warn || level == Level.Error; }
    level == Level.Error
}

// Replaces out only when enabled. Input must not borrow from out.
// All non-printable/non-ASCII bytes are escaped, as is backslash itself.
fn render(logger: Logger, level: Level, message: const u8[:], out: u8[>..]&) -> bool {
    if !enabled(logger, level) { return false; }
    out.clear();
    if logger.color {
        if level == Level.Debug { out.append("\x1b[36m"); }
        else if level == Level.Info { out.append("\x1b[32m"); }
        else if level == Level.Warn { out.append("\x1b[33m"); }
        else { out.append("\x1b[31m"); }
    }
    if level == Level.Debug { out.append("[DEBUG]"); }
    else if level == Level.Info { out.append("[INFO]"); }
    else if level == Level.Warn { out.append("[WARN]"); }
    else { out.append("[ERROR]"); }
    if logger.color { out.append("\x1b[0m"); }
    out.push(' ');
    let hex = "0123456789abcdef";
    let count = if message.len < MAX_MESSAGE_BYTES { message.len } else { MAX_MESSAGE_BYTES };
    for i in count {
        let c = message[i];
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
