#include <stdint.h>
#include <stdio.h>

#ifndef M
#define M 32
#endif

#ifndef N
#define N 32
#endif

#ifndef K
#define K 32
#endif

#if M <= 0 || N <= 0 || K <= 0
#error "M, N, and K must be positive"
#endif

#if defined(__GNUC__)
#define NOINLINE __attribute__((noinline))
#else
#define NOINLINE
#endif

static int32_t a[M][K];
static int32_t b[K][N];
static int64_t c[M][N];

static int32_t init_a(int i, int k) {
    return (int32_t)(((i * 3 + k * 5 + 1) % 17) - 8);
}

static int32_t init_b(int k, int j) {
    return (int32_t)(((k * 7 + j * 11 + 3) % 19) - 9);
}

static NOINLINE void init_matrices(void) {
    for (int i = 0; i < M; ++i) {
        for (int k = 0; k < K; ++k) {
            a[i][k] = init_a(i, k);
        }
    }

    for (int k = 0; k < K; ++k) {
        for (int j = 0; j < N; ++j) {
            b[k][j] = init_b(k, j);
        }
    }

    for (int i = 0; i < M; ++i) {
        for (int j = 0; j < N; ++j) {
            c[i][j] = 0;
        }
    }
}

static NOINLINE void matmul_inner(void) {
    for (int i = 0; i < M; ++i) {
        for (int j = 0; j < N; ++j) {
            int64_t sum = 0;
            for (int k = 0; k < K; ++k) {
                sum += (int64_t)a[i][k] * b[k][j];
            }
            c[i][j] = sum;
        }
    }
}

static int64_t expected_value(int i, int j) {
    int64_t sum = 0;
    for (int k = 0; k < K; ++k) {
        sum += (int64_t)init_a(i, k) * init_b(k, j);
    }
    return sum;
}

static NOINLINE int verify_and_checksum(int64_t *checksum) {
    int64_t local_checksum = 0;
    for (int i = 0; i < M; ++i) {
        for (int j = 0; j < N; ++j) {
            int64_t expected = expected_value(i, j);
            local_checksum += c[i][j];
            if (c[i][j] != expected) {
                printf(
                    "matmul_inner failed at (%d,%d): got %lld expected %lld\n",
                    i,
                    j,
                    (long long)c[i][j],
                    (long long)expected
                );
                return 1;
            }
        }
    }
    *checksum = local_checksum;
    return 0;
}

int main(void) {
    int64_t checksum = 0;

    init_matrices();
    matmul_inner();

    if (verify_and_checksum(&checksum) != 0) {
        return 1;
    }

    printf(
        "matmul_inner passed M=%d N=%d K=%d checksum=%lld\n",
        M,
        N,
        K,
        (long long)checksum
    );
    return 0;
}
