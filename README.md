# gem5 RISC-V O3 Baseline

本仓库用于搭建一个可复现的 gem5 RISC-V O3 baseline，服务于毕业论文中“面向边缘端信号与智能处理的流式访存优化研究”的性能对比。

当前阶段的目标是建立可信 CPU baseline，不代表 stream engine 已经实现。

## 当前状态

- 最小 benchmark：`benchmarks/vadd/vadd.c`
- 默认 sanity-check 规模：`N = 1024`
- 已补充规模：`N = 16384`
- RISC-V binary：`build/vadd_N1024.riscv`、`build/vadd_N16384.riscv`
- gem5 binary：`tools/gem5/build/RISCV/gem5.opt`
- BOOM-like O3 配置：`gem5_configs/riscv_o3_baseline.py`
- BOOM-like profile：`gem5_configs/boom_like_profiles.py`
- gem5 运行包装脚本：`scripts/run_gem5.py`
- stats 解析脚本：`scripts/parse_stats.py`
- 已完成结果：`vadd_N1024` 和 `vadd_N16384` 的 `o3_nopf` / `o3_stridepf`
- 汇总表格：`results/summary.csv`

## 项目结构

```text
benchmarks/
  vadd/vadd.c                 最小 vector-add benchmark
build/
  vadd_N*.riscv               静态链接 RISC-V benchmark binary
gem5_configs/
  boom_like_profiles.py       BOOM-like O3 profile 参数
  riscv_o3_baseline.py        gem5 SE-mode O3 system config
notes/
  env_check.md                环境与安装状态记录
  boom_config_survey.md       BOOM 公开配置调研，英文版
  boom_survey_cn.md           BOOM 公开配置调研，中文版
  boom_detailed_config_survey_cn.md
                              BOOM 细粒度配置调研：FU/cache/BPD
  boom_like_config_verification.md
                              BOOM-like O3 参数验证记录
  vadd_baseline_results.md    当前 vadd baseline 结果说明
scripts/
  bootstrap_host_deps.sh      Ubuntu host 依赖安装脚本
  build_benchmarks.sh         RISC-V benchmark 编译脚本
  monitor_gem5_build.sh       gem5 构建进度一次性检查脚本
  parse_stats.py              gem5 stats-to-CSV 解析脚本
  run_gem5.py                 gem5 运行包装脚本
results/
  vadd_N1024/o3_nopf/         no-prefetch O3 结果
  vadd_N1024/o3_stridepf/     stride-prefetch O3 结果
  vadd_N16384/o3_nopf/        更大规模 no-prefetch O3 结果
  vadd_N16384/o3_stridepf/    更大规模 stride-prefetch O3 结果
  summary.csv                 stats 汇总表
```

## Step 进度

| Step | 状态 | 说明 |
| --- | --- | --- |
| 1. 环境检查 | 已完成 | 见 `notes/env_check.md` |
| 2. 最小 vadd benchmark | 已完成 | 源码在 `benchmarks/vadd/vadd.c` |
| 3. RISC-V 编译脚本 | 已完成 | 生成 `build/vadd_N1024.riscv`、`build/vadd_N16384.riscv` |
| 4. gem5 O3 no-prefetch run | 已完成 | `vadd_N1024`、`vadd_N16384` 已跑通 |
| 5. BOOM 公开配置调研 | 已完成 | 见 `notes/boom_config_survey.md` 和 `notes/boom_survey_cn.md` |
| 6. BOOM-like O3 配置 | 已完成 | Medium-like O3 profile 已实现并验证 |
| 7. stride-prefetch baseline | 已完成 | `vadd_N1024`、`vadd_N16384` 已跑通 |
| 8. stats 整理脚本 | 已完成 | `scripts/parse_stats.py` 生成 `results/summary.csv` |

## 环境准备

安装 host 依赖和 RISC-V 工具链：

```bash
sudo ./scripts/bootstrap_host_deps.sh
```

重新编译当前 benchmark：

```bash
./scripts/build_benchmarks.sh
```

可覆盖编译器、优化等级和问题规模：

```bash
RISCV_GCC=riscv64-linux-gnu-gcc OPT=-O3 N=1024 ./scripts/build_benchmarks.sh
```

## gem5 构建

本地 gem5 源码位于 `tools/gem5`。RISCV target 已经构建到：

```text
tools/gem5/build/RISCV/gem5.opt
```

如需重新构建：

```bash
cd tools/gem5
scons build/RISCV/gem5.opt -j4
```

如果 VM 内存压力较大，可以改用更保守的 `-j2`。

检查 `gem5.opt` 是否存在：

```bash
test -x tools/gem5/build/RISCV/gem5.opt && echo "gem5.opt ready" || echo "still building"
```

## 运行 baseline

运行 no-prefetch O3 baseline：

```bash
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/vadd_N1024.riscv \
  --bench-name vadd_N1024 \
  --config o3_nopf
```

运行 stride-prefetch O3 baseline：

```bash
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/vadd_N1024.riscv \
  --bench-name vadd_N1024 \
  --config o3_stridepf
```

