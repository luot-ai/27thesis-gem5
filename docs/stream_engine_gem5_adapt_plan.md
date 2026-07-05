# Stream Engine gem5 适配草案

## 目的

本文整理当前 Chisel RTL / 软件示例中的 Stream Engine 语义，并给出第一版
gem5 适配范围。目标不是立刻复现完整 RTL 时序，而是先实现一个能跑通
vector add 的近似 stream-engine model，之后再逐步增加更细的流水线和 cache
连接。

## 已阅读材料

- `docs/流式访存总结文档.md`
- `docs/指令集文档.md`
- `codes_lib/software/stream_instr.h`
- `codes_lib/software/stream-add.c`
- `codes_lib/rtl/Stream.scala`

当前工作区中只看到 `codes_lib/rtl/Stream.scala`。IDE 中提到的
`codes_lib/Stream.scala` 和 `rtl_codes/Stream.scala` 在当前路径下暂未找到。

## 第一版适配边界

按照当前讨论，第一版 gem5 适配范围收敛为：

- 先只支持 vector add 风格的线性 load/load/store stream。
- 访存接口先实现为 Stream Engine 直连 AXI / memory bus 的近似模型。
- 暂不实现 Stream Engine 与 L2 cache 的连接。
- 暂不实现 Stream Engine 与 L1 D-cache 的连接。
- 暂不实现 FFT / PP buffer 路径。
- 暂不实现 CALSTREAM 指令在 CPU dispatch/issue/execute/writeback 流水线里的精确流动。
- 可以先把 CALSTREAM 建模为 Stream Engine 内部带计算部件的多级流水。
- 指令编码以 `docs/指令集文档.md` v0.6 为当前实现依据。
- compute 指令第一版只支持 SSS ADD，但代码结构要保留后续扩展 sub/mul/SSR/PP 的空间。
- direct AXI 版本不保证与 CPU cache 自动一致，按编程约束处理。

因此第一版的验收目标是：

1. gem5 能识别 stream 配置指令和 `sss_add`。
2. Stream Engine 内部能保存 descriptor / FIFO / ready 状态。
3. Stream Engine 能按配置从 memory bus 取 A/B 数据，执行加法，写回 C。
4. stream 版本 vector add 能在 gem5 SE-mode 下跑通并自检通过。
5. stats 能输出 stream 指令数、stream load/store 请求数、buffer stall 等基础指标。
6. batch runner 能把 `o3_stream_axi` 纳入现有 baseline 对比。

## 已确认的关键约束

### SE-mode / TLB

当前 gem5 SE-mode O3 配置里仍然有 `system.cpu.mmu`，并包含 RISC-V ITB/DTB。
例如当前 `config.ini` 中有：

```text
system.cpu.mmu
system.cpu.mmu.dtb: type=RiscvTLB
system.cpu.mmu.itb: type=RiscvTLB
```

但这不是启动 Linux 后由真实页表驱动的 TLB。RISC-V SE-mode 里，
`RiscvProcess` 使用 `EmulationPageTable`，TLB 翻译时会通过 process 的
emulation page table 将虚拟地址映射到 gem5 内部物理地址。

这和原 RTL 不同：原 RTL 面向 DSP CPU / bare-metal 场景，不启动 Linux，
也没有 TLB。适配时需要明确：

- 软件里传给 stream 指令的数组地址是 SE-mode 虚拟地址；
- Stream Engine 若要走 gem5 memory bus，需要得到物理地址；
- 第一版可以选择在 stream 指令执行时调用 gem5 的翻译接口，或者先用
  SE-mode process memory 接口实现功能模型。

具体方案分两步做：

1. **功能跑通阶段**
   Stream 指令执行时先使用 `SETranslatingPortProxy` 或 process
   `EmulationPageTable` 对虚拟地址进行访问。这个路径最容易保证功能正确，
   也能绕开 direct AXI 与 CPU cache 不一致导致的初始值 / 校验问题。代价是
   memory traffic 和 stall 不代表真实 AXI 时序。

