# BOOM 公开配置调研

## 目的

本文调研公开的 BOOM 配置，并为当前论文阶段确定一个实用的、类 BOOM 的 gem5 O3 baseline。

这是一个受公开 BOOM 配置启发的类 BOOM O3 baseline。
它不是对 BOOM 的周期精确复现。

## 资料来源

* BOOM 文档：参数化与生成器概述

  * https://docs.boom-core.org/en/latest/sections/parameterization.html
* BOOM 公开配置 mixin

  * https://github.com/riscv-boom/riscv-boom/blob/master/src/main/scala/v3/common/config-mixins.scala
* Chipyard BOOM 配置封装

  * https://github.com/ucb-bar/chipyard/blob/main/generators/chipyard/src/main/scala/config/BoomConfigs.scala

## 公开 BOOM 配置族

公开 BOOM 配置通常不是以固定的独立 RTL 文件形式暴露，而是通过 Chipyard / BOOM 的配置 mixin 进行组合和生成。常见配置族包括：

* Small BOOM
* Medium BOOM
* Large BOOM
* 某些 Chipyard 配置中的 Mega / 更大规模 BOOM 变体

这些配置主要通过调整核心宽度和结构规模来扩展。最重要的参数包括：

* 取指宽度
* 译码宽度
* 分派宽度
* 发射宽度 / 发射队列结构
* 提交宽度
* 重排序缓冲区项数
* 读队列项数
* 写队列项数
* 物理寄存器文件大小
* 分支预测器 / BTB / RAS 参数
* 通过外围 Chipyard 系统配置的 cache 和 TLB 参数

## 可以较合理映射到 gem5 O3 的参数

以下 BOOM 风格参数可以较合理地近似映射到 gem5 O3 CPU 参数：

| BOOM 概念          | gem5 O3 参数区域                   | 说明                        |
| ---------------- | ------------------------------ | ------------------------- |
| 取指宽度             | `fetchWidth`                   | 高层含义相近。                   |
| 译码宽度             | `decodeWidth`                  | 高层含义相近。                   |
| 重命名 / 分派宽度       | `renameWidth`, `dispatchWidth` | gem5 将多个流水级宽度分开建模。        |
| 发射宽度             | `issueWidth`                   | 可作为有用近似，但调度模型并不完全相同。      |
| 提交宽度             | `commitWidth`, `squashWidth`   | 与退休 / 提交带宽在高层含义上相近。       |
| ROB 项数           | `numROBEntries`                | 直接有参考价值。                  |
| 整数物理寄存器数量        | `numPhysIntRegs`               | 近似映射。                     |
| 浮点物理寄存器数量        | `numPhysFloatRegs`             | 近似映射。                     |
| Load Queue 项数    | `LQEntries`                    | 直接有参考价值。                  |
| Store Queue 项数   | `SQEntries`                    | 直接有参考价值。                  |
| 分支预测器            | gem5 分支预测器对象                   | 只能近似。                     |
| BTB / RAS        | BTB / RAS 预测器参数                | 只能近似。                     |
| L1 / L2 cache 大小 | gem5 cache 对象                  | 可以做较合理的 classic-cache 近似。 |

## 无法干净映射的参数

有些 BOOM 细节不应声称已被 gem5 O3 复现：

* 精确的 Chisel 流水线时序
* 精确的 BOOM 发射队列实现
* 精确的旁路网络时序
* 精确的功能单元延迟与仲裁
* 精确的分支预测器实现细节
* 精确的前端 FTQ / Fetch Target Queue 行为
* 精确的访存依赖预测器行为
* 精确的 cache coherence / TileLink 行为
* 精确的 Rocket-Chip / Chipyard tile 集成方式
* Chisel 生成的 RTL 结构
* 物理设计影响、FPGA 时序或综合后的面积 / 功耗

这些差异是重要的，因为 gem5 O3 是一个模拟器模型，具有自身的流水线实现，并不是由 BOOM RTL 生成得到的模型。

## 候选 Baseline

### Small-like O3

