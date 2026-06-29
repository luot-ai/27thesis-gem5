# BOOM 细粒度配置调研

## 目的

本文补充更细粒度的 BOOM 公开配置调研，重点关注：

- issue queue / execution unit / functional unit 组织；
- L1 I-cache / D-cache 参数；
- branch predictor 配置；
- 这些参数与 gem5 O3 baseline 的映射边界。

本文仍然遵循同一个原则：

```text
This is a BOOM-like O3 baseline inspired by public BOOM configurations.
It is not a cycle-accurate reproduction of BOOM.
```

## 资料来源

- BOOM documentation: parameterization
  - https://docs.boom-core.org/en/latest/sections/parameterization.html
- BOOM v4 config mixins
  - https://github.com/riscv-boom/riscv-boom/blob/master/src/main/scala/v4/common/config-mixins.scala
- BOOM v4 execution-unit sources
  - https://github.com/riscv-boom/riscv-boom/tree/master/src/main/scala/v4/exu/execution-units
- Chipyard BOOM config wrappers
  - https://github.com/ucb-bar/chipyard/blob/main/generators/chipyard/src/main/scala/config/BoomConfigs.scala

## 公开 BOOM v4 配置族

公开 BOOM 配置不是单个固定 RTL 文件，而是通过 Chisel / Chipyard config mixin 组合得到。v4 `config-mixins.scala` 中常见配置包括：

- `WithNSmallBooms`
- `WithNMediumBooms`
- `WithNLargeBooms`
- `WithNMegaBooms`
- `WithNGigaBooms`

这些配置主要扩展：

- fetch/decode 宽度；
- ROB 项数；
- issue queue 类型、深度、issueWidth、dispatchWidth；
- load/store queue；
- 物理寄存器文件；
- fetch buffer / FTQ；
- L1 I-cache / D-cache；
- branch predictor mixin。

## 核心宽度与 ROB / LSQ

| BOOM 配置 | fetchWidth | decodeWidth | ROB | LDQ | STQ | int phys regs | fp phys regs | FTQ entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Small | 4 | 1 | 32 | 8 | 8 | 52 | 48 | 16 |
| Medium | 4 | 2 | 64 | 16 | 16 | 80 | 64 | 32 |
| Large | 8 | 3 | 96 | 24 | 24 | 100 | 96 | 32 |
| Mega | 8 | 4 | 128 | 32 | 32 | 144 | 128 | 40 |
| Giga | 8 | 5 | 130 | 32 | 32 | 128 | 128 | 40 |

观察：

- Small / Medium 的 fetchWidth 都是 4，但 decodeWidth 分别是 1 和 2；
- Large 及以上 fetchWidth 提高到 8；
- Mega / Giga 的 LDQ/STQ 都是 32，接近我们当前 gem5 baseline 的 `LQEntries=32`、`SQEntries=32`；
- Mega 的 ROB=128，与当前 gem5 baseline 的 `numROBEntries=128` 一致；
- 公开 Medium BOOM 的 ROB=64，比当前 gem5 baseline 更小。因此当前 baseline 更像 “Medium-to-Mega 之间的 gem5 O3 折中配置”，而不是严格 Medium BOOM。

## Issue Queue 配置

BOOM v4 公开配置把 issue queue 分为四类：

- `IQ_MEM`：访存相关 issue queue；
- `IQ_UNQ`：unique / 特殊功能队列，例如 CSR、乘除法、部分转换等；
- `IQ_ALU`：整数 ALU 队列；
- `IQ_FP`：浮点队列。

| BOOM 配置 | MEM IQ | UNQ IQ | ALU IQ | FP IQ |
| --- | --- | --- | --- | --- |
| Small | issueWidth=2, entries=8, dispatchWidth=1 | issueWidth=1, entries=8, dispatchWidth=1 | issueWidth=1, entries=8, dispatchWidth=1 | issueWidth=1, entries=8, dispatchWidth=1 |
| Medium | issueWidth=2, entries=12, dispatchWidth=2 | issueWidth=1, entries=12, dispatchWidth=2 | issueWidth=2, entries=20, dispatchWidth=2 | issueWidth=1, entries=12, dispatchWidth=2 |
| Large | issueWidth=2, entries=16, dispatchWidth=3 | issueWidth=1, entries=16, dispatchWidth=3, slow=8 | issueWidth=3, entries=16, dispatchWidth=3, slow=8 | issueWidth=1, entries=24, dispatchWidth=3, slow=12 |
| Mega | issueWidth=3, entries=32, dispatchWidth=4 | issueWidth=1, entries=20, dispatchWidth=4 | issueWidth=4, entries=40, dispatchWidth=4 | issueWidth=2, entries=32, dispatchWidth=4 |
| Giga | issueWidth=2, entries=32, dispatchWidth=5, slow=12 | issueWidth=1, entries=32, dispatchWidth=5, slow=24 | issueWidth=5, entries=20, dispatchWidth=5, slow=10 | issueWidth=2, entries=32, dispatchWidth=5, slow=20 |

