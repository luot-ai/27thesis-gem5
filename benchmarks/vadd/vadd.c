#include <stdint.h>
#include <stdio.h>

#include "../common/gem5_roi.h"

#ifndef N
#define N 1024
#endif

#ifdef USE_STATIC_VADD_DATA
#include "../common/vadd_static_data.h"
#else
static int32_t vadd_a[N];
static int32_t vadd_b[N];
static int32_t vadd_y[N];
#endif

int main(void) {
#ifndef USE_STATIC_VADD_DATA
    for (int i = 0; i < N; ++i) {
        vadd_a[i] = i;
        vadd_b[i] = 2 * i + 1;
        vadd_y[i] = 0;
    }
#endif

    gem5_roi_begin();
    for (int i = 0; i < N; ++i) {
        vadd_y[i] = vadd_a[i] + vadd_b[i];
    }
    gem5_roi_end();

    for (int i = 0; i < N; ++i) {
        int32_t expected = 3 * i + 1;
        if (vadd_y[i] != expected) {
            printf("vadd failed at %d: got %d expected %d\n",
                   i, vadd_y[i], expected);
            return 1;
        }
    }

    printf("vadd passed N=%d\n", N);
    return 0;
}
