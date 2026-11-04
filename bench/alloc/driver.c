// SPDX-License-Identifier: Apache-2.0
// Linux/GNU-ld instrumentation of direct calls from this generated program.
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <unistd.h>

typedef struct {
    uint64_t malloc_calls, calloc_calls, realloc_calls, free_calls;
    uint64_t malloc_bytes, calloc_bytes, realloc_bytes;
    uint64_t mmap_calls, mmap_bytes, mprotect_calls, munmap_calls, madvise_calls;
} counters;
static counters observed;
static int counting;

void *__real_malloc(size_t);
void *__real_calloc(size_t, size_t);
void *__real_realloc(void *, size_t);
void __real_free(void *);
void *__real_mmap(void *, size_t, int, int, int, off_t);
int __real_mprotect(void *, size_t, int);
int __real_munmap(void *, size_t);
int __real_madvise(void *, size_t, int);

void *__wrap_malloc(size_t n) {
    if (counting) { ++observed.malloc_calls; observed.malloc_bytes += n; }
    return __real_malloc(n);
}
void *__wrap_calloc(size_t n, size_t size) {
    if (counting) { ++observed.calloc_calls; observed.calloc_bytes += n * size; }
    return __real_calloc(n, size);
}
void *__wrap_realloc(void *p, size_t n) {
    if (counting) { ++observed.realloc_calls; observed.realloc_bytes += n; }
    return __real_realloc(p, n);
}
void __wrap_free(void *p) {
    if (counting) ++observed.free_calls;
    __real_free(p);
}
void *__wrap_mmap(void *p, size_t n, int protection, int flags, int fd, off_t offset) {
    if (counting) { ++observed.mmap_calls; observed.mmap_bytes += n; }
    return __real_mmap(p, n, protection, flags, fd, offset);
}
int __wrap_mprotect(void *p, size_t n, int protection) {
    if (counting) ++observed.mprotect_calls;
    return __real_mprotect(p, n, protection);
}
int __wrap_munmap(void *p, size_t n) {
    if (counting) ++observed.munmap_calls;
    return __real_munmap(p, n);
}
int __wrap_madvise(void *p, size_t n, int advice) {
    if (counting) ++observed.madvise_calls;
    return __real_madvise(p, n, advice);
}

// Including the generated translation unit exposes its pinned runtime's
// registry for snapshots. No generated source is patched or redistributed.
#include "allocation_probe.c"

static uint8_t expected[28592];
static size_t expected_size;
static uint64_t sink_calls;

static void append(const char *text) {
    size_t n = strlen(text);
    if (n > sizeof expected - expected_size) abort();
    memcpy(expected + expected_size, text, n);
    expected_size += n;
}
static void escaped(size_t count) {
    for (size_t i = 0; i < count; ++i) append("\\xff");
    append("... [truncated]");
}
static void quoted(size_t count) { append("\""); escaped(count); append("\""); }
static void make_expected(int record) {
    expected_size = 0;
    append("\x1b[35m[FATAL]\x1b[0m ");
    if (record) {
        append("timestamp="); quoted(64); append(" ");
        append("target="); quoted(64); append(" ");
        append("file="); quoted(256); append(" line=4294967295 ");
        for (size_t i = 0; i < 8; ++i) {
            quoted(64); append("="); quoted(256); append(" ");
        }
        append("[fields truncated] ");
    }
    escaped(4096); append("\n");
    if (expected_size != (record ? 28592u : 16417u)) abort();
}

uint8_t allocation_sink(sl_u8 line) {
    if (line.len < 0 || (uint64_t)line.len != expected_size ||
            memcmp(line.data, expected, expected_size)) return 0;
    ++sink_calls;
    return 1;
}

typedef struct { uint64_t regions, reserved_bytes, top_bytes; } arena_snapshot;
static arena_snapshot snapshot(void) {
    arena_snapshot out = {0};
    out.regions = (uint64_t)gs_nregions;
    for (long i = 0; i < gs_nregions; ++i) {
        const gs_region *r = &gs_regions[i];
        if (r->stack->top < r->base || r->stack->top > r->base + r->usable) abort();
        out.reserved_bytes += r->size;
        out.top_bytes += (uint64_t)(r->stack->top - r->base);
    }
    return out;
}
static long minor_faults(void) {
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage)) abort();
    return usage.ru_minflt;
}

