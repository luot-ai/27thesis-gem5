# gem5 O3 LSU 周期校准方案

## 目标

当前目标不是继续追求“更强”的 O3 baseline，而是让 naive O3 的周期数尽量和
RTL baseline / BOOM-like 单 LSU 行为对齐，从而让 stream-engine 对比更可信。

本文只提出配置和验证方案，暂不直接修改配置代码。

## 当前问题

当前 `medium_boom_like` O3 配置的访存侧偏强：

```text
issueWidth = 4
LQEntries / SQEntries = 32 / 32
L1D MSHR = 16
L2 MSHR = 32
Mem FU = 4 个 RdWrPort
cacheLoadPorts = 200
cacheStorePorts = 200
```

这意味着 gem5 O3 可以在同一周期发射多条 load/store，并允许大量 cache miss
并行挂起。它更像一个访存发射端口很宽的 O3 core，而不是 RTL baseline 的单 LSU。

对 `vadd` 这种规则流式访存，当前配置会让 naive 版本非常擅长 overlap miss：

```text
load a[i]
load b[i]
add
store y[i]
```

不会按单个元素串行执行，而是大量迭代交叠。

## RTL Baseline 约束

当前 RTL baseline 的关键约束是：

```text
load/store 指令单发经过 LSU
load 和 store 共享 LSU 通路
load-hit 情况下，load issue 到 dependent compute issue 约 +2 cycle
compute issue 到 dependent store issue 约 +2 cycle
```

这里的 `+2 cycle` 指的是 wakeup / issue-cycle 间隔，不是 memory miss latency。

## BOOM 参考结论

公开 BOOM 文档中，LSU 由 LDQ / STQ 组成，并负责决定 memory op 何时发往
memory system。文档版 BOOM currently only supports one LSU；load 和 store 会竞争
memory port。BOOM 仍然是乱序 core，可以有 LDQ/STQ 和 non-blocking cache，但 LSU
入口不是当前 gem5 O3 这种近乎无限宽。

BOOM 有 fast/slow wakeup 概念：

```text
ALU: fast wakeup
load: slow wakeup，等 load 返回 / writeback 后唤醒 dependent
```

gem5 O3 没有显式 fast/slow wakeup 分类。gem5 中普通 ALU 和 load 都在完成 /
writeback 路径调用 `wakeDependents()`。ALU 因为 `opLat=1` 表现得很快；load 必须等
DCache/LSQ response 后才唤醒 dependent。

因此，若目标是周期校准，应把 gem5 O3 的访存发射宽度先收紧到更接近单 LSU。

## 建议新增配置

建议新增一个独立配置，而不是覆盖当前 `o3_nopf`：

```text
o3_single_lsu_nopf
o3_single_lsu_stridepf
o3_stream_axi_functional_single_lsu
```

其中 `o3_single_lsu_nopf` 用作 naive baseline；stream 版本是否使用同一 CPU 配置
取决于实验口径。

## 配置改动建议

### 1. 单 LSU / 单访存发射口

新增一个 FUPool，只保留 1 个 combined memory port：

```text
RdWrPort count = 1
ReadPort count = 0
WritePort count = 0
```

效果：

```text
每周期最多发射 1 条 MemRead 或 MemWrite
load 和 store 竞争同一访存 FU
```

这是最接近 RTL 单 LSU 的第一优先级改动。

### 2. 限制 LSQ 到 DCache 的端口

当前：

```text
cacheLoadPorts = 200
cacheStorePorts = 200
```

建议改为：

```text
cacheLoadPorts = 1
cacheStorePorts = 1
```

这会限制 LSQ 每周期向 DCache 发请求的能力。注意：gem5 中 load 和 store 仍然分别
计数，因此这不是完全严格的“load/store 共用一个 cache port”。真正共用端口主要靠
`RdWrPort count = 1` 约束。

### 3. 保留 O3 乱序窗口

第一版建议暂时不改：

```text
issueWidth = 4
ROB = 128
IQ = 64
LQ/SQ = 32/32
```

原因是我们当前要校准 LSU，不要一次改太多变量。若 single-LSU 后 naive 仍明显偏强，
再考虑减少 LQ/SQ 或 MSHR。

### 4. MSHR 参数分阶段收紧

第一版建议保留：

```text
L1D MSHR = 16
L2 MSHR = 32
```

如果结果仍过强，再尝试：

```text
L1D MSHR = 4 或 8
L2 MSHR = 8 或 16
```

不建议一开始把 MSHR 改成 1，因为 BOOM / O3 通常是 non-blocking cache，单 LSU
不等于 blocking cache。

### 5. load-hit wakeup 校准

当前 gem5 观测：

```text
system.cpu.lsq0.loadToUse::min_value = 3 cycles
```

RTL 目标：

```text
load issue -> dependent compute issue = +2 cycles
```

这两个口径接近但不完全等价。第一版不建议为了 `+2` 直接硬改 gem5 wakeup 逻辑。
建议先记录：

