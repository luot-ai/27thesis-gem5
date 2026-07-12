#include <stdint.h>
#include <stdio.h>

#include "../common/gem5_roi.h"
#include "../common/stream_instr_v06.h"

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

static uintptr_t stream_addr(const void *ptr) {
    return (uintptr_t)ptr;
}

static void configure_streams(void) {
    for (int fifo = 0; fifo < 3; ++fifo) {
        cfg_iter(1, N, fifo);
        cfg_reuse(1, fifo);
        cfg_i_limit(N, fifo);
        cfg_i_repeat(1, fifo);
        cfg_stride(4, fifo);
        cfg_tilestride(128, fifo);
    }

    cfg_axi_load(stream_addr(vadd_a), 0);
    cfg_axi_load(stream_addr(vadd_b), 1);
    cfg_store(stream_addr(vadd_y), 2);
}

int main(void) {
#ifndef USE_STATIC_VADD_DATA
    for (int i = 0; i < N; ++i) {
        vadd_a[i] = i;
        vadd_b[i] = 2 * i + 1;
        vadd_y[i] = 0;
    }
#endif

    gem5_roi_begin();
    configure_streams();

    for (int i = 0; i < N; ++i) {
        sss_add(0, 1, 2);
    }
    gem5_roi_end();

    /*
     * The first functional model may complete synchronously. A later timing
     * model may need an explicit wait/drain before CPU-side verification.
     */
    for (int i = 0; i < N; ++i) {
        int32_t expected = 3 * i + 1;
        if (vadd_y[i] != expected) {
            printf("stream_vadd failed at %d: got %d expected %d\n",
                   i, vadd_y[i], expected);
            return 1;
        }
    }

    printf("stream_vadd passed N=%d\n", N);
    return 0;
}
