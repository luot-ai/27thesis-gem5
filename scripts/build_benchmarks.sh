#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build"

RISCV_GCC="${RISCV_GCC:-}"
OPT="${OPT:--O3}"
N="${N:-1024}"

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

"${CC}" "${OPT}" -static -DN="${N}" \
    "${ROOT_DIR}/benchmarks/vadd/vadd.c" \
    -o "${BUILD_DIR}/vadd_N${N}.riscv"

echo "built ${BUILD_DIR}/vadd_N${N}.riscv"

