#ifndef BENCHMARKS_COMMON_GEM5_ROI_H
#define BENCHMARKS_COMMON_GEM5_ROI_H

#include <stdint.h>

static inline void gem5_roi_begin(void)
{
#if defined(__riscv)
    register uint64_t a0 asm("a0") = 0;
    register uint64_t a1 asm("a1") = 0;
    __asm__ volatile(".long 0x8000007b"
                     : "+r"(a0), "+r"(a1)
                     :
                     : "memory");
#endif
}

static inline void gem5_roi_end(void)
{
#if defined(__riscv)
    register uint64_t a0 asm("a0") = 0;
    register uint64_t a1 asm("a1") = 0;
    __asm__ volatile(".long 0x8400007b"
                     : "+r"(a0), "+r"(a1)
                     :
                     : "memory");
#endif
}

#endif
