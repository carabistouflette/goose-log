// SPDX-License-Identifier: Apache-2.0
// Same runtime fixture, memory-sink copy, timing loop, and checksum for all paths.
#define SPDLOG_LEVEL_NAMES { spdlog::string_view_t("TRACE", 5), spdlog::string_view_t("DEBUG", 5), \
    spdlog::string_view_t("INFO", 4), spdlog::string_view_t("WARN", 4), spdlog::string_view_t("ERROR", 5), \
    spdlog::string_view_t("FATAL", 5), spdlog::string_view_t("OFF", 3) }
#include <spdlog/spdlog.h>
#include <spdlog/sinks/base_sink.h>
#include <spdlog/details/null_mutex.h>
#include <algorithm>
#include <chrono>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
extern "C" {
#include "goose_adapter.h"
#include "log.h"
}

static std::vector<uint8_t> last;
static uint64_t checksum = 0, calls = 0, iteration = 0;
static bool measuring = false;

static void capture(const uint8_t *data, size_t size) {
    if (size == 0 || size > 16417) std::abort();
    last.assign(data, data + size);
    ++calls;
    if (measuring) checksum += size + data[iteration % size];
}

extern "C" uint8_t comparison_sink(sl_u8 line) {
    capture(line.data, static_cast<size_t>(line.len));
    return 1;
}

static void logc_sink(log_Event *event) {
    // No untrusted format strings: driver supplies only the fixed "%.*s".
    static char buffer[16417];
    const int prefix = std::snprintf(buffer, sizeof(buffer), "[%s] ", log_level_string(event->level));
    if (prefix < 0 || static_cast<size_t>(prefix) >= sizeof(buffer)) std::abort();
    const int body = std::vsnprintf(buffer + prefix, sizeof(buffer) - prefix, event->fmt, event->ap);
    if (body < 0 || static_cast<size_t>(prefix + body + 1) >= sizeof(buffer)) std::abort();
    buffer[prefix + body] = '\n';
    capture(reinterpret_cast<const uint8_t *>(buffer), prefix + body + 1);
}

class MemorySink final : public spdlog::sinks::base_sink<spdlog::details::null_mutex> {
    spdlog::memory_buf_t formatted_;
    void sink_it_(const spdlog::details::log_msg &message) override {
        formatted_.clear();
        formatter_->format(message, formatted_);
        capture(reinterpret_cast<const uint8_t *>(formatted_.data()), formatted_.size());
    }
    void flush_() override {}
};

struct Context {
    sl_u8 message;
    spdlog::logger *logger;
    spdlog::level::level_enum level;
    decltype(&comparison_macho_record) record_formatter;
};
using Emit = void (*)(const Context &);
static void emit_goose(const Context &context) {
    comparison_goose_log(static_cast<int32_t>(context.level), context.message);
}
static void emit_logc(const Context &context) {
    log_log(context.level, "fixture", 1, "%.*s", static_cast<int>(context.message.len),
            reinterpret_cast<const char *>(context.message.data));
}
static void emit_spdlog(const Context &context) {
    context.logger->log(spdlog::source_loc{}, context.level,
        spdlog::string_view_t(reinterpret_cast<const char *>(context.message.data), context.message.len));
}
static void emit_spdlog_time(const Context &context) {
    context.logger->log(spdlog::log_clock::time_point{}, spdlog::source_loc{}, context.level,
        spdlog::string_view_t(reinterpret_cast<const char *>(context.message.data), context.message.len));
}
static void emit_record(const Context &context) {
    int64_t size = 0;
    const auto *result = context.record_formatter(context.message, &size);
    capture(result, static_cast<size_t>(size));
}

static uint64_t number(const char *text, uint64_t maximum) {
    if (!*text || *text == '-') throw std::runtime_error("invalid integer");
    char *end = nullptr;
    errno = 0;
    const auto value = std::strtoull(text, &end, 10);
    if (errno || *end || value > maximum) throw std::runtime_error("integer out of range");
    return value;
}