static void control(void) {
    counting = 1;
    void *p = malloc(31), *q = calloc(2, 17);
    if (!p || !q) abort();
    memset(p, 7, 31);
    p = realloc(p, 67);
    if (!p) abort();
    free(p); free(q);
    const size_t page = (size_t)sysconf(_SC_PAGESIZE);
    void *mapping = mmap(NULL, page, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED || mprotect(mapping, page, PROT_READ) ||
        madvise(mapping, page, MADV_DONTNEED) || munmap(mapping, page)) abort();
    counting = 0;
    if (observed.malloc_calls != 1 || observed.calloc_calls != 1 ||
        observed.realloc_calls != 1 || observed.free_calls != 2 ||
        observed.mmap_calls != 1 || observed.mprotect_calls != 1 ||
        observed.munmap_calls != 1 || observed.madvise_calls != 1) abort();
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    char *end = NULL;
    unsigned long iterations = strtoul(argv[2], &end, 10);
    if (!*argv[2] || *end || !iterations || iterations > 1000000) return 2;
    const char *phase = argv[1];
    int init = !strcmp(phase, "init"), is_control = !strcmp(phase, "control");
    int warm = !strncmp(phase, "warm-", 5);
    int record = strstr(phase, "record") != NULL, filtered = strstr(phase, "filtered") != NULL;
    if (!init && !is_control && strcmp(phase, "cold-plain") && strcmp(phase, "warm-plain") &&
        strcmp(phase, "cold-record") && strcmp(phase, "warm-record") &&
        strcmp(phase, "cold-filtered") && strcmp(phase, "warm-filtered")) return 2;
    uint8_t input[4097];
    memset(input, 0xff, sizeof input);
    const sl_u8 message = {input, sizeof input};
    arena_snapshot before = {0}, after = {0};
    uint64_t measured_calls = 0;
    long faults_before = minor_faults(), faults_after;
    if (is_control) control();
    else if (init) {
        counting = 1;
        goose_init(argc, argv);
        counting = 0;
        after = snapshot();
    } else {
        goose_init(argc, argv);
        make_expected(record);
        if (warm && allocation_emit(record ? 1 : 0, message) != 1) abort();
        sink_calls = 0;
        before = snapshot();
        faults_before = minor_faults();
        counting = 1;
        measured_calls = warm ? iterations : 1;
        for (uint64_t i = 0; i < measured_calls; ++i)
            if (allocation_emit(filtered ? 2 : record ? 1 : 0, message) != (filtered ? 0 : 1)) abort();
        counting = 0;
        faults_after = minor_faults();
        after = snapshot();
        int64_t length = -1;
        const uint8_t *output = allocation_output(&length);
        const size_t expected_length = filtered && !warm ? 0 : expected_size;
        if (length < 0 || (uint64_t)length != expected_length ||
            (expected_length && memcmp(output, expected, expected_length)) ||
            sink_calls != (filtered ? 0 : measured_calls)) abort();
        goto report;
    }
    faults_after = minor_faults();
report:
    printf("{\"phase\":\"%s\",\"measured_calls\":%llu,\"sink_calls\":%llu,"
           "\"malloc_calls\":%llu,\"calloc_calls\":%llu,\"realloc_calls\":%llu,\"free_calls\":%llu,"
           "\"malloc_requested_bytes\":%llu,\"calloc_requested_bytes\":%llu,\"realloc_requested_bytes\":%llu,"
           "\"mmap_calls\":%llu,\"mmap_requested_bytes\":%llu,\"mprotect_calls\":%llu,\"munmap_calls\":%llu,\"madvise_calls\":%llu,"
           "\"regions_before\":%llu,\"regions_after\":%llu,\"reserved_bytes_before\":%llu,\"reserved_bytes_after\":%llu,"
           "\"arena_top_bytes_before\":%llu,\"arena_top_bytes_after\":%llu,\"minor_faults\":%ld}\n",
           phase, (unsigned long long)measured_calls, (unsigned long long)sink_calls,
           (unsigned long long)observed.malloc_calls, (unsigned long long)observed.calloc_calls,
           (unsigned long long)observed.realloc_calls, (unsigned long long)observed.free_calls,
           (unsigned long long)observed.malloc_bytes, (unsigned long long)observed.calloc_bytes,
           (unsigned long long)observed.realloc_bytes, (unsigned long long)observed.mmap_calls,
           (unsigned long long)observed.mmap_bytes, (unsigned long long)observed.mprotect_calls,
           (unsigned long long)observed.munmap_calls, (unsigned long long)observed.madvise_calls,
           (unsigned long long)before.regions, (unsigned long long)after.regions,
           (unsigned long long)before.reserved_bytes, (unsigned long long)after.reserved_bytes,
           (unsigned long long)before.top_bytes, (unsigned long long)after.top_bytes,
           faults_after - faults_before);
    if (!is_control) goose_exit();
    return 0;
}
