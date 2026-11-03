// SPDX-License-Identifier: Apache-2.0
// POSIX-only native test adapter. Never included by the logging library.
#include <stdint.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

static uintptr_t guarded_start(sl_u8 data, int64_t readable) {
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0 || readable < 0 || readable > data.len) abort();
    uintptr_t start = (uintptr_t)data.data + (uintptr_t)readable;
    uintptr_t remainder = start % (uintptr_t)page;
    if (remainder) start += (uintptr_t)page - remainder;
    return start;
}

static void guarded_protect(sl_u8 data, int64_t readable, int protection) {
    long page = sysconf(_SC_PAGESIZE);
    uintptr_t start = guarded_start(data, readable);
    uintptr_t end = (uintptr_t)data.data + (uintptr_t)data.len;
    end -= end % (uintptr_t)page;
    // Protect only whole pages inside the backing array, avoiding neighbors.
    if (start >= end || mprotect((void *)start, end - start, protection)) abort();
}

static int64_t guarded_offset(sl_u8 data, int64_t readable) {
    uintptr_t start = guarded_start(data, readable);
    guarded_protect(data, readable, PROT_NONE);
    return (int64_t)(start - (uintptr_t)data.data - (uintptr_t)readable);
}

static void guarded_restore(sl_u8 data, int64_t readable) {
    guarded_protect(data, readable, PROT_READ | PROT_WRITE);
}

static uint8_t guarded_touch(sl_u8 data) {
    // A negative control must issue a real read, even under optimization.
    volatile const uint8_t *address = data.data;
    return *address;
}
