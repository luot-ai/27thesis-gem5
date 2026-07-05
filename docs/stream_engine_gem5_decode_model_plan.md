# Stream Engine gem5 Decode / Functional Model 适配方案

## 目的

本文专门细化 `docs/stream_engine_gem5_adapt_plan.md` 中的 Step 3/4：

1. 在 gem5 RISC-V decoder 中识别 stream custom 指令。
2. 把所有 stream 指令的语义转交给 StreamEngine。
3. 第一版用 functional model 跑通 `stream_vadd`。

第一版目标不是复现完整时序，而是形成一个能编译、能 decode、能跑通自检的
闭环。后续再逐步替换为 timing direct AXI port。

## 当前拍板边界

- RISC-V custom-0 opcode：`0x0b`。
- gem5 decoder 顶层按 `QUADRANT` 和 `OPCODE5` 分解 opcode。
- `0x0b` 的低两位是 `11`，所以 `QUADRANT=0x3`。
- `0x0b >> 2 = 0x02`，所以应在 `decode OPCODE5` 的 `0x02` 分支加入 stream。
- 不要误把 `decoder.isa` 中已有的 `0x0b: decode FUNCT3` 当成 custom-0；
  那段位于其他 opcode 分支下，是 AMO/向量相关路径。

v0.6 stream 分类：

| 类别 | `funct3` | 第一版动作 |
| --- | ---: | --- |
| CFG | `000` | 更新 StreamEngine descriptor/config register |
| SSR | `110` | stream + stream -> register，第二小目标 |
| SSS | `111` | stream + stream -> stream，第一版只做 ADD |

第一版必须支持：

- `cfg_iter`
- `cfg_i_limit`
- `cfg_i_repeat`
- `cfg_stride`
- `cfg_tilestride`
- `cfg_reuse`
- `cfg_axi_load`
- `cfg_store`
- `sss_add`

`cfg_load` 可以先报 unsupported，或者临时映射为 `cfg_axi_load`。建议实现时先
映射为 `cfg_axi_load` 并在 stats/debug 中计数，方便兼容旧测试。

## Decoder 接入方案

### 文件入口

主要改动位置：

- `tools/gem5/src/arch/riscv/isa/decoder.isa`
- `tools/gem5/src/arch/riscv/isa/includes.isa`
- 可选：`tools/gem5/src/arch/riscv/isa/formats/stream.isa`
- 可选：`tools/gem5/src/arch/riscv/isa/formats/formats.isa`

第一版可以不新建复杂 format，直接复用 `ROp` 风格生成 StaticInst：

```text
decode QUADRANT {
  0x3: decode OPCODE5 {
    0x02: decode FUNCT3 {
      0x0: decode FUNCT7 {
        0x00: stream_cfg_iter(...)
        0x01: stream_cfg_i_limit(...)
        ...
      }
      0x6: stream_ssr(...)
      0x7: stream_sss(...)
    }
  }
}
```

因为所有 stream 指令都是 R-type，`ROp` 已经能提供 `Rs1`、`Rs2`、`Rd` 的
读写框架。CFG/SSS 不写通用寄存器；SSR 写 `Rd`。

如果 `ROp` 直接写起来太散，第二步再抽一个 `StreamOp` format，把公共的
engine lookup、非法 `funct7` 检查和 disassembly 收进去。

### 指令执行形态

所有 stream 指令都不在 ISA execute 代码里自己实现语义，而是转发给
StreamEngine：

```text
CFG execute:
  engine.cfg(kind, fifo_id=Rs2, value=Rs1, pc, seq/context)

SSS execute:
  src0 = Rs1[1:0]
  src1 = Rs1[3:2]
  dst  = Rs2
  op   = FUNCT7[4:0]
  engine.sss(op, src0, src1, dst, pc, context)

SSR execute:
  src0 = Rs1[1:0]
  src1 = Rs1[3:2]
  op   = FUNCT7[4:0]
  Rd = engine.ssr(op, src0, src1, pc, context)
```