2. **timing direct AXI 阶段**
   Stream Engine 作为独立 SimObject，提供一个 `RequestPort` 连接
   `system.membus`。stream 指令传入的 base address 仍然是虚拟地址，但在
   发起每个 burst / word 请求前，通过 CPU `ThreadContext` 对应的
   SE-mode page table 翻译成物理地址，然后用物理地址构造 memory packet。
   这个模型绕过 CPU 私有 cache，接近“直连 AXI 到 memory bus”的目标。

timing 阶段需要注意 page crossing：一个 stream burst 如果跨 4 KiB page，
必须拆成多个物理连续的小请求。第一版可以保守地逐 word 翻译；确认功能后再
优化成“同一 page 内按 cacheline / burst 翻译一次”。

这个 VA->PA 翻译只属于 gem5 SE-mode 适配层，不应写成硬件 RTL 拥有 TLB。
统计里可以加 `stream.addrTranslations`，但第一版翻译延迟建议先按 0 cycle
处理，避免把仿真机制误当成硬件机制。

### Cache 一致性

第一版 direct AXI / memory-bus Stream Engine 不保证自动 cache 一致性。
这与原 RTL 设计取向一致：编程人员需要保证直连 AXI 对象在整个生命周期中
走：

```text
memory -> stream buffer -> memory
```

也就是说，这类对象应避免被 CPU 普通 load/store 提前带入 cache，或者避免
stream 写回后又由 CPU 从 stale cacheline 读取。

在 gem5 第一版中，这会影响 benchmark 设计：

- 输入数组初始化后要确保数据在 memory 中对 Stream Engine 可见；
- 输出数组校验前要确保 CPU 不会读到 stale cache 数据；
- 如果短期内难以精确模拟这套编程约束，可以先用 functional memory path
  跑通语义，再逐步替换为 timing memory port。

短期建议：

- `stream_vadd` bring-up 使用功能路径完成端到端自检。
- timing AXI 性能实验先要求 stream 数据区不被 CPU 普通 load/store 访问；
  如果 benchmark 必须由 CPU 初始化 / 校验，则先增加显式 flush / invalidate
  或使用无私有 cache 的 stream 专用配置进行对照。
- 在文档和实验说明中明确：direct AXI stream 对象需要由软件保证生命周期内
  不与 CPU cache 产生隐式一致性依赖。

### SSS ADD 算子

第一版只实现：

```text
dst = src0 + src1
```

但实现时要把 opcode/funct 或算子类型抽象出来，后续可以扩展：

- `ssr_add`
- `ssr_sub`
- `ssr_mul`
- PP 写回类指令

### `cfg_i(length)` 单位

当前以代码为准：软件传入的 `length` 是 word 总数。RTL 中：

```text
lengthMap = cfgLength / l2LineWord
```

因此 vector add 示例里的 `cfg_i(1, 512, fifo)` 表示该 stream 共有 512
个 word，硬件再根据每个半区 / cacheline 的 word 数转成 burst 数。

### Store 完成 / wait 语义

旧 `stream-add.c` 中没有显式 wait/drain 指令。第一版 gem5 如果要在同一个
benchmark 内校验 C 数组，需要提供一种完成语义：

- 功能模型阶段可以让 `sss_add` 或 stream engine 语义同步完成，保证循环后 C 已写回；
- timing 模型阶段建议新增或保留一个可选 wait/drain 机制，或者在 benchmark
  侧显式等待 stream store 队列清空。

## RTL 设计理解

### Stream / FIFO 结构

从 `Stream.scala` 当前代码看，Stream Engine 维护：

- `addrCfg`：每个 stream 的起始地址。
- `addrDyn`：当前动态访问地址。
- `strideCfg`：一个 tile 内相邻 word 的地址步长。
- `tileStrideCfg`：相邻 tile 首地址之间的步长。
- `reuseCfg`：load stream 中每个 word 被消费的次数。
- `lengthMap`：每轮要访问的 tile / burst 数，当前 RTL 中由 `cfg_i` 的 length 除以 `l2LineWord` 得到。
- `outerIterMap` / `oIterCntMap`：外层 block 计数。
- `burstCntMap`：当前 stream 已完成的 burst / tile 计数。
- `loadreadyMap`：load stream buffer 中每个 word 还有多少次可消费。
- `storereadyMap`：store stream buffer 中每个 word 是否已有待写回结果。
- `Fifo`：stream buffer 数据体。