```text
loadToUse min / mean / distribution
O3PipeView 中 load issue tick 与 dependent add issue tick
```

如果必须进一步对齐，再考虑修改 load `opLat`、L1D latency 或 wakeup 路径。

### 6. compute -> store-data 校准

RTL 目标：

```text
compute issue -> dependent store issue = +2 cycles
```

gem5 中 ALU `opLat=1`，dependent store-data 可能比 RTL 更早被唤醒。第一版建议先
用 O3PipeView / debug trace 量实际 issue tick 差。如果明显偏小，再考虑：

```text
IntAlu opLat = 2
```

但这会影响所有整数计算，不只影响 store-data，因此优先级低于 single-LSU。

## 验证方法

### Benchmark

使用静态数据版 `vadd_N1024`：

```text
a/b 初值来自 ELF data 段
y 来自 bss
ROI 只包计算循环
```

这样避免 ROI 前 CPU 初始化数组导致 L1D 预热。

### 必看统计

```text
system.cpu.numCycles
system.cpu.ipc
system.cpu.commitStats0.numLoadInsts
system.cpu.commitStats0.numStoreInsts
system.cpu.commitStats0.committedInstType::MemRead
system.cpu.commitStats0.committedInstType::MemWrite
system.cpu.lsq0.loadToUse::min_value
system.cpu.lsq0.loadToUse::mean
system.cpu.dcache.overallMisses::total
system.l2cache.overallMisses::total
system.l2cache.overallAvgMshrMissLatency::total
```

### 当前参考结果

静态数据 `N=1024`，当前宽访存 O3：

```text
naive vadd / o3_nopf:
  ROI cycles = 12175
  L1D misses = 2559
  L2 misses = 192
  L2 avg MSHR miss latency ~= 139 CPU cycles

stream vadd / o3_stream_axi_functional:
  ROI cycles = 11870
  loadBurstBusyCycles = 11264
```

### 单 LSU 第一版实测结果

已新增以下独立配置，原配置保持不变：

```text
o3_single_lsu_nopf
o3_stream_axi_functional_single_lsu
```

两组配置都使用：

```text
RdWrPort count = 1
ReadPort count = 0
WritePort count = 0
cacheLoadPorts = 1
cacheStorePorts = 1
```

静态数据 `N=1024`、ROI 只包含向量加核心循环，实测如下：

| CPU/benchmark | config | ROI cycles | IPC |
| --- | --- | ---: | ---: |
| 原4端口 CPU / naive | `o3_nopf` | 12175 | 0.673840 |
| 单 LSU CPU / naive | `o3_single_lsu_nopf` | 12959 | 0.633074 |
| 原4端口 CPU / stream | `o3_stream_axi_functional` | 11870 | 0.262174 |
| 单 LSU CPU / stream | `o3_stream_axi_functional_single_lsu` | 11870 | 0.262174 |

单 LSU 使 naive 增加 784 cycles，即增加约 6.44%。stream ROI 不变，因为当前
stream 核心循环的数据传输走 StreamEngine 简化 memory-side，SSS 也不占用普通
`MemRead/MemWrite` FU。

在相同单 LSU CPU 下：

```text
cycle reduction = 12959 - 11870 = 1089 cycles
speedup = 12959 / 11870 = 1.0917x
cycle reduction ratio = 8.40%
```

64B cacheline 对应 16 个 `int32` 元素，1024 个元素共有 64 组，因此：

```text
naive  = 202.48 cycles / 16 elements
stream = 185.47 cycles / 16 elements
收益    = 17.02 cycles / 16 elements
```

两组 benchmark 均通过程序自检。生成的 `config.ini` 也确认单 LSU 配置中的 combined
`RdWrPort count=1`，且 `cacheLoadPorts/cacheStorePorts` 均为 1。

single-LSU 后预期：

```text
naive vadd cycles 应上升
load/store 发射 overlap 应减少
stream vadd 若仍用当前 stream memory-side，周期变化应较小
```

## 推荐实施顺序

1. 新增 `single_lsu` FUPool，不改其他参数。
2. 添加 `o3_single_lsu_nopf` 配置并跑 `vadd_N1024`。
3. 记录 ROI cycles、loadToUse、L1/L2 miss、committed load/store 数。
4. 与当前 `o3_nopf` 和 `o3_stream_axi_functional` 对比。
5. 如果 naive 仍偏强，再收紧 L1D/L2 MSHR。
6. 如果 load-hit / compute-store issue 间隔仍与 RTL 差距明显，再考虑 wakeup/latency
   校准。

## 报告措辞建议

```text
We use two gem5 O3 CPU profiles. The default O3 profile is a medium BOOM-like
out-of-order baseline with a relatively permissive memory issue model. For
cycle-sensitive comparison with the RTL baseline, we additionally use a
single-LSU O3 profile that constrains memory issue to one combined load/store
operation per cycle. This profile is intended to approximate the single LSU
constraint of the RTL baseline and the public BOOM LSU description; it is not
a cycle-accurate BOOM reproduction.
```