第一版只接受 `op=ADD`。其他 `op_id` 可以返回 illegal instruction 或 panic；
建议返回 illegal instruction，便于测试定位。

## StreamEngine 放置方案

### 第一版建议

第一版实现一个 functional StreamEngine C++ 类，后续再包装为正式 SimObject。
推荐文件：

- `tools/gem5/src/stream/StreamEngine.py`
- `tools/gem5/src/stream/stream_engine.hh`
- `tools/gem5/src/stream/stream_engine.cc`
- `tools/gem5/src/stream/SConscript`

Python config 中创建：

```python
system.stream_engine = StreamEngine()
```

ISA execute 侧通过 `xc->tcBase()` 拿到 `ThreadContext`，再由 StreamEngine 的
registry 找到当前 system 对应的 engine：

```text
engine = StreamEngine::get(xc->tcBase()->getSystemPtr())
```

如果第一版为了少改 SimObject 体系，也可以先做一个 per-system singleton
functional engine；但是接口仍然按 `StreamEngine::get(system)` 写，避免之后
从 singleton 切到 SimObject 时重写 ISA 代码。

### 为什么不把语义写在 decoder 里

decoder / StaticInst 只负责：

- 解码字段；
- 读取 `Rs1/Rs2`；
- 写回 SSR 的 `Rd`；
- 把语义请求交给 engine。

StreamEngine 负责：

- descriptor/config register；
- FIFO/ready；
- 地址计算；
- functional memory read/write；
- pipeline latency bookkeeping；
- stats 和事件 trace。

这样后续从 functional model 换成 timing AXI port 时，decoder 基本不动。

## Functional Model 状态

第一版可以先固定 4 个 FIFO，足够覆盖 vector add：

```text
fifo 0: load A
fifo 1: load B
fifo 2: store C
fifo 3: reserved
```

每个 FIFO descriptor：

```text
base_vaddr
kind: none / axi_load / l2_load / store
outer_iter
length_words
i_limit
i_repeat
stride_bytes
tile_stride_bytes
reuse
arch_index
ready[]
values[]
```

第一版 `stream_vadd` 只需要线性模式：

```text
outer_iter = 1
length_words = N
i_limit = N
i_repeat = 1
stride_bytes = 4
reuse = 1
```

`tile_stride_bytes` 先记录下来，不必影响线性地址计算。后续做 block/tile 模式
时再使用。

## CFG 指令语义

所有 CFG 指令都更新 engine 内部寄存器：

| CFG | 动作 |
| --- | --- |
| `cfg_iter` | 拆 `outerIter=value[15:0]`、`length=value[31:16]` |
| `cfg_i_limit` | 写 `i_limit` |
| `cfg_i_repeat` | 写 `i_repeat` |
| `cfg_stride` | 写 `stride_bytes` |
| `cfg_tilestride` | 写 `tile_stride_bytes` |
| `cfg_reuse` | 写 `reuse` |
| `cfg_axi_load` | 写 `base_vaddr`，标记 FIFO 为 load |
| `cfg_store` | 写 `base_vaddr`，标记 FIFO 为 store |

CFG 第一版可以同步完成，不引入额外延迟。后续可加 `cfgInsts` stats。

## SSS ADD Functional 语义

`sss_add(src0, src1, dst)` 的第一版执行流程：

1. 检查 `src0/src1` 是 load FIFO，`dst` 是 store FIFO。
2. 取三个 FIFO 的 `arch_index`。
3. 根据 `base_vaddr + index * stride_bytes` 计算源/目的虚拟地址。
4. 用 `SETranslatingPortProxy` 或等价 process memory helper 读两个 `int32_t`。
5. 执行 `int32_t result = a + b`。
6. functional 阶段立即把 result 写到目的地址，保证 benchmark 后续自检可见。
7. 更新 `arch_index`、ready/value 影子状态和 stats。

即使第一版直接读写 memory，也保留 FIFO/ready 的影子状态。这样 trace 和后续
timing port 可以沿用同一套 descriptor。

