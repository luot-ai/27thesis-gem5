#ifndef BENCHMARKS_COMMON_VADD_STATIC_DATA_H
#define BENCHMARKS_COMMON_VADD_STATIC_DATA_H

#include <stdint.h>

#ifndef N
#error "N must be defined before including vadd_static_data.h"
#endif

extern int32_t vadd_a[N];
extern int32_t vadd_b[N];
extern int32_t vadd_y[N];

#endif
