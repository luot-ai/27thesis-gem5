# 2026-08-15 工作记录

## 今日完成

1. 核对 vadd 的 ROI 数据、cacheline 大小和每 16 个元素的执行周期。
2. 使用 gem5 O3PipeView 获取 origin vadd 指令 trace，并编写
   `scripts/analyze_o3_loop_trace.py`，按 1024 次核心循环迭代重组流水线记录。
3. 确认 origin 核心循环第一条指令之前的 commit cycle 为 `167840`。
4. 分析慢迭代分布：大部分迭代为 2 cycles，每 16 个 `int32` 元素出现一次
   cacheline 边界相关的长延迟。
5. 拆解 L2 miss 路径，并区分 cache、总线、DRAM 和返回路径中的可配置延迟。
6. 修复无目标寄存器的 stream 自定义指令在生成反汇编时崩溃的问题；修改已通过
   C++ 对象编译与 gem5 提交检查，尚未完整链接后重跑 stream O3PipeView。
7. 对比当前 gem5 O3 baseline 与 Zircon RTL 配置，确认原 baseline 在译码、提交、
   ROB、IQ、LSU 和 cache 容量等方面更激进。
8. 增加单 LSU 配置并完成 vadd ROI 对比：

| CPU/benchmark | ROI cycles | IPC |
| --- | ---: | ---: |
| 原 4-memory-port origin | 12175 | 0.673840 |
| 单 LSU origin | 12959 | 0.633074 |
| 原 4-memory-port stream | 11870 | 0.262174 |
| 单 LSU stream | 11870 | 0.262174 |

相同单 LSU 条件下，stream 相对 origin 减少 `1089 cycles`，周期减少约
`8.40%`。

## Zircon 宽度对齐配置

新增 `zircon_width_like` profile，以及两个使用该 profile 的配置：

```text
o3_zircon_width_nopf
o3_stream_axi_functional_zircon_width
```

流水线宽度映射如下：

| 参数 | 原 `medium_boom_like` | Zircon RTL | `zircon_width_like` |
| --- | ---: | ---: | ---: |
| fetch | 4 | 4 | 4 |
| decode | 4 | 2 | 2 |
| rename | 4 | 跟随 decode | 2 |
| dispatch | 4 | 跟随 decode | 2 |
| issue | 4 | 3 ALU + 1 Mul/Div + 1 LSU | 5（全局上限） |
| writeback | 4 | 最多接近总 issue 能力 | 5 |
| commit | 4 | 2 | 2 |
| squash | 4 | 未单独给出 | 2 |
| memory issue | 4 个 combined ports | LSU 单发 | 1 个 combined port |

本轮只校准流水线宽度并沿用单 LSU。为隔离变量，以下参数仍保持
`medium_boom_like`：128 ROB、64 IQ、32 LQ、32 SQ、物理寄存器数量、64B
cacheline，以及 L1/L2 容量和延迟。

因此该配置是“Zircon 宽度近似配置”，还不是完整的 Zircon 微架构复现。后续若继续
对齐，应分开评估 ROB/IQ、cache 容量与 128B L2 line，避免无法判断周期变化来自哪一项。

### 配置验证与 ROI 结果

两个新配置均通过 `N=1024` 程序自检，生成的 `config.ini` 确认：

```text
fetch/decode/rename/dispatch = 4/2/2/2
issue/writeback/commit/squash = 5/5/2/2
cacheLoadPorts/cacheStorePorts = 1/1
combined RdWrPort count = 1
```

实测 ROI：

| CPU/benchmark | config | ROI cycles | IPC |
| --- | --- | ---: | ---: |
| 单 LSU origin，原 4-wide profile | `o3_single_lsu_nopf` | 12959 | 0.633074 |
| Zircon-width origin | `o3_zircon_width_nopf` | 13149 | 0.623926 |
| 单 LSU stream，原 4-wide profile | `o3_stream_axi_functional_single_lsu` | 11870 | 0.262174 |
| Zircon-width stream | `o3_stream_axi_functional_zircon_width` | 11902 | 0.261469 |

相对只改单 LSU 的版本，宽度对齐使 origin 增加 `190 cycles`（约 `1.47%`），
使 stream 增加 `32 cycles`（约 `0.27%`）。在相同 Zircon-width CPU 条件下：

```text
cycle reduction = 13149 - 11902 = 1247 cycles
speedup = 13149 / 11902 = 1.1048x
cycle reduction ratio = 9.48%
```

这说明当前 `N=1024` vadd 中，单 LSU 是比 2-wide decode/commit 更明显的 origin
约束；stream 版本仍主要受 StreamEngine 的访存延迟模型约束。

## 阻塞 Cache 敏感性试验

gem5 classic timing cache 不能将 MSHR 设为 0，否则 cache miss 无处保存请求和返回
状态。新增以下配置，用 `1 MSHR + 1 target/MSHR` 近似不支持 miss 并行的阻塞
cache：

```text
o3_zircon_blocking_cache_nopf
o3_stream_axi_functional_zircon_blocking_cache
```

对应 profile 为 `zircon_blocking_cache_like`。L1I、L1D 和 L2 均配置为：

```text
mshrs = 1
tgts_per_mshr = 1
```

其他参数保持 `zircon_width_like` 不变，包括流水线宽度、单 LSU、cache 容量、
cacheline 和访问延迟。两组 `N=1024` benchmark 均通过程序自检。

| CPU/benchmark | 正常 MSHR cycles | 阻塞 cache cycles | 变化 |
| --- | ---: | ---: | ---: |
| Zircon-width origin | 13149 | 34084 | +159.21% |
| Zircon-width stream | 11902 | 12028 | +1.06% |

在相同阻塞-cache 配置下：

```text
cycle reduction = 34084 - 12028 = 22056 cycles
speedup = 34084 / 12028 = 2.8337x
cycle reduction ratio = 64.71%
```

origin 的 L1D `overallMisses` 从 2468 降为 195 并不表示命中率变好。正常配置中，
大量后续请求可以进入 cache 并合并为 MSHR hit；阻塞配置会让它们停在 cache 之外，
等唯一 miss 完成后再访问，因此统计上的 miss 次数减少，但总周期显著增加。
对应的 L1D `blockedCycles::no_mshrs` 从 0 增加到 30837 cycles，直接显示了唯一
MSHR 被占用时产生的阻塞。

该配置是敏感性分析的极端下界，不应直接称为“gem5 完全没有 MSHR”。当前 stream
数据路径绕过 L1/L2，因此阻塞普通 cache 会显著放大 stream 相对 origin 的收益。

## 今日提交

```text
4b1f764  增加 O3 循环 trace 分析工具
1056291  增加单 LSU 配置并记录向量加结果
87a6b36  arch-riscv: 修复无目标寄存器指令的反汇编（tools/gem5）
```

本轮另新增“增加 Zircon 宽度近似配置并记录结果”提交，保存本文档、配置和实测结果。
