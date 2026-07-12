# Stream Engine v2c 异步访存建模计划

## 目标

v2c 的目标是在 v2b 的 readyMap 发射检查和 SSS 计算流水基础上，把 StreamEngine 的
访存侧改成内部异步状态机。

这里的“异步”不等于真实 timing AXI。v2c 先不接 AXI/cache port，只假设一个半区
refill/drain 需要固定 cycle。到达完成 cycle 后，StreamEngine 再更新 FIFO 和
readyMap。

## 为什么 v2c 很关键

v2a 的访存是同步功能模型：

```text
SSS 需要数据
  -> 当场 refill load buffer
  -> 当场计算
  -> store 半区满时当场 drain
```

这种模型能保证功能正确，但时序不可信，因为访存没有后台进度。

v2c 要改成：

```text
load 半区为空
  -> 发起异步 refill
  -> 过 refill_latency cycles 后填 FIFO / 设置 loadReadyMap

store 半区满
  -> 发起异步 drain
  -> 过 drain_latency cycles 后写 memory / 清 storeReadyMap

SSS
  -> 只看 readyMap
  -> 不 ready 就等
```

这样计算侧和访存侧就能并行推进，memory-bound kernel 的等待周期才有意义。

## 与 timing AXI 的关系

v2c 不实现真实 AXI 请求，也不连接 gem5 cache/memory port。

v2c 只建模：

- 访存请求什么时候发起；
- 哪个 FIFO 半区正在 refill/drain；
- 这个请求什么时候完成；
- 完成时如何更新 FIFO / readyMap / burst 状态；
- 计算指令因为 readyMap 不满足等待了多久。

真实 AXI/cache 接口放到 v2d。v2d 可以把 v2c 的固定 latency backend 替换成真实
timing port，而不用重写 readyMap 和 stream buffer 逻辑。

## 配置阶段约定

v2c 建议把 reset 语义收敛到 `cfg_iter`：

```text
cfg_iter:
    reset arch/spec index = 0
    reset FIFO data
    reset loadReadyMap / storeReadyMap
    reset addrDyn / burstCnt / outerIterCount
    清掉 pending refill/drain

cfg_stride / cfg_tilestride / cfg_reuse / cfg_i_limit / cfg_i_repeat:
    只改配置字段
    不 reset index
    不清 FIFO

cfg_load / cfg_axi_load / cfg_store:
    只设置 base/kind
    是否 reset 尽量避免；如果当前代码仍 reset，需要在 v2c 中整理掉
```

后续可以加 `cfg_done`，把配置阶段和流计算阶段明确隔开：

```text
cfg_done(fifo):
    标记该 fifo 配置完成
    之后访存状态机才允许对该 fifo 发起 refill/drain
```

如果 v2c 暂时不加新指令，也至少在文档和代码注释里约定：软件必须先完成所有 CFG，
再执行 stream compute。

## Load 异步 Refill

load stream 可以发起 refill 的条件：

```text
fifo.kind == Load
fifo.configDone == true   // 如果 v2c 实现 cfg_done
!memoryDone(fifo)
目标 segment 是 burstCnt % fifoSegNum
该 segment 的 loadReadyMap 全为 0
当前没有同一条 refill 通路的 pending load
```

stream0/stream1 共享一条 refill 通路，选择规则继续沿用 v2a：

```text
如果只有一个 stream 可 refill，选它
如果两个 stream 都可 refill，选 burstCnt 更小的
如果 burstCnt 相同，选 stream0
```

发起 refill 时不立刻写 FIFO：

```text
pendingLoad.valid = true
pendingLoad.fifoId = selected_fifo
pendingLoad.segment = selected_segment
pendingLoad.addr = addrDyn[selected_fifo]
pendingLoad.readyTick = cpu.clockEdge(refillLatency(segmentWords))
```

到完成事件触发后才完成：

```text
for off in 0 .. activeWords-1:
    data[segment][off] = memory[addr + off * 4]
    loadReadyMap[segment][off] = reuseCfg

清 pendingLoad
推进 addrDyn / burstCnt / outerIterCount
```

## Store 异步 Drain

store stream 可以发起 drain 的条件：

```text
fifo.kind == Store
fifo.configDone == true   // 如果 v2c 实现 cfg_done
目标 segment 是 burstCnt % fifoSegNum
该 segment 的 storeReadyMap 全为 1
当前没有 pending store drain
```

发起 drain 时不立刻写 memory，也不立刻清 storeReadyMap：

```text
pendingStore.valid = true
pendingStore.fifoId = store_fifo
pendingStore.segment = selected_segment
pendingStore.addr = addrDyn[store_fifo]
pendingStore.readyTick = cpu.clockEdge(drainLatency(segmentWords))
```

到完成事件触发后才完成：

```text
for off in 0 .. activeWords-1:
    memory[addr + off * 4] = data[segment][off]
    storeReadyMap[segment][off] = false

清 pendingStore
推进 addrDyn / burstCnt / outerIterCount
```

注意：如果软件在最后立刻用 CPU load 检查结果，而没有 stream wait 指令，v2c 可能需要
临时提供一个“仿真结束前 drain all”机制，或者后续补 `stream_wait`。否则最后一个
store 半区可能还在 pending。

## 异步事件模型

当前 v2c 使用 gem5 `EventFunctionWrapper` 建模后台访存进度，不再依赖 SSS 每次
ready check 手动推进 `virtualMemoryCycle`。

