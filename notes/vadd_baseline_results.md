# vadd_N1024 Baseline Results

## 目的

本文记录当前第一组 gem5 RISC-V O3 baseline 结果，用于确认评估链路已经跑通：

- benchmark 能编译为 RISC-V 可执行文件；
- gem5 O3 no-prefetch baseline 能正常运行；
- stride-prefetch baseline 能正常运行；
- stats 能被整理为 CSV 表格。

本文先记录 `vadd_N1024` 的最小流程验证结果，并补充 `vadd_N16384`
作为规模放大后的 sanity check。结果仍然只代表 vector-add 这一类简单
流式 kernel，不应直接外推到完整论文结论。

## 实验配置

| 项目 | 配置 |
| --- | --- |
| benchmark | `vadd_N1024` |
| benchmark 源码 | `benchmarks/vadd/vadd.c` |
| RISC-V binary | `build/vadd_N1024.riscv` |
| gem5 binary | `tools/gem5/build/RISCV/gem5.opt` |
| gem5 version | 25.1.0.1 |
| CPU baseline | Medium-like BOOM-inspired gem5 O3 |
| no-prefetch result | `results/vadd_N1024/o3_nopf`, `results/vadd_N16384/o3_nopf` |
| stride-prefetch result | `results/vadd_N1024/o3_stridepf`, `results/vadd_N16384/o3_stridepf` |
| summary CSV | `results/summary.csv` |

该 CPU 配置是受公开 BOOM 配置启发的 BOOM-like gem5 O3 baseline。
它不是对 BOOM 的周期精确复现。

## 核心结果：N = 1024

| 指标 | `o3_nopf` | `o3_stridepf` | 变化 |
| --- | ---: | ---: | ---: |
| simulated instructions | 139167 | 139167 | 相同 |
| cycles | 210900 | 153872 | 减少约 27.0% |
| IPC | 0.659872 | 0.904434 | 提高约 37.1% |
| CPI | 1.515445 | 1.105664 | 降低 |
| L1D overall misses | 10655 | 5049 | 减少约 52.6% |
| L1D overall miss rate | 0.369914 | 0.169435 | 降低 |
| L2 overall misses | 1502 | 1796 | 增加 |

stride-prefetch run 的预取相关指标：

| 指标 | 数值 |
| --- | ---: |
| `pfIssued` | 3501 |
| `pfUseful` | 488 |
| `pfUnused` | 117 |
| `accuracy` | 0.139389 |
| `coverage` | 0.534502 |
| `pfLate` | 2526 |

## 规模放大 Sanity Check：N = 16384

为了检查 `N=1024` 是否过小、是否被启动开销和冷 cache 效应放大影响，
进一步运行了 `vadd_N16384`。

| 指标 | `o3_nopf` | `o3_stridepf` | 变化 |
| --- | ---: | ---: | ---: |
| simulated instructions | 502123 | 502123 | 相同 |
| cycles | 508314 | 352590 | 减少约 30.6% |
| IPC | 0.987821 | 1.424099 | 提高约 44.2% |
| CPI | 1.012330 | 0.702198 | 降低 |
| L1D overall misses | 94132 | 34050 | 减少约 63.8% |
| L1D overall miss rate | 0.731173 | 0.263518 | 降低 |
| L2 overall misses | 2462 | 4675 | 增加 |

`vadd_N16384` 的 stride-prefetch 预取相关指标：

| 指标 | 数值 |
| --- | ---: |
| `pfIssued` | 40643 |
| `pfUseful` | 4762 |
| `pfUnused` | 188 |
| `accuracy` | 0.117167 |
| `coverage` | 0.898660 |
| `pfLate` | 32752 |

## 初步解读

`o3_stridepf` 相比 `o3_nopf` 有更低的 cycle 数和更高的 IPC。对 `vadd_N1024` 这种规则流式访存 kernel，stride prefetcher 能提前发起部分数据访问，因此 L1D miss 数明显降低。

`N=16384` 的结果说明，先前 `N=1024` 的 IPC 偏低部分来自 benchmark 规模太小。规模放大后，no-prefetch IPC 从 0.659872 提高到 0.987821，stride-prefetch IPC 从 0.904434 提高到 1.424099。这说明固定启动开销和冷态影响在小规模运行中占比明显。

同时，预取并不是免费的。`o3_stridepf` 的 L2 overall misses 比 no-prefetch 更多，说明预取向下一级 cache / memory system 引入了额外流量。`pfIssued` 远大于 `pfUseful`，且 `accuracy` 只有约 0.139，也说明当前预取器配置并不是完美命中未来 demand access。

因此，这组结果适合作为后续 stream-engine 机制的 baseline：

- no-prefetch O3 表示普通乱序核基线；
- stride-prefetch O3 表示已有硬件预取机制基线；
- 后续 stream engine 不能只和 no-prefetch 比，还应和 stride-prefetch 比。

## 和 Stream Engine 的区别

stride prefetcher 主要解决“数据能否更早进入 cache”的问题。它通常不会减少主指令流中的 load/store 指令，也不会直接减少地址生成、rename、issue、commit 等流水线压力。

后续 stream engine 要验证的是另一类收益：能否把规则访存从主指令流中解耦，由硬件维护索引更新、buffer 状态和访存请求，从而减少访存相关指令对乱序流水线资源的占用。

## 当前结论

当前阶段已经具备一个可复现的最小 baseline 流程：

1. 编译 `vadd_N1024`；
2. 跑 gem5 O3 no-prefetch；
3. 跑 gem5 O3 stride-prefetch；
4. 生成 `results/summary.csv`；
5. 记录 BOOM-like O3 配置来源和验证结果。

下一步应增加更多流式 benchmark，例如 `saxpy`、`triad` 或 `stencil1d`，并对每个 benchmark 使用至少一个比 `N=1024` 更大的规模，避免只基于单个小 kernel 得出过强结论。
