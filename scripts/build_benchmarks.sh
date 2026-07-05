#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build"

RISCV_GCC="${RISCV_GCC:-}"
OPT="${OPT:--O3}"
N="${N:-1024}"
MATMUL_M="${MATMUL_M:-32}"
MATMUL_N="${MATMUL_N:-32}"
MATMUL_K="${MATMUL_K:-32}"
BENCHMARKS="${BENCHMARKS:-${BENCHMARK:-vadd matmul_inner}}"

find_riscv_gcc() {
    if [[ -n "${RISCV_GCC}" ]]; then
        command -v "${RISCV_GCC}" >/dev/null 2>&1 || {
            echo "error: RISCV_GCC='${RISCV_GCC}' was not found or is not executable" >&2
            exit 1
        }
        echo "${RISCV_GCC}"
        return
    fi

    for cc in riscv64-unknown-linux-gnu-gcc riscv64-linux-gnu-gcc; do
        if command -v "${cc}" >/dev/null 2>&1; then
            echo "${cc}"
            return
        fi
    done

    cat >&2 <<'EOF'
error: no RISC-V Linux GCC found.

Install one, or pass RISCV_GCC explicitly, for example:
  sudo apt install gcc-riscv64-linux-gnu
  RISCV_GCC=riscv64-linux-gnu-gcc ./scripts/build_benchmarks.sh
EOF
    exit 1
}

CC="$(find_riscv_gcc)"
mkdir -p "${BUILD_DIR}"

build_vadd() {
    "${CC}" "${OPT}" -static -DN="${N}" \
        "${ROOT_DIR}/benchmarks/vadd/vadd.c" \
        -o "${BUILD_DIR}/vadd_N${N}.riscv"

    echo "built ${BUILD_DIR}/vadd_N${N}.riscv"
}

build_matmul_inner() {
    "${CC}" "${OPT}" -static \
        -DM="${MATMUL_M}" \
        -DN="${MATMUL_N}" \
        -DK="${MATMUL_K}" \
        "${ROOT_DIR}/benchmarks/matmul_inner/matmul_inner.c" \
        -o "${BUILD_DIR}/matmul_inner_M${MATMUL_M}_N${MATMUL_N}_K${MATMUL_K}.riscv"

    echo "built ${BUILD_DIR}/matmul_inner_M${MATMUL_M}_N${MATMUL_N}_K${MATMUL_K}.riscv"
}

build_stream_vadd() {
    "${CC}" "${OPT}" -static -DN="${N}" \
        "${ROOT_DIR}/benchmarks/stream_vadd/stream_vadd.c" \
        -o "${BUILD_DIR}/stream_vadd_N${N}.riscv"

    echo "built ${BUILD_DIR}/stream_vadd_N${N}.riscv"
}

if [[ "${BENCHMARKS}" == "all" ]]; then
    BENCHMARKS="vadd matmul_inner stream_vadd"
fi

for benchmark in ${BENCHMARKS//,/ }; do
    case "${benchmark}" in
        vadd)
            build_vadd
            ;;
        matmul_inner|matmul|gemm)
            build_matmul_inner
            ;;
        stream_vadd|stream)
            build_stream_vadd
            ;;
        *)
            echo "error: unknown benchmark '${benchmark}'" >&2
            echo "available benchmarks: vadd, matmul_inner, stream_vadd" >&2
            exit 1
            ;;
    esac
done