文档中的抽象是：

```text
Stream -> Block -> Tile -> Word
```

第一版 vector add 只需要最简单情况：

```text
outerIter = 1
length = 元素总数
stride = 4
reuse = 1
两个 load stream: A, B
一个 store stream: C
```

### iCnt / 索引状态

RTL 中有两套普通索引状态：

- `specI`：dispatch 侧推测态。
- `archI`：commit 侧架构态。

它们由 `iLimitCfg` 和 `iRepeatCfg` 控制，可描述：

```text
[0, limit) 重复 repeat 次，然后进入下一个区间
```

第一版如果不接 CPU 流水线，可以先不区分 `specI` / `archI`，而是在
Stream Engine 内部用单个架构态计数器推进。这样会牺牲乱序 flush 精确性，
但能先跑通功能。

后续如果要接 CPU 流水线，需要把 `specI` / `archI` 恢复机制映射到 gem5 O3
的 rename / commit / squash 路径，这会明显复杂。

### V0 直连 AXI load

RTL V0 load 路径的核心语义：

1. 当某个 load stream 的某个半区全部 `ready == 0`，且还没超过配置次数，就可以发起读请求。
2. 一次 AXI 读请求读取一个 L2 cacheline 对应的半区。
3. 返回数据逐 word 写入 FIFO。
4. 每个写入 word 的 `ready` 置为 `reuseCfg`。
5. burst 完成后更新 `burstCntMap` 和 `addrDyn`。
6. 如果本轮 burst wrap，则更新 `oIterCntMap`。

第一版 gem5 适配可以把这建模为：

```text
load stream 半区空闲
  -> 生成一组 word 读请求
  -> 数据到达后写入 stream buffer
  -> ready = reuse
```

### V0 直连 AXI store

RTL store 路径的核心语义：

1. store stream 的某个半区全部 `ready == 1` 时可以写回。
2. 一次 AXI 写请求写回一个半区。
3. 写回时逐 word 清除 `storereadyMap`。
4. burst 完成后更新 store stream 的 `addrDyn` / `burstCntMap` / `oIterCntMap`。

第一版 vector add 只需要 fifo 2 作为 store stream。

### CALSTREAM / SSS 计算

`cal_stream(src0, src1, dst)` 的旧软件接口在 v0.6 指令集中对应 `sss_add`，
当前 vector add 示例中表示：

```text
dst[i] = src0[i] + src1[i]
```

执行时需要：

1. 检查两个 load stream 的对应 index ready > 0。
2. 检查 store stream 的对应 index ready == 0。
3. 读取 FIFO[src0][idx0] 和 FIFO[src1][idx1]。
4. 执行加法。
5. 写入 FIFO[dst][idx2]。
6. load ready 递减，store ready 置位。

第一版可以先只支持 SSS ADD。SSR ADD、更多 `op_id` 和 PP 类指令后续再做。

## 指令级 Difftest 评估

用户提出：是否需要做指令级 difftest，即 gem5 O3 每提交一条或多条指令时，
检查这条指令的写回结果，并与 golden 模型比对。即使 stream 指令不写通用
寄存器，也可以把 stream 侧写回结果取出来检查。

我的建议是：不要把它作为第一版功能跑通的前置条件，但应该从一开始预留
stream 语义事件日志，后续可以升级成 difftest。

原因：

- SSS 指令不写通用寄存器，传统“寄存器写回值 difftest”不够用。
- O3 会有推测执行、squash、重放；如果在 execute 阶段修改 Stream Engine，
  difftest 必须处理恢复问题。
- 如果第一版将 stream side effect 放到 commit 语义上，功能会更容易对齐，
  但 timing 精度会下降。
- golden 的来源尚未确定；直接做每条指令级 difftest 会先卡在 golden
  模型定义上。

建议分四阶段：

1. **端到端校验**
   先让 `stream_vadd` 最终输出数组与普通 C golden 相同。这是第一版必须做的。

2. **stream 事件级 trace**
   在 gem5 中记录每条已提交 stream 指令的语义事件：

   ```text
   commit_sn / pc / opcode
   cfg 写入了哪个 descriptor 字段
   sss_add 使用的 src fifo / dst fifo / index
   sss_add 读到的 src0/src1 值
   sss_add 产生的 dst 值
   stream load/store 写 memory 的地址和值
   ```

   这个 trace 可以先只用于调试，不阻塞正常模拟。

