# vadd_N1024 Baseline Results

## 目的

本文记录当前第一组 gem5 RISC-V O3 baseline 结果，用于确认评估链路已经跑通：

- benchmark 能编译为 RISC-V 可执行文件；
- gem5 O3 no-prefetch baseline 能正常运行；
- stride-prefetch baseline 能正常运行；
- stats 能被整理为 CSV 表格。

本结果只代表 `vadd_N1024` 这个小规模流式 kernel 的初步现象，不应直接外推到完整论文结论。

## 实验配置

| 项目 | 配置 |
| --- | --- |
| benchmark | `vadd_N1024` |
| benchmark 源码 | `benchmarks/vadd/vadd.c` |
| RISC-V binary | `build/vadd_N1024.riscv` |
| gem5 binary | `tools/gem5/build/RISCV/gem5.opt` |
| gem5 version | 25.1.0.1 |
| CPU baseline | Medium-like BOOM-inspired gem5 O3 |
| no-prefetch result | `results/vadd_N1024/o3_nopf` |
| stride-prefetch result | `results/vadd_N1024/o3_stridepf` |
| summary CSV | `results/summary.csv` |

该 CPU 配置是受公开 BOOM 配置启发的 BOOM-like gem5 O3 baseline。
它不是对 BOOM 的周期精确复现。

## 核心结果

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

## 初步解读

`o3_stridepf` 相比 `o3_nopf` 有更低的 cycle 数和更高的 IPC。对 `vadd_N1024` 这种规则流式访存 kernel，stride prefetcher 能提前发起部分数据访问，因此 L1D miss 数明显降低。

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

下一步应增加更多流式 benchmark，例如 `saxpy`、`triad` 或 `stencil1d`，避免只基于单个小 kernel 得出过强结论。
