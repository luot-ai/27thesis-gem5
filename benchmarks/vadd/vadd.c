#include <stdint.h>
#include <stdio.h>

#ifndef N
#define N 1024
#endif

static int32_t a[N];
static int32_t b[N];
static int32_t y[N];

int main(void) {
    for (int i = 0; i < N; ++i) {
        a[i] = i;
        b[i] = 2 * i + 1;
        y[i] = 0;
    }

    for (int i = 0; i < N; ++i) {
        y[i] = a[i] + b[i];
    }

    for (int i = 0; i < N; ++i) {
        int32_t expected = 3 * i + 1;
        if (y[i] != expected) {
            printf("vadd failed at %d: got %d expected %d\n", i, y[i], expected);
            return 1;
        }
    }

    printf("vadd passed N=%d\n", N);
    return 0;
}