3. **stream semantic difftest**
   后续写一个轻量 golden interpreter，读取同一串 stream 语义事件或同一段
   benchmark 输入，逐条比对：

   ```text
   descriptor state
   iCnt state
   FIFO ready/value
   memory write addr/value
   ```

   这比“每条 O3 指令寄存器写回 difftest”更适合 stream engine。

4. **可选 O3 commit 级检查**
   如果后续要验证 stream 指令和 O3 推测执行的精确交互，再把检查挂到 O3
   commit 路径。普通 RISC-V 指令不需要重复 difftest；重点检查 stream custom
   指令的 architectural side effect：

   ```text
   CFG: descriptor 更新
   SSS: FIFO / store stream 写入
   SSR: rd 写回值
   load/store stream: memory 地址和值
   squash: 推测 side effect 是否被取消
   ```

第一版建议让 stream side effect 发生在 commit 语义之后，或者只在 commit
后变成 architectural state。这样最容易避免 O3 execute 阶段推测修改 FIFO
后又被 squash 的恢复问题。等功能稳定后，如果要更接近 RTL 的 `specI` /
`archI`，再引入 execute-time 推测态、commit 提交和 squash rollback。

结论：第一版先做端到端校验 + 可选事件 trace；等新编码和功能模型稳定后，
再做 stream semantic difftest。

## 新版指令编码 v0.6

当前实现以 `docs/指令集文档.md` v0.6 为准。所有 stream 指令仍使用
RISC-V R-type custom-0：

```asm
.insn r 0x0b, funct3, funct7, rd, rs1, rs2
```

### CFG

CFG 统一使用：

```text
opcode = 0x0b
funct3 = 000
funct7 = cfg_id
rd     = x0
rs1    = cfg_value
rs2    = fifo_id
```

| `cfg_id` / `funct7` | 指令 | `rs1` | `rs2` | 语义 |
| ---: | --- | --- | --- | --- |
| 0 | `cfg_iter` | `{length[15:0], outerIter[15:0]}` | `fifo_id` | 配置 block 数和 block 内 word 数 |
| 1 | `cfg_i_limit` | `limit` | `fifo_id` | 配置索引推进上限 |
| 2 | `cfg_i_repeat` | `repeat` | `fifo_id` | 配置局部重复次数 |
| 3 | `cfg_stride` | `stride` | `fifo_id` | 配置 word stride |
| 4 | `cfg_tilestride` | `tilestride` | `fifo_id` | 配置 tile stride |
| 5 | `cfg_reuse` | `reuse` | `fifo_id` | 配置每个 word 的复用次数 |
| 6 | `cfg_load` / `cfg_L2_load` | `base_addr` | `fifo_id` | 配置 L2/cache load stream |
| 7 | `cfg_axi_load` | `base_addr` | `fifo_id` | 配置 AXI load stream |
| 8 | `cfg_store` | `base_addr` | `fifo_id` | 配置 store stream |

### SSS / SSR

Compute 指令共用 `op_id`，其中 `funct7[6:5]` 保留为 0，
`funct7[4:0] = op_id`。

| 类别 | `funct3` | `rd` | `rs1` | `rs2` | 语义 |
| --- | ---: | --- | --- | --- | --- |
| SSS | `010` | `x0` | `{src1_fifo_id[1:0], src0_fifo_id[1:0]}` | `dst_fifo_id` | stream + stream -> stream |
| SSR | `111` | `result_reg` | `{src1_fifo_id[1:0], src0_fifo_id[1:0]}` | `x0` | stream + stream -> register |

第一版只实现 `op_id = 0x00` 的 ADD：

```text
SSS ADD: dst_fifo <- src0_fifo + src1_fifo
SSR ADD: rd       <- src0_fifo + src1_fifo
```

注意：`docs/指令集文档.md` 第 2 节一级分类表写的是 `SSR=110`、
`SSS=111`，但第 6/7 节和第 9 节宏定义写的是 `SSS=010`、`SSR=111`。
当前建议按详细章节和宏定义实现，也就是：