访存侧是一个配置完成后启动的周期性状态机：

```text
每个 CPU cycle 检查一次 stream buffer 状态
如果 load 半区为空且该 load stream 已配置完成，尝试发起 read refill
如果 store 半区满且该 store stream 已配置完成，尝试发起 write drain
read/write 完成事件到期后更新 FIFO / readyMap
```

这件事不由 `sssCanIssue()` 触发。`sssCanIssue()` 只看 readyMap 决定计算指令是否
可发射。SSS 计算写回或配置指令只是让 memory-side tick 保持调度，真正是否发请求
由 memory-side tick 自己判断。

读写通路分开建模：

```text
pendingRead  : 最多一个，多个 load stream 用简单 RR 选择
pendingWrite : 最多一个，store stream 满半区后发起

pendingRead 和 pendingWrite 可以同时存在
```

发起 pending 请求时，StreamEngine 会用 CPU 时钟把配置的 cycle 延迟转换成完成 tick：

```text
readyTick = tc->getCpuPtr()->clockEdge(latencyCycles)
```

这让 refill/drain 可以在 CPU 等待 SSS readyMap 的同时后台完成。它仍然不是真实
timing AXI，因为数据搬运本身仍通过 functional proxy 完成，只是完成时间由事件控制。

## 固定 Latency 参数

当前使用以下运行时配置参数：

```text
--stream-mem-burst-latency 176
--stream-mem-refill-latency 176
--stream-mem-drain-latency 176
--stream-mem-burst-words 32
```

其中 `--stream-mem-burst-latency` 是兼容/快捷参数；如果没有显式指定 refill/drain，
运行脚本会把它同时传给 refill 和 drain。

```text
refillLatency = stream_mem_refill_latency or stream_mem_burst_latency
drainLatency  = stream_mem_drain_latency  or stream_mem_burst_latency
```

本轮新增了 `mem_refill_latency`、`mem_drain_latency`、`mem_burst_words` 等
SimObject 参数，所以代码修改后需要重新 scons。后续如果只是改这些参数的命令行取值，
则不需要重新编译。

不同半区大小按 32-word burst chunk 放缩：

```text
latency = ceil(segmentWords / memBurstWords) * baseLatency
```

例如：

```text
64B  segment = 16 words -> 176 cycles
128B segment = 32 words -> 176 cycles
256B segment = 64 words -> 352 cycles
```

这不是带宽精确模型。176 cycles 的含义是：128B 连续半区约等于“一个 L2 miss
首包延迟 + 第二条连续 cache line 的较小增量”的乐观估计。后续 v2d 接 timing port
后，这个固定参数可以退化成 debug / fallback 参数。

读写通路不再用 load/store 优先级参数互斥仲裁；它们可以同时 pending。load 侧多个
FIFO 之间使用简单 RR。

## 与 SSS 的关系

SSS 不再触发同步 refill。

SSS 发射前只看 readyMap：

```text
loadReadyMap[src0][idx0] != 0
loadReadyMap[src1][idx1] != 0
storeReadyMap[dst][idxD] == false
```

ready 后，SSS 的 writeback：

```text
loadReadyMap[src0][idx0]--
loadReadyMap[src1][idx1]--
data[dst][idxD] = result
storeReadyMap[dst][idxD] = true
```

storeReadyMap 置位后，访存侧后台看到半区 full，再发起异步 drain。

## 统计项

v2c 已加入：

```text
memBurstStarts
loadBurstStarts
storeBurstStarts
memBurstBusyCycles
loadBurstBusyCycles
storeBurstBusyCycles
memoryTickCycles
sssReadyChecks
sssSourceStallCycles
sssDestStallCycles
```

已有的：

```text
loadRefills
storeDrains
fifoLoadConsumes
fifoStoreProduces
computeOps
```

可以继续保留，但含义要从“同步完成次数”更新为“异步请求完成次数”。

其中 `memBurstBusyCycles` 记录简化访存通路被 pending burst 占用的配置 cycle 数。

## 能得到什么时序数据

v2c 做完后，可以开始得到有意义的简化时序数据：

- stream 计算因为 load 数据未到而等待的周期；
- stream 计算因为 store buffer 满而等待的周期；
- load refill / store drain 与计算的重叠效果；
- segment size、reuse、refill latency 对总周期的影响；
- memory-bound kernel 的趋势性性能。

但 v2c 结果仍需注明：

```text
这是 StreamEngine 内部 fixed-latency async memory model。
它不是完整 timing AXI/cache model。
```

因此 v2c 适合做设计趋势和机制验证。若要和真实系统或论文中的 AXI/cache 配置严肃对比，
还需要 v2d 的 timing port / cache 接口。

## 完成标准

v2c 最小完成标准：

1. `stream_vadd_N1024` 功能正确。
2. load refill 不再由 SSS 同步触发，而是 pending 后完成。
3. store drain 不再同步清 readyMap，而是 pending 后完成。
4. SSS 因 source not ready / dst full 能产生等待统计。
5. 修改 refill/drain latency 会改变等待统计和简化总周期。
6. 文档记录 v2c 仍未接真实 AXI/cache。

## 后续 v2d

v2d 再做：

- timing AXI / memory port；
- cache/L2 接口；
- AXI request/response 与 pendingLoad/pendingStore 对接；
- stream wait / drain 指令；
- 更真实的带宽和仲裁建模。
