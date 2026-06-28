#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-${ROOT_DIR}/tools/gem5/build/RISCV}"
GEM5_OPT="${GEM5_OPT:-${BUILD_DIR}/gem5.opt}"
INTERVAL="${INTERVAL:-30}"
prev_bytes=""
prev_o_count=""
prev_pyo_count=""
prev_cc_count=""

while true; do
    now="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$now]"

    if [[ -x "${GEM5_OPT}" ]]; then
        echo "status: DONE"
        ls -lh "${GEM5_OPT}"
        echo
        "${GEM5_OPT}" --version 2>&1 | head -5 || true
        exit 0
    fi

    echo "status: building or not finished"

    if [[ -d "${BUILD_DIR}" ]]; then
        human_size="$(du -sh "${BUILD_DIR}" 2>/dev/null | awk '{print $1}')"
        bytes="$(du -sb "${BUILD_DIR}" 2>/dev/null | awk '{print $1}')"
        o_count="$(find "${BUILD_DIR}" -name '*.o' 2>/dev/null | wc -l)"
        pyo_count="$(find "${BUILD_DIR}" -name '*.pyo' 2>/dev/null | wc -l)"
        cc_count="$(find "${BUILD_DIR}" -name '*.cc' 2>/dev/null | wc -l)"

        echo "build-dir: ${human_size} (${bytes} bytes)"
        echo "object-files: ${o_count}"
        echo "pyo-files: ${pyo_count}"
        echo "generated-cc-files: ${cc_count}"

        if [[ -n "${prev_bytes}" ]]; then
            echo "delta-since-last-check: bytes=$((bytes - prev_bytes)), o=$((o_count - prev_o_count)), pyo=$((pyo_count - prev_pyo_count)), cc=$((cc_count - prev_cc_count))"
        fi

        prev_bytes="${bytes}"
        prev_o_count="${o_count}"
        prev_pyo_count="${pyo_count}"
        prev_cc_count="${cc_count}"

        echo "recent-files:"
        find "${BUILD_DIR}" -type f -printf '%T@ %p\n' 2>/dev/null \
            | sort -nr \
            | head -8 \
            | sed "s#^[0-9.]* ${BUILD_DIR}/#  #"
    else
        echo "build-dir: missing (${BUILD_DIR})"
    fi

    scons_lines="$(ps -eo pid,etime,pcpu,pmem,cmd | grep -E 'scons|cc1plus|g\\+\\+' | grep -v grep || true)"
    if [[ -n "${scons_lines}" ]]; then
        echo "processes:"
        echo "${scons_lines}" | head -12
    else
        echo "processes: no scons/g++/cc1plus process found"
        echo "hint: if gem5.opt is still missing, restart with:"
        echo "  cd ${ROOT_DIR}/tools/gem5 && scons build/RISCV/gem5.opt -j4"
    fi

    echo "memory:"
    free -h | sed -n '1,3p'
    echo

    sleep "${INTERVAL}"
done