注意：

- 这里的 `issueWidth` 是对应 issue queue 的发射宽度，不等价于 gem5 单个全局 `issueWidth`；
- BOOM 的 issue queue 是分类型、分端口、带 slow entries 的结构；
- gem5 O3 默认建模更集中，不能干净复现 BOOM 的各类 issue queue。

## Execution Unit / Functional Unit 组织

BOOM 源码把 execution pipeline、execution unit、functional unit 分层组织。公开配置的 `issueParams` 不能直接等价为“FU 数量”，但能说明各类队列和发射端口压力。

BOOM v4 execution-unit 源码中可见的主要执行单元类型包括：

| BOOM execution unit | 典型功能 | 源码中出现的 FU code / unit |
| --- | --- | --- |
| `MemExeUnit` | 地址生成、store data 生成 | `FC_AGEN`, `FC_DGEN` |
| `ALUExeUnit` | 整数 ALU | `FC_ALU`, `ALUUnit` |
| `UniqueExeUnit` | 乘法、除法、CSR、整数到 FP 等特殊功能 | `FC_MUL`, `FC_DIV`, `FC_CSR`, `FC_I2F` |
| `FPExeUnit` | FPU、FDiv、FP-to-int 等 | `FC_FPU`, `FC_FDV`, `FC_F2I` |

functional-unit 源码中还能看到：

- `ALUUnit` 包装 Rocket Chip ALU；
- `PipelinedMulUnit` 包装 Rocket Chip pipelined multiplier；
- `DivUnit` 包装 Rocket Chip `MulDiv`；
- `FPUUnit` 包装 Rocket Chip / hardfloat 相关 FPU；
- `IntToFPUnit` 带 configurable latency；
- FPU 中 FP 单元被 padding 到统一 latency，便于调度写回端口。

FPU 参数在公开 BOOM 配置中通常为：

```text
FPUParams(sfmaLatency=4, dfmaLatency=4, divSqrt=true)
```

这说明公开 BOOM 配置默认包含单精度 / 双精度 FMA pipeline，并启用 divide/sqrt 支持。

## Cache 配置

BOOM tile 中 L1 cache 参数来自 Rocket Chip / Chipyard cache 参数。公开 BOOM v4 mixin 中可见：

| BOOM 配置 | D-cache 参数 | I-cache 参数 |
| --- | --- | --- |
| Small | rowBits=64, nSets=64, nWays=4, nMSHRs=2, nTLBWays=8 | rowBits=64, nSets=64, nWays=4, fetchBytes=8 |
| Medium | rowBits=64, nSets=64, nWays=4, nMSHRs=2, nTLBWays=8 | rowBits=64, nSets=64, nWays=4, fetchBytes=8 |
| Large | rowBits=128, nSets=64, nWays=8, nMSHRs=4, nTLBWays=16 | rowBits=128, nSets=64, nWays=8, fetchBytes=16 |
| Mega | rowBits=128, nSets=64, nWays=8, nMSHRs=8, nTLBWays=32 | rowBits=128, nSets=64, nWays=8, fetchBytes=16 |
| Giga | rowBits=128, nSets=64, nWays=8, nMSHRs=8, nTLBWays=32 | rowBits=128, nSets=64, nWays=8, fetchBytes=16 |

如果按常见 64-byte cache line 粗略估算：

- Small / Medium 的 L1 大致是 64 sets × 4 ways × 64 B = 16 KiB；
- Large / Mega / Giga 的 L1 大致是 64 sets × 8 ways × 64 B = 32 KiB。

但严格来说，BOOM cache 参数需要结合 Rocket Chip system-level cache block bytes、TileLink 系统参数一起解释，不能只看 BOOM mixin 就断言完整 cache hierarchy。

当前 gem5 baseline 使用：

