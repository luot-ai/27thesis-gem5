# Stream Engine v2b 时序适配计划

## 目标

v2b 的目标是在 v2a 的 ping-pong buffer / ready map 功能模型上，加入最小可用的
时序等待行为。

v2b 暂时不追求完整 AXI/cache timing，而是先让 stream 指令不再“无代价地同步补齐
访存”。当 source stream buffer 没 ready 或 destination stream buffer 满时，模型
需要体现等待。

## 测试范围

v2b-a 阶段先不补充新 directed tests，也不补非整半区测试。先继续使用已经跑通的
`stream_vadd_N1024`，避免在改时序模型时同时扩大测试变量。

后续需要补测试时，再优先补整半区参数组合：

- `stream_vadd_N1024`
- `stream_segment_bytes=64`
- `stream_segment_bytes=128`
- `stream_segment_bytes=256`

这些配置都能整除 `N=1024`，足够先验证不同半区大小下 refill/drain 次数和结果正确。

## O3 Issue 语义

长期目标是让 stream 指令像普通指令一样进入 O3：

```text
fetch -> decode -> rename -> issue queue -> read operands -> execute -> commit
```

区别在于普通指令 issue 前主要检查物理寄存器是否 ready，而 stream 计算指令还需要
检查 stream buffer ready map：

```text
source load stream:
    readymap[src_fifo][src_index] > 0

destination store stream:
    store_ready[dst_fifo][dst_index] == 0
```

如果 source 没 ready 或 destination 已满，stream 计算指令应该等待，而不是在执行
函数里直接把访存同步做完。

## v2b 实现方向

v2b 不额外补一个 `stream_compute_lanes` 近似参数。更直接的做法是在 IQ 发射逻辑里
增加 stream ready 条件：普通指令检查物理寄存器 ready，stream 计算指令额外检查
stream buffer ready map。

当前 stream 指令仍标记为 `IsNonSpeculative`，因此 v2b 仍然会保留“到 ROB 头部附近
才真正执行”的保守语义。即便如此，IQ 发射前也应该先检查 ready map；不满足条件时，
这条 stream 计算指令不能调用 `StreamEngine::sssAdd(...)`。

当前 non-spec 路径大致是：

```text
dispatch:
    stream 指令进入 IQ 的 nonSpecInsts

commit:
    stream 指令到 ROB head
    commit 发送 nonSpecSeqNum 给 IEW

IEW / IQ:
    scheduleNonSpec(nonSpecSeqNum)
    检查 stream ready map
    ready 后才发射并调用 StreamEngine::sssAdd(...)
```

也就是说，v2b 的 ready map 发射检查仍发生在 commit 通知 IEW 之后。后续把 stream
指令定义为 SE FU 普通发射后，才能把这个检查提前到常规 issue 选择路径中。

SSS 指令的 ready 条件参考 RTL：

```text
src0_idx = src0_iterCnt % fifoWord
src1_idx = src1_iterCnt % fifoWord
dst_idx  = dst_iterCnt  % fifoWord

ready =
    loadreadyMap[src0][src0_idx] != 0
 && loadreadyMap[src1][src1_idx] != 0
 && storereadyMap[dst_idx] == false
```

如果不 ready：

- source load FIFO 未 ready：等待 refill 侧把对应 word 写入 buffer 并设置
  `loadreadyMap`；
- destination store FIFO 满：等待 store drain 侧清掉对应 `storereadyMap`；
- 指令留在 IQ / non-spec ready 路径中等待；
- 等待周期计入 stream compute stall 统计。

如果 ready，则 IQ 才允许发射该 SSS。`StreamEngine::sssAdd(...)` 建模为 3-cycle
pipelined 计算路径：

```text
cycle 0: readop    从 source FIFO 读两个操作数
cycle 1: calculate 执行 add
cycle 2: writeback 更新 ready map，并把结果写入 destination FIFO
```

writeback 对 ready map 的影响参考 RTL：