每次运行会写入：

```text
results/<bench-name>/<config>/
  config.json
  config.ini
  simout
  simerr
  stats.txt
```

`config.json` 记录运行命令、benchmark、profile、cache/clock 设置和是否启用 stride prefetcher。即使运行失败，也应保留 `simout`、`simerr` 和 `config.json` 用于诊断。

## BOOM-like O3 配置说明

当前 profile 是一个 Medium-like、受公开 BOOM 配置启发的 gem5 O3 baseline。核心参数包括：

| 参数 | 当前值 |
| --- | ---: |
| `fetchWidth` | 4 |
| `decodeWidth` | 4 |
| `renameWidth` | 4 |
| `dispatchWidth` | 4 |
| `issueWidth` | 4 |
| `wbWidth` | 4 |
| `commitWidth` | 4 |
| `numROBEntries` | 128 |
| `numIQEntries` | 64 |
| `LQEntries` | 32 |
| `SQEntries` | 32 |
| `numPhysIntRegs` | 128 |
| `numPhysFloatRegs` | 128 |
| `numPhysVecRegs` | 128 |

重要表述：

```text
This is a BOOM-like O3 baseline inspired by public BOOM configurations.
It is not a cycle-accurate reproduction of BOOM.
```

也就是说，本项目目标是在 gem5 中建立一个可信的乱序 CPU baseline，而不是复现 BOOM RTL 时序、Chisel 实现细节或 Chipyard system integration。

## 当前结果摘要

当前 `vadd` 的核心结果如下：

| benchmark | config | instructions | cycles | IPC | L1D misses |
| --- | --- | ---: | ---: | ---: | ---: |
| `vadd_N1024` | `o3_nopf` | 139167 | 210900 | 0.659872 | 10655 |
| `vadd_N1024` | `o3_stridepf` | 139167 | 153872 | 0.904434 | 5049 |
| `vadd_N16384` | `o3_nopf` | 502123 | 508314 | 0.987821 | 94132 |
| `vadd_N16384` | `o3_stridepf` | 502123 | 352590 | 1.424099 | 34050 |

相对 `o3_nopf`，`o3_stridepf` 在 `vadd_N1024` 上：

- cycle 数减少约 27.0%；
- IPC 提高约 37.1%；
- L1D miss 数减少约 52.6%。

在 `vadd_N16384` 上：

- cycle 数减少约 30.6%；
- IPC 提高约 44.2%；
- L1D miss 数减少约 63.8%。

规模放大后 IPC 明显提高，说明 `N=1024` 的 IPC 偏低部分来自 benchmark 太小、固定启动开销和冷态影响占比较大。

更完整的解释见：

```text
notes/vadd_baseline_results.md
```

## 重新生成 stats 汇总

```bash
python3 scripts/parse_stats.py --results-dir results
```

输出：

```text
results/summary.csv
```

当前 parser 会提取：

- instruction / tick / cycle / IPC / CPI；
- L1D、L1I、L2 miss 指标；
- stride-prefetch 的 `pfIssued`、`pfUseful`、`accuracy`、`coverage` 等指标。

字段缺失时会留空，不会崩溃。

## git 结果文件策略

建议跟踪：

- `results/**/config.json`
- `results/**/config.ini`
- `results/**/simout`
- `results/**/simerr`
- `results/**/stats.txt`
- `results/summary.csv`

建议忽略：

- `tools/`
- `logs/`
- `results/**/config.dot`
- `results/**/config.dot.pdf`
- `results/**/config.dot.svg`
- `results/**/citations.bib`

原因是 `tools/` 和 `logs/` 属于本地环境，`config.dot*` 与 `citations.bib` 属于 gem5 可再生输出。真正用于复现实验和分析的关键信息已经保存在 `config.json`、`config.ini`、`simout/simerr`、`stats.txt` 和 `summary.csv`。

## 后续工作

建议下一阶段先扩展 benchmark，再考虑 stream-engine 机制：

1. 增加 `saxpy`、`triad` 或 `stencil1d` 等流式 kernel；
2. 扩展 `scripts/build_benchmarks.sh` 支持多个 benchmark；
3. 增加批量运行脚本，例如 `scripts/run_baselines.sh`；
4. 继续扩展 `scripts/parse_stats.py` 的派生指标，例如 speedup、cycle reduction、miss reduction；
5. 在多个 benchmark 上比较 `o3_nopf`、`o3_stridepf` 和后续 stream-engine 方案。

## 组会表述

本阶段目标不是完成 stream engine 建模，而是先建立可信的 O3 CPU baseline。

后续 stream engine 的收益不仅要和普通 O3 CPU 比，也要和 gem5 中的 stride prefetcher 比。

stride prefetcher 主要解决数据提前进入 cache 的问题，但不会减少动态 load/store 指令，也不会减少地址生成、rename、issue、commit 等流水线压力。

stream engine 后续要验证的是：能否把规则访存从主指令流中解耦，由硬件维护索引更新、buffer 状态和访存请求，从而降低边缘端 signal / AI 小 kernel 中访存相关指令对计算流水的干扰。
