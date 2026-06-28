# gem5 RISC-V O3 Baseline

This project is building a reproducible gem5 RISC-V O3 baseline for thesis experiments on streaming memory-access optimization.

本阶段只是建立 baseline，不代表 stream engine 已经完成。

## Current Status

- Minimal benchmark source: `benchmarks/vadd/vadd.c`
- Default problem size: `N = 1024`
- Build script: `scripts/build_benchmarks.sh`
- Built benchmark: `build/vadd_N1024.riscv`
- Environment notes: `notes/env_check.md`
- BOOM-like O3 config: `gem5_configs/riscv_o3_baseline.py`
- gem5 run wrapper: `scripts/run_gem5.py`
- gem5 O3 runs: blocked until `tools/gem5/build/RISCV/gem5.opt` is built
- stream engine: not implemented in this stage

## Project Layout

```text
benchmarks/
  vadd/vadd.c                 Minimal vector-add benchmark.
build/
  vadd_N1024.riscv            Static RISC-V benchmark binary.
gem5_configs/
  boom_like_profiles.py       BOOM-like O3 profile values.
  riscv_o3_baseline.py        gem5 SE-mode O3 system config.
notes/
  env_check.md                Environment and setup status.
  boom_config_survey.md       Public BOOM configuration survey.
scripts/
  bootstrap_host_deps.sh      Ubuntu host dependency installer.
  build_benchmarks.sh         RISC-V benchmark build script.
  monitor_gem5_build.sh       One-shot gem5 build progress checker.
  run_gem5.py                 gem5 run wrapper.
results/
  <bench-name>/<config>/      Per-run output directory.
```

## Step Progress

| Step | Status | Notes |
| --- | --- | --- |
| 1. Environment check | Done | See `notes/env_check.md`. |
| 2. Minimal vadd benchmark | Done | Source in `benchmarks/vadd/vadd.c`. |
| 3. RISC-V build script | Done | Produces `build/vadd_N1024.riscv`. |
| 4. gem5 run wrapper | Done | Ready, but real run waits for `gem5.opt`. |
| 5. BOOM public config survey | Done | See `notes/boom_config_survey.md`. |
| 6. BOOM-like O3 config | Done | Medium-like O3 profile implemented. |
| 7. Stride-prefetch baseline | Prepared | Entry exists as `o3_stridepf`; must be verified after gem5 builds. |
| 8. Stats parser | Not started | Good next scripting task after docs. |

## RISC-V Toolchain

Install a RISC-V Linux GNU compiler, or point `RISCV_GCC` at an existing compiler.

On Ubuntu:

```bash
sudo ./scripts/bootstrap_host_deps.sh
```

Build the current benchmark:

```bash
./scripts/build_benchmarks.sh
```

Useful overrides:

```bash
RISCV_GCC=riscv64-linux-gnu-gcc OPT=-O3 N=1024 ./scripts/build_benchmarks.sh
```

## gem5

gem5 source has been cloned to `tools/gem5`. No local `gem5.opt` has been built yet.

Build the RISCV target:

```bash
cd tools/gem5
scons build/RISCV/gem5.opt -j2
```

`-j2` is a conservative default for the current VM. If memory pressure is low, `-j4` is also reasonable.

The run wrapper accepts `--gem5-bin /path/to/gem5.opt`, so the project does not depend on a hard-coded absolute path.

To check whether the build has finished without continuously monitoring it:

```bash
test -x tools/gem5/build/RISCV/gem5.opt && echo "gem5.opt ready" || echo "still building"
```

For a fuller one-shot progress check:

```bash
./scripts/monitor_gem5_build.sh
```

## BOOM-like O3 Config

The current BOOM-like profile is defined in:

```text
gem5_configs/boom_like_profiles.py
gem5_configs/riscv_o3_baseline.py
```

After `gem5.opt` is available, the medium BOOM-like no-prefetch baseline can be run with:

```bash
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/vadd_N1024.riscv \
  --bench-name vadd_N1024 \
  --config o3_nopf
```

The wrapper writes `config.json`, `simout`, and `simerr` under
`results/<bench-name>/<config>/`. If gem5 exits successfully, `stats.txt` and
the usual gem5 output files will also be in the same directory.

To check the command layout before `gem5.opt` exists:

```bash
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/vadd_N1024.riscv \
  --bench-name vadd_N1024 \
  --config o3_nopf \
  --dry-run
```

The profile is BOOM-like only: it maps public BOOM-style widths and queue sizes to gem5 O3 parameters, but it is not a cycle-accurate BOOM RTL reproduction.

## Result Directory Contract

Each experiment should use one result directory:

```text
results/
  vadd_N1024/
    o3_nopf/
      config.json
      simout
      simerr
      stats.txt
    o3_stridepf/
      config.json
      simout
      simerr
      stats.txt
```

`config.json` records the command, benchmark, gem5 config, clock/cache
settings, and whether stride prefetching was requested. This makes failed runs
useful too, because the exact attempted command remains visible.

## Next Steps

1. Finish building `tools/gem5/build/RISCV/gem5.opt`.
2. Run `vadd_N1024` with `--config o3_nopf`.
3. Inspect `simout`, `simerr`, and `stats.txt`.
4. Verify whether `--config o3_stridepf` works with this gem5 version.
5. Add `scripts/parse_stats.py` to produce a compact result table.

## Baseline Scope

The immediate goal is to run `vadd_N1024` on gem5 O3 with no prefetching. After that, the project will verify the stride-prefetch baseline and add stats parsing.

This is a BOOM-like O3 baseline inspired by public BOOM configurations. It is not a cycle-accurate reproduction of BOOM.

## Group Meeting Wording

本阶段目标不是完成 stream engine 建模，而是先建立可信的 O3 CPU baseline。

后续 stream engine 的收益不仅要和普通 O3 CPU 比，也要和 gem5 中的 stride prefetcher 比。

stride prefetcher 主要解决数据提前进入 cache 的问题，但不会减少动态 load/store 指令，也不会减少地址生成、rename、issue、commit 等流水线压力。

stream engine 后续要验证的是：能否把规则访存从主指令流中解耦，由硬件维护索引更新、buffer 状态和访存请求，从而降低边缘端 signal / AI 小 kernel 中访存相关指令对计算流水的干扰。