```text
loadreadyMap[src0][src0_idx]--
loadreadyMap[src1][src1_idx]--
Fifo[dst][dst_idx] = result
storereadyMap[dst_idx] = true
```

这三段计算路径是 pipelined 的：每条 SSS 有 3-cycle latency，但可以按配置的
initiation interval 连续接收已经 ready 的 SSS。由于 v2b 仍保持当前 non-spec 执行
边界，实际可观察到的 stream 计算发射宽度仍受当前 O3/non-spec 路径限制；这里不再
额外用 `stream_compute_lanes` 人为扩展。

初始假设：

```text
refill 一个 32-word burst: 50 cycles
drain  一个 32-word burst: 50 cycles
stream add pipeline latency: 3 cycles
stream add initiation interval: 沿用当前 initiation_interval 参数
```

对于不同 `stream_segment_bytes`，可以先按 word 数线性放缩：

```text
burst_cycles = ceil(segment_words / 32) * 50
```

v2b-a 需要维护：

- load refill 的开始/完成 cycle；
- store drain 的开始/完成 cycle；
- compute 指令因为 source not ready 等待的 cycle；
- compute 指令因为 destination full 等待的 cycle；
- SSS readop/calculate/writeback 的内部 pipeline cycle；
- refill/drain 的次数和总周期统计。

这个版本仍然可以不真实占用 gem5 memory port，但统计中必须能看出等待来自哪里。它比
v2a 更可信，因为 ready map 的生产/消费时序已经被建模；但它仍不是最终 O3 紧耦合
模型，因为 stream 指令还没有作为 SE FU 普通发射。

## 后续工作

v2b 之后再补下面几类更完整的机制。

### 1. 错误路径恢复与 SE FU 发射

- 增加错误路径恢复机制；
- 在 dispatch 阶段配合 `icntmap` 动态获取 program-order index；
- 把 stream 指令定义为发射到 SE 这个 FU；
- 这样 stream 计算指令不必等到 ROB 队头才发射；
- ready 条件仍然来自 stream ready map，而不是通用物理寄存器。

### 2. 真实 AXI 接口

- refill/drain 不再使用固定 burst latency；
- 通过真实 timing AXI / memory port 发请求；
- stall、带宽、仲裁由访存接口自然产生。

### 3. Stream 指令接入 CPU 流水线

Issue 的 ready 条件和 dispatch 获取 index 完成后，还需要继续把 stream 计算指令接入
更完整的流水线：

- 不同 stream op 发射到不同 SE 功能单元；
- 操作数来自 stream buffer，而不是通用寄存器堆；
- writeback 更新 stream buffer / ready map，不写通用寄存器；
- SSS/SSR/后续扩展 op 可以分别映射到合适的 SE FU。

## Refill / Drain

最终如果接上 timing memory/cache/AXI port，refill/drain 会天然产生 stall 和带宽竞争。

v2b 暂时先用固定延迟模拟：

- refill 由 StreamEngine 访存侧发起；
- drain 由 store buffer 半区满触发；
- 同一条直连 AXI 路径上 stream0/stream1 refill 仍按 v2a 的 `burstCnt` 竞争规则；
- store drain 先按 RTL 风格处理 stream2；
- 暂时不建真实 AXI request，也不接 L2/cache port。

## 暂不处理

v2b 暂不处理：

- 非整半区 directed test；
- 真实 timing AXI request；
- L2 cache port 连接；
- cache coherence；
- CFG 指令错误路径恢复；
- store commit buffer；
- AXI 写请求取消队列；
- PP/FFT 路径。

这些可以留到 v2c 或之后。

## 完成标准

v2b 最小完成标准：

- `stream_vadd_N1024` 在 `64B/128B/256B` 半区下结果正确；
- stats 能看到 refill/drain 次数；
- stats 能看到 stream compute 等待周期；
- 改变固定 burst latency 会影响总模拟周期或 stream engine timing 统计；
- 文档明确说明该结果是简化 timing model，不是完整 AXI/cache timing。