```text
STREAM_F3_CFG = 0x0
STREAM_F3_SSS = 0x2
STREAM_F3_SSR = 0x7
```

需要后续确认第 2 节表格是否是旧内容。

`codes_lib/software/stream_instr.h` 仍可作为旧版软件接口和语义参考，但不再作为
最终编码依据。

第一版建议只实现：

- `cfg_i`
- `cfg_i_limit`
- `cfg_i_repeat`
- `cfg_reuse`
- `cfg_stride`
- `cfg_tilestride`
- `cfg_axi_load`
- `cfg_store`
- `sss_add`

`cfg_load` 可先不支持，或暂时视为 `cfg_axi_load` 的别名，但需要用户确认。
`SSR ADD` 可作为第二个小目标实现，方便之后做 stream -> register 的结果检查。

## Vector Add 适配目标

`codes_lib/software/stream-add.c` 中的核心配置是：

```c
cfg_i(1, 512, 0);
cfg_i(1, 512, 1);
cfg_i(1, 512, 2);
cfg_reuse(1, 0);
cfg_reuse(1, 1);
cfg_i_limit(512, 0);
cfg_i_limit(512, 1);
cfg_i_limit(512, 2);
cfg_i_repeat(1, 0);
cfg_i_repeat(1, 1);
cfg_i_repeat(1, 2);
cfg_stride(4, 0);
cfg_stride(4, 1);
cfg_tilestride(128, 0);
cfg_tilestride(128, 1);
cfg_axi_load((uint32_t)a, 0);
cfg_axi_load((uint32_t)b, 1);
cfg_store((uint32_t)c, 2);

for (int i = 0; i < 512; i++) {
    sss_add(0, 1, 2);
}
```

第一版 benchmark 可以整理成项目内可编译的 `stream_vadd`：

- 使用当前 `benchmarks/vadd/vadd.c` 的初始化和校验风格。
- 将普通 `y[i] = a[i] + b[i]` 替换成 stream 配置加 `sss_add` 循环。
- `N` 默认可以先设为 512 或 1024。
- 如果 direct AXI 绕过 cache 导致普通 CPU 校验读到旧数据，需要先解决一致性问题。

## gem5 实现入口建议

### ISA decode

gem5 RISC-V 的 decode 入口在：

- `tools/gem5/src/arch/riscv/isa/decoder.isa`
- `tools/gem5/src/arch/riscv/isa/bitfields.isa`
- `tools/gem5/src/arch/riscv/isa/formats/*.isa`
- `tools/gem5/src/arch/riscv/insts/*.hh`
- `tools/gem5/src/arch/riscv/insts/*.cc`

应先在 `decoder.isa` 中添加 custom stream opcode 分支，再补对应
instruction class。当前先按 `docs/指令集文档.md` 的 v0.6 详细章节 /
宏定义实现 `CFG`、`SSS ADD`，后续再扩展更多 `op_id`。

### Stream Engine model

建议第一版新增一个 gem5 SimObject，暂名：

```text
StreamEngine
```

职责：

- 保存 stream descriptor。
- 保存 FIFO / ready map。
- 接收 stream 指令语义调用。
- 通过 request port 连接到 `system.membus`，近似 RTL 中直连 AXI。
- 维护 stream stats。

gem5 配置中新增：

```text
o3_stream_axi
```

大致连接：

```text
CPU custom stream instruction
  -> StreamEngine model
  -> system.membus
  -> MemCtrl / DRAM
```

暂不连接：

```text
StreamEngine -> L1 D-cache
StreamEngine -> L2 cache
```

### 建模层次选择

有两个可选层次：

| 层次 | 优点 | 风险 |
| --- | --- | --- |
| 功能模型 | 最快跑通，可先验证指令语义和 benchmark 正确性 | timing / memory traffic 不准 |
| timing SimObject + memory port | 更接近直连 AXI，可统计请求和 stall | 实现复杂，需要处理 O3 指令如何等待 engine ready |

建议顺序：

1. 先实现功能正确模型：stream 指令更新 engine 状态，engine 直接完成必要的数据搬运/计算。
2. 再加 timing memory port：load/store 通过 membus 发 packet，buffer ready 由响应驱动。
3. 最后再考虑 CALSTREAM 与 O3 issue / commit / squash 的精确耦合。

