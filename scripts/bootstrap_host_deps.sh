#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "error: this script installs Ubuntu packages and must be run with sudo:" >&2
    echo "  sudo ./scripts/bootstrap_host_deps.sh" >&2
    exit 1
fi

apt update
apt install -y \
    build-essential \
    git \
    pre-commit \
    m4 \
    scons \
    zlib1g \
    zlib1g-dev \
    libprotobuf-dev \
    protobuf-compiler \
    libprotoc-dev \
    libgoogle-perftools-dev \
    python3-dev \
    python3-venv \
    python3-pip \
    python3-pydot \
    python3-tk \
    python-is-python3 \
    libboost-all-dev \
    libhdf5-serial-dev \
    libcapstone-dev \
    libpng-dev \
    libelf-dev \
    pkg-config \
    wget \
    cmake \
    doxygen \
    clang-format \
    mypy \
    gcc-riscv64-linux-gnu \
    g++-riscv64-linux-gnu

echo "host dependencies installed"