Small-like baseline 可以使用较窄的 O3 核心和较小的队列：

* 2-wide 前端 / 后端
* 相对较小的 ROB
* 较小的 load / store queue
* 较小的物理寄存器文件

该配置更容易运行，但如果论文 baseline 需要代表一个较强的乱序 CPU，它可能偏弱。

### Medium-like O3

Medium-like baseline 是更适合作为第一阶段目标的配置：

* 3-wide 或 4-wide 前端 / 后端
* 中等规模 ROB
* 中等规模 load / store queue
* 中等规模物理寄存器文件
* 常规私有 L1 cache 与 L2 cache

该配置能够提供一个可信的 O3 baseline，同时不会让模拟成本过高。

### Large-like O3

Large-like baseline 会使用更宽的流水线和更大的队列：

* 更宽的 fetch / decode / rename / issue / commit
* 更大的 ROB
* 更大的 LSQ
* 更大的物理寄存器文件
* 更强的分支预测

该配置后续可能有用，但在最小 benchmark 流程和 stats 统计链路稳定之前，它可能过于复杂。

## 当前阶段推荐的类 BOOM Baseline

当前阶段建议使用一个 Medium-like、受 BOOM 启发的 gem5 O3 profile 作为主要 baseline。

推荐的初始配置如下：

| 参数                 |      建议 gem5 取值 | 理由                           |
| ------------------ | --------------: | ---------------------------- |
| `fetchWidth`       |               4 | 中等激进的前端配置。                   |
| `decodeWidth`      |               4 | 匹配较实际的中等宽度 O3 目标。            |
| `renameWidth`      |               4 | 保持前端与后端平衡。                   |
| `dispatchWidth`    |               4 | 保持后端平衡。                      |
| `issueWidth`       |               4 | 避免设置成不现实的超大机器。               |
| `wbWidth`          |               4 | 与发射宽度保持平衡。                   |
| `commitWidth`      |               4 | 中等 O3 提交带宽。                  |
| `squashWidth`      |               4 | 与提交 / 取指规模匹配。                |
| `numROBEntries`    |             128 | 中等规模 ROB，适合作为第一版 baseline。   |
| `numIQEntries`     |              64 | 中等规模发射队列。                    |
| `LQEntries`        |              32 | 对流式 kernel 足够。               |
| `SQEntries`        |              32 | 对简单访存 kernel 足够。             |
| `numPhysIntRegs`   |             128 | 中等规模整数物理寄存器文件。               |
| `numPhysFloatRegs` |             128 | 中等规模浮点物理寄存器文件，也可作为向量标量部分的近似。 |
| L1 I-cache         |   32 KiB, 4-way | 常规私有 L1。                     |
| L1 D-cache         |   32 KiB, 4-way | 常规私有 L1。                     |
| L2 cache           | 512 KiB 到 1 MiB | 对单核运行而言，是合理的下一级 cache 配置。    |

具体 cache 层次可以在第一次 gem5 运行成功后再细化。
对于 Step 6，第一版实现应优先保证一个可工作的单核 SE-mode O3 配置，而不是追求完美的 BOOM 保真度。

## 为什么该配置适合当前论文阶段

当前论文阶段需要一个可信的 CPU baseline，用于后续和 stream-engine 机制进行比较。Medium-like O3 baseline 比较合适，因为：

* 它强于顺序核或很小的 O3 baseline；
* 它可以将 gem5 模拟时间控制在可接受范围内；
* 它能够暴露 rename、issue、LSQ、ROB 和 cache 层次上的压力；
* 它可以和无预取、stride prefetch 等配置进行对比；
* 它避免了声称周期精确复现 BOOM 的风险。

## 报告表述建议

建议使用以下表述：

这是一个受公开 BOOM 配置启发的类 BOOM O3 baseline。
它不是对 BOOM 的周期精确复现。

目标是在 gem5 中提供一个可信的乱序 CPU baseline，而不是复现 BOOM RTL 时序、Chisel 实现细节或 Chipyard 系统集成方式。