int main(int argc, char **argv) try {
    if (argc != 6) throw std::runtime_error("usage: driver ADAPTER FIXTURE ITERATIONS MINIMUM LEVEL");
    const std::string adapter = argv[1];
    const bool record_profile = adapter == "macho-record" || adapter == "goose-record+policy";
    if (adapter != "goose-log" && adapter != "log.c" && adapter != "spdlog" && adapter != "spdlog-supplied-time" && !record_profile)
        throw std::runtime_error("unknown adapter");
    const auto count = number(argv[3], 10000000);
    const auto minimum = number(argv[4], 6);
    const auto level = number(argv[5], 5);
    if (!count) throw std::runtime_error("iterations must be positive");
    std::ifstream input(argv[2], std::ios::binary);
    if (!input) throw std::runtime_error("cannot open fixture");
    const std::string message((std::istreambuf_iterator<char>(input)), {});
    if (message.size() > 4096 || std::any_of(message.begin(), message.end(), [](unsigned char c) {
        return c < 32 || c > 126 || c == '\\';
    })) throw std::runtime_error("shared profile requires printable ASCII except backslash, <=4096 bytes");
    const bool accepted = minimum < 6 && level >= minimum;
    const std::string names[] = {"TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"};
    std::string expected = "[" + names[level] + "] " + message + "\n";
    if (record_profile) {
        if (level != 2 || !accepted) throw std::runtime_error("record profile requires enabled Info");
        std::string clean = message;
        if (message == "password=not-a-real-secret") clean = "password: ********";
        else if (message != "request completed status=200 bytes=1234")
            throw std::runtime_error("unknown record-policy fixture; provide an independently reviewed oracle");
        if (adapter == "macho-record")
            expected = "[2023-11-14 22:13:20.000000000 UTC] [INFO] [app.goose:42] [" + clean + "]\n";
        else expected = "[INFO] timestamp=\"2023-11-14 22:13:20.000000000 UTC\" file=\"app.goose\" line=42 " + clean + "\n";
    }
    auto memory = std::make_shared<MemorySink>();
    spdlog::logger cpp_logger("bench", memory);
    cpp_logger.set_level(static_cast<spdlog::level::level_enum>(minimum));
    cpp_logger.set_formatter(std::make_unique<spdlog::pattern_formatter>(
        "[%l] %v", spdlog::pattern_time_type::utc, "\n"));
    if (adapter == "goose-log" || record_profile) { goose_init(argc, argv); comparison_set_minimum(minimum); }
    if (adapter == "log.c") {
        log_set_quiet(true);
        if (log_add_callback(logc_sink, nullptr, minimum) != 0) throw std::runtime_error("log.c callback setup");
    }
    const Context context = {{reinterpret_cast<uint8_t *>(const_cast<char *>(message.data())),
        static_cast<int64_t>(message.size())}, &cpp_logger,
        static_cast<spdlog::level::level_enum>(level),
        adapter == "macho-record" ? comparison_macho_record : comparison_goose_record};
    const Emit emit = record_profile ? emit_record : adapter == "goose-log" ? emit_goose
        : adapter == "log.c" ? emit_logc : adapter == "spdlog-supplied-time" ? emit_spdlog_time : emit_spdlog;
    emit(context);
    if (calls != (accepted ? 1u : 0u) || (accepted && std::string(last.begin(), last.end()) != expected))
        throw std::runtime_error("adapter output/callback count mismatch");
    for (size_t i = 0; i < 1000; ++i) emit(context);
    calls = checksum = 0;
    measuring = true;
    const auto start = std::chrono::steady_clock::now();
    for (iteration = 0; iteration < count; ++iteration) emit(context);
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
    if (calls != (accepted ? count : 0)) throw std::runtime_error("timed callback count mismatch");
    if (accepted && std::string(last.begin(), last.end()) != expected)
        throw std::runtime_error("final output mismatch");
    uint64_t expected_checksum = 0;
    if (accepted) for (uint64_t i = 0; i < count; ++i)
        expected_checksum += expected.size() + static_cast<unsigned char>(expected[i % expected.size()]);
    if (checksum != expected_checksum) throw std::runtime_error("timed checksum mismatch");
    if (adapter == "goose-log" || record_profile) goose_exit();
    std::printf("{\"elapsed_ns\":%lld,\"calls\":%llu,\"checksum\":%llu,\"iterations\":%llu}\n",
        static_cast<long long>(elapsed), static_cast<unsigned long long>(calls),
        static_cast<unsigned long long>(checksum), static_cast<unsigned long long>(count));
} catch (const std::exception &error) {
    std::fprintf(stderr, "%s\n", error.what());
    return 1;
}