- L1 I-cache: 32 KiB, 4-way；
- L1 D-cache: 32 KiB, 4-way；
- L2: 512 KiB, 8-way。

这比公开 Small/Medium BOOM 的常见 L1 容量估计更大，但比 Large/Mega/Giga 的 associativity 更低。它是一个实用 gem5 classic-cache baseline，而不是 Chipyard cache hierarchy 复刻。

## Branch Predictor 配置

BOOM v4 public configs 默认在 Small / Medium / Large / Mega / Giga 前叠加：

```scala
new WithTAGELBPD
```

`WithTAGELBPD` 的核心参数和组成包括：

- `bpdMaxMetaLength = 120`
- `globalHistoryLength = 64`
- `localHistoryLength = 1`
- `localHistoryNSets = 0`
- predictor bank 组合：Loop predictor、TAGE、BTB、BIM、micro-BTB。

v4 mixin 还提供其他 BPD 变体：

| BPD mixin | 组成/特征 |
| --- | --- |
| `WithTAGELBPD` | Loop + TAGE + BTB + BIM + micro-BTB，公开 BOOM 默认常用 |
| `WithFastTAGEBPD` | TAGE + slow/fast BTB + slow/fast BIM + micro-BTB |
| `WithBoom2BPD` | BIM + BTB + gshare-like TAGE variant，global history 16 |
| `WithAlpha21264BPD` | local/global BIM + tournament predictor + BTB |
| `WithSWBPD` | software branch predictor bank |

当前 gem5 baseline 使用 gem5 O3 默认 / 经典 branch predictor 近似，不能声称实现 BOOM 的 TAGE-L BPD。后续如果要更接近 BOOM，应优先考虑在 gem5 中显式设置更强的 branch predictor，例如 TournamentBP 或 TAGE-like predictor，并在报告中写成“近似 BOOM-style predictor”，而不是“复现 BOOM BPD”。

## 与当前 gem5 baseline 的对应关系

| 维度 | 公开 BOOM 观察 | 当前 gem5 baseline | 评价 |
| --- | --- | --- | --- |
| Fetch/decode | Medium: 4/2, Large: 8/3, Mega: 8/4 | 4/4 | decode 较宽，fetch 较保守 |
| ROB | Medium 64, Large 96, Mega 128 | 128 | 接近 Mega |
| LSQ | Medium 16/16, Large 24/24, Mega 32/32 | 32/32 | 接近 Mega |
| Int phys regs | Medium 80, Large 100, Mega 144 | 128 | Large 与 Mega 之间 |
| FP phys regs | Medium 64, Large 96, Mega 128 | 128 | 接近 Mega |
| Issue queue | BOOM 分 MEM/UNQ/ALU/FP 多队列 | gem5 单组 O3 参数近似 | 只能近似 |
| FU | BOOM execution unit 类型明确，端口与队列耦合 | gem5 FUPool 默认/近似 | 不能精确映射 |
| L1 cache | Small/Medium 约 16 KiB，Large+ 约 32 KiB | 32 KiB I/D, 4-way | 容量接近 Large+，路数不同 |
| BPD | 默认 TAGE-L | gem5 predictor 近似 | 当前不复现 TAGE-L |

## 对后续配置的建议

如果当前论文阶段只需要可信 baseline，维持现有 gem5 O3 profile 是可以接受的，因为：

- ROB / LSQ / phys regs 已经达到较强 O3 规模；
- vadd sanity check 已经显示 no-prefetch 与 stride-prefetch 差异明显；
- 继续调得更像 BOOM 会增加验证成本。

如果后续希望更“BOOM-like”，建议按优先级逐步调整：

1. **Branch predictor**：显式指定一个更强的 gem5 branch predictor，并记录其与 BOOM TAGE-L 的差异。
2. **Cache**：增加一个 `large_like` cache profile，例如 L1 32 KiB 8-way，L2 1 MiB。
3. **FU / issue**：不要直接声称复现 BOOM FU；可以建立一个 gem5 FUPool profile，粗略增加整数 ALU、load/store、FP pipeline 能力。
4. **多个 profile**：保留当前 `medium_boom_like` 作为主线，再增加 `large_boom_like` 作为敏感性分析。

最重要的是，报告中应把它描述为：

```text
BOOM-inspired gem5 O3 profile, calibrated from public BOOM configuration families.
```

而不是：

```text
BOOM-equivalent core.
```