## 第一版 stats 建议

建议新增以下统计：

- `stream.cfgInsts`
- `stream.calInsts`
- `stream.loadStreamRequests`
- `stream.storeStreamRequests`
- `stream.loadWords`
- `stream.storeWords`
- `stream.computeOps`
- `stream.bufferFullStallCycles`
- `stream.bufferEmptyStallCycles`
- `stream.calStreamReadyCycles`
- `stream.calStreamStallCycles`
- `stream.bytesRead`
- `stream.bytesWritten`

如果第一版是功能模型，stall 类 stats 可先置 0 或只统计 engine 内部估算值。

## 需要重点确认的问题

1. `docs/指令集文档.md` 第 2 节和第 6/7/9 节的 `SSS` / `SSR`
   `funct3` 不一致。
   当前建议按 `SSS=010`、`SSR=111` 实现，需要确认表格是否需要修正。

2. direct AXI 使用虚拟地址还是物理地址？
   当前建议功能阶段用 `SETranslatingPortProxy`，timing 阶段在 stream engine
   发请求前做 VA->PA 翻译，再用物理地址访问 `system.membus`。

3. direct AXI 对象的编程约束如何在 benchmark 中表达？
   需要一个明确的 stream_vadd 写法，避免输入/输出数组被 CPU cache 路径污染。

4. `tileStride=128` 对 vector add 的原因是什么？
   对 32-word line 来说 128B 正好是一条 line。第一版可按这个理解实现，但需要确认。

5. `cfg_store` 是否也应支持 stride / tileStride？
   RTL store 写回里目前看起来 `addrDyn(2)` 按 `l2Line` 推进，没有用 `strideCfg(2)`。vector add 连续写没问题，后续更复杂 store 需要确认。

6. stream 数量和 FIFO 尺寸最终是多少？
   从代码看 vector add 至少用 0/1 load、2 store，FIFO 是两个 cacheline 规模。需要确认 `streamNum`、`l2LineWord`、`fifoWord` 的最终常量。

7. 是否需要保留 `cfg_load`？
   第一版只做 AXI，因此可以只支持 `cfg_axi_load`。如果软件仍会发 `cfg_load`，需要决定是否把它当成 AXI load。

8. 是否要在第一版里实现 `SSR ADD`？
    vector add 不需要，matmul inner-product 后续可能需要 stream -> register
    的写回结果。建议第一版先做 `SSS ADD`，`SSR ADD` 作为第二个小目标。

9. stream 指令是否需要 memory fence 语义？
    配置指令、load stream、store stream 与普通 CPU load/store 的顺序关系需要定义。第一版可以在软件侧插入明确的等待/完成指令，但当前 v0.6 指令集中没有看到 wait/fence。

10. stream kernel 如何知道所有 store 已写回完成？
    `stream-add.c` 中循环后没有显式 wait。RTL 可能依赖程序结束前自然 drain。gem5 benchmark 若要校验 C，需要一个可等待 stream 完成的机制，或者让 `sss_add` / `cfg_store` 模型同步完成。

11. 是否要把 stream semantic difftest 作为第二阶段目标？
    第一版建议只预留事件 trace；功能稳定后再引入 golden interpreter。

## 建议的下一步

1. 确认 `SSS` / `SSR` 的 `funct3` 冲突，以 v0.6 宏定义为优先候选。
2. 在项目中新增 `benchmarks/stream_vadd/`，使用 v0.6 header 编译。
3. 在 gem5 中加入 stream 指令 decode 和功能模型。
4. 新增 gem5 config：`o3_stream_axi_functional`。
5. 跑 `stream_vadd` 端到端自检，并输出 stream 事件 trace。
6. 再实现 timing direct AXI port 和 VA->PA 翻译拆页逻辑。
7. 新增 gem5 config：`o3_stream_axi_timing`。
8. 跑 `stream_vadd`，与 `o3_nopf` / `o3_stridepf` / `o3_stridepf_d8` /
   `o3_stridepf_l1d_l2_l3_d8` 对比。
9. 根据结果再决定是否实现内部多级流水和 stream semantic difftest。