## Pipeline Latency 建模

用户提示：计算指令可以模拟 pipelined 延迟。建议分两层：

### 第一版 functional latency

功能结果仍同步可见，但 engine 内部维护一条虚拟流水线：

```text
compute_latency_cycles = 3  # 可配置
compute_initiation_interval = 1
next_issue_tick
last_complete_tick
```

每次 `sss_add`：

```text
issue_tick = max(curTick(), next_issue_tick)
complete_tick = issue_tick + compute_latency_cycles * clock_period
next_issue_tick = issue_tick + initiation_interval * clock_period
last_complete_tick = max(last_complete_tick, complete_tick)
```

stats / trace 记录 issue/complete tick，但 functional 写回仍立即发生。这样先能
跑通自检，也能观察 engine 内部流水线利用情况。

### 第二版 timing latency

当有 wait/drain 或 timing direct AXI port 后，再让 store 对 CPU 可见时间受
`complete_tick` 控制。否则没有 wait 指令时，CPU 可能在 stream store 完成前
立刻读 C 数组，导致自检和真实异步模型打架。

换句话说：第一版把 pipeline latency 当 engine 内部统计；第二版再让它影响
程序可观察时间。

## 地址翻译和内存访问

第一版 functional model 使用 SE-mode 翻译路径：

```text
ThreadContext -> Process -> EmulationPageTable / SETranslatingPortProxy
```

这不是目标硬件里的 TLB。它只是 gem5 SE-mode 下把 C 程序虚拟地址映射到
gem5 内部物理内存的适配层。

第一版不要直接绕开这个层，否则 `a/b/c` 的用户态地址无法稳定对应 memory。

第二版 timing direct AXI：

```text
stream base virtual address
  -> page-aware VA->PA in StreamEngine adapter
  -> physical Request packet
  -> system.membus
```

跨 page 的 burst 必须拆分。

## 事件 Trace

第一版建议加入可选 trace，不作为 pass/fail 条件：

```text
CFG fifo=0 field=stride value=4 pc=...
SSS issue op=add src0=0 src1=1 dst=2 idx=17 a=17 b=35 result=52
STORE fifo=2 addr=... value=52
```

trace 可以先用 debug flag 或简单 stats 文件控制。不要在默认运行中输出海量
文本。

## 与 O3 推测执行的关系

第一版为了降低风险，建议把 stream side effect 视为 execute 时同步发生的
functional side effect，并先用简单 benchmark 验证。这个模型不严格处理 O3
squash。

如果后续要严肃处理推测执行，有两条路线：

1. 在 execute 阶段只写 speculative state，commit 阶段再提交到 arch state。
2. 继续 execute 阶段修改 engine，但为每条 stream 指令记录 undo log，squash
   时回滚。

更推荐第一条，但它需要接 O3 commit 路径，复杂度高。第一版先不做。

## 最小验收标准

第一版 Step 3/4 完成时，应满足：

1. `stream_vadd` 的 custom-0 指令不再触发 illegal instruction。
2. `cfg_*` 指令能更新 StreamEngine descriptor。
3. `sss_add` 能通过 engine 完成 A+B->C。
4. `stream_vadd` 在 `o3_stream_axi_functional` 下自检通过。
5. stats 至少包含 `stream.cfgInsts`、`stream.sssInsts`、`stream.loadWords`、
   `stream.storeWords`、`stream.computeOps`。

## 对 Step 1/2 的并行拆分

Step 1 和 Step 2 可以开 subagent 并行做，但要限定写入范围：

- Header subagent：只写 `benchmarks/common/stream_instr_v06.h`。
- Benchmark subagent：只写 `benchmarks/stream_vadd/stream_vadd.c`。

集成时再由主线程统一修改：

- `scripts/build_benchmarks.sh`
- README 或实验说明；
- 后续 gem5 config。

这样两个 subagent 不会互相覆盖，也不会碰 gem5 decoder/model 的核心代码。
