# Stream Engine v2a 双半区访存模型计划

## 目标

v2a 的目标不是让 stream 指令立刻乱序执行，而是先把当前
`stream_engine.cc` 中“计算指令直接读写内存”的功能模型，改成更接近 RTL 的
stream buffer 访存模型：

- 每个 stream 使用一个双半区 ping-pong buffer；
- load stream 由访存侧 refill buffer，计算指令只从 buffer 读；
- store stream 由计算指令写入 buffer，访存侧在半区满后 drain 到内存；
- CFG 指令和计算指令暂时继续保持 non-speculative；
- 暂时不做 PP/FFT 路径，不做 timing AXI，不做 L2 cache 端口连接。

## gem5 Cacheline 与 Stream 半区大小

当前仓库的 gem5 运行脚本默认 cacheline 是 64B：

- `scripts/run_gem5.py` 中 `--cache-line-size` 默认值是 `64`；
- `gem5_configs/riscv_o3_baseline.py` 把该值写入 `system.cache_line_size`；
- 最新一次 `stream_vadd_N1024/o3_stream_axi_functional/run_metadata.json` 也记录了
  `"cache_line_size": 64`。

v2a 中 gem5 O3 的 cacheline 保持不动，仍然是 64B。stream engine 的双半区大小
不要再强行等同于 gem5 cacheline，而是单独做成 stream engine 参数。

建议 v2a 先使用：

```text
gem5 cacheline bytes       = 64 B
stream segment bytes       = 128 B
word bytes                 = 4 B
streamSegmentWords         = 128 / 4 = 32 words
fifoSegNum                 = 2
fifoWord                   = 2 * streamSegmentWords = 64 words
```

也就是说，文档和 RTL 里常用的 `l2LineWord` 在 v2a 代码里最好改名为
`streamSegmentWords` 或 `segmentWords`，避免误解成 gem5 的 cacheline word 数。
如果为了贴近 RTL 代码暂时沿用 `l2LineWord` 这个名字，也必须在注释中说明：
它表示 stream buffer 一个半区的 word 数，不表示 gem5 cacheline 的 word 数。

## Buffer 结构

v2a 中每个 stream descriptor 除了现有配置字段外，还需要维护：

```text
data[fifoWord]       // 64 个 int32 word，分 line0/line1
loadReady[fifoWord]  // load stream 使用，表示每个 word 还可被消费几次
storeReady[fifoWord] // store stream 使用，表示每个 word 是否已有待写回结果
```

半区划分：

```text
line0: index 0  .. streamSegmentWords-1
line1: index streamSegmentWords .. 2*streamSegmentWords-1

slot = iterCnt % fifoWord
seg  = slot / streamSegmentWords
off  = slot % streamSegmentWords
```

其中 stream0/stream1 先作为 load stream，stream2 先作为 store stream。

## Load Refill 与 FIFO 竞争规则

load stream 某个半区可以 refill 的条件：

- 该 stream 已经通过 `cfg_axi_load` 或 `cfg_load` 配置为 load；
- 对应半区内所有 `loadReady` 都为 0；
- 该 stream 还没有完成配置的 line/burst 数；
- 对直连 AXI 路径，v2a 暂时只支持连续 word stream，即每个 word 地址按 4B 递增。

v2a 可以先模拟 FIFO 之间的简单竞争，不需要真实 timing AXI。参考 RTL 中
`LoadSelect` 的策略：

```text
fifo0Valid = stream0 存在可 refill 半区
fifo1Valid = stream1 存在可 refill 半区

pick1 = fifo1Valid && (!fifo0Valid || burstCnt[1] < burstCnt[0])

如果 pick1:
    本轮 refill stream1
否则:
    本轮 refill stream0
```

也就是说：

- stream0 和 stream1 之间共享一条直连 AXI refill 通路；
- 如果只有一个 stream 有空半区，就选它；
- 如果两个 stream 都有空半区，优先选 `burstCnt` 更小的那个，让两个 load stream
  的 refill 进度尽量保持平衡；
- 如果 `burstCnt` 相同，按 RTL 表达式会优先 stream0。

半区选择也按 RTL 思路：

```text
seg 可 refill 条件:
    segmentReadyAllZero(stream, seg)
    && stream 已配置完成
    && stream 是 load stream
    && (burstCnt[stream] % fifoSegNum == seg)
    && oIterCnt[stream] != outerIter[stream]
```

在 `fifoSegNum = 2` 时，`burstCnt` 的低位决定本轮应填 line0 还是 line1：

```text
burstCnt even -> line0
burstCnt odd  -> line1
```

refill 一个半区时：

```text
for off in 0 .. streamSegmentWords-1:
    data[seg*streamSegmentWords + off] = memory[addrDyn + off*4]
    loadReady[seg*streamSegmentWords + off] = reuseCfg
```

随后更新：

```text
burstCnt++
addrDyn += tileStrideBytes
```

这里按你现在对 RTL 的判断：直连 AXI 路径不支持非连续 stride stream，因此
`cfg_stride` 不参与 AXI refill 的逐 word 地址生成。v2a 先要求 AXI load stream
是连续 32-bit word，即等价于 `strideBytes == 4`。

## Store Drain 规则

store stream 某个半区可以 drain 的条件：

- 该 stream 已经通过 `cfg_store` 配置为 store；
- 对应半区内所有 `storeReady` 都为 1。

drain 一个半区时：

```text
for off in 0 .. streamSegmentWords-1:
    memory[addrDyn + off*4] = data[seg*streamSegmentWords + off]
    storeReady[seg*streamSegmentWords + off] = 0
```

随后更新：

```text
burstCnt++
addrDyn += streamSegmentBytes
```

store stream 先按 RTL 行为实现：

- 只有 stream2 作为普通 store stream；
- `storeSegSel = PriorityEncoder(wFifoSegFull)`，选择已经全满的半区；
- 写回过程中每接受一个 word，就清掉对应 `storeReady`；
- 一个半区写完后，`addrDyn(2)` 按 `streamSegmentBytes` 推进；
- 如果 `(burstCnt(2) + 1) == lengthMap(2)`，则回到 `addrCfg(2)`，`burstCnt(2)`
  清零，`oIterCnt(2)` 递增。

`stream_vadd_N1024` 在 `streamSegmentBytes=128B` 时正好是
`1024 / 32 = 32` 个完整半区。

## 计算指令行为

`sss_add(src0, src1, dst)` 在 v2a 中不再直接访问内存。

执行流程：

```text
idx0 = src0.iterCnt % fifoWord
idx1 = src1.iterCnt % fifoWord
idxD = dst.iterCnt  % fifoWord

要求:
    loadReady[src0][idx0] > 0
    loadReady[src1][idx1] > 0
    storeReady[dst][idxD] == 0

执行:
    result = data[src0][idx0] + data[src1][idx1]
    data[dst][idxD] = result
    loadReady[src0][idx0]--
    loadReady[src1][idx1]--
    storeReady[dst][idxD] = 1
    src0.iterCnt++
    src1.iterCnt++
    dst.iterCnt++
```

因为 v2a 仍然保持 non-speculative，暂时可以在 `sss_add` 执行前同步调用
`serviceMemory()`，确保需要的 load 半区已经 refill，并在 store 半区满时同步
drain。等 v2a 跑通后，再考虑让 ready 检查影响 O3 issue/stall。

当前代码实现没有单独暴露一个 `serviceMemory()` 函数，而是在计算指令路径上做
按需服务：

- `consumeLoad()` 发现目标 word 未 ready 时，调用 `serviceLoadsUntilReady()`；
- `serviceLoadsUntilReady()` 每次只通过共享 refill 通路补一个 load 半区；
- `sss_add()` 把结果写入 store buffer 后，调用 `drainReadyStoreSegments()`；
- store 半区满后同步 drain 到 SE-mode 内存。

## 与当前 v1 的差别

当前 v1：

```text
sss_add:
    a = memory[src0.addr + src0.iterCnt * stride]
    b = memory[src1.addr + src1.iterCnt * stride]
    memory[dst.addr + dst.iterCnt * stride] = a + b
```

v2a：

```text
memory -> load buffer -> sss_add -> store buffer -> memory
```

这一步的关键价值是把 stream engine 的访存状态显式建出来，为后续 OoO stream
指令做准备。

## 暂不实现

v2a 暂时不实现：

- PP buffer / FFT 写回另一条 line；
- calstream 进入 CPU 普通流水级计算；
- timing AXI 请求、带宽、仲裁延迟；
- L2 cache port 连接和 cache coherence；
- stream 指令乱序执行；
- 错误路径上的 FIFO 回滚。

## 当前实现状态

已实现的代码位置：

- `tools/gem5/src/stream/StreamEngine.py`：新增 `stream_segment_bytes` 参数，默认
  `128`；
- `tools/gem5/src/stream/stream_engine.hh/.cc`：新增双半区 buffer、load refill、
  store drain、stream0/stream1 refill 竞争和相关统计；
- `gem5_configs/riscv_o3_baseline.py`：把 `--stream-segment-bytes` 传入
  `StreamEngine`；
- `scripts/run_gem5.py`、`scripts/run_batch.py`：新增
  `--stream-segment-bytes` 参数，默认 `128`。

当前实现选择：

- 代码中使用 `streamSegmentBytes` / `streamSegmentWords`，不再使用容易误解的
  `l2LineWord` 命名；
- `cfg_iter` 的高 16 位仍表示 `lengthWords`，半区数量在模型内用
  `ceil(lengthWords / streamSegmentWords)` 计算；
- 直连 AXI load 暂时只支持连续 32-bit word stream，即 `strideBytes == 4`；
- load refill 地址按 `addrDyn + off * 4` 生成，一个半区结束后
  `addrDyn += tileStrideBytes`，一轮结束后回到 `base`；
- store drain 地址按 `addrDyn + off * 4` 生成，一个半区结束后
  `addrDyn += streamSegmentBytes`，一轮结束后回到 `base`；
- 当前仍保持 stream 指令 non-speculative，计算指令不会绕过提交边界乱序修改
  stream engine 状态。

## 验证结果

已重新编译：

```text
scons build/RISCV/gem5.opt -j2 --linker=lld
scons: done building targets.
```

已运行：

```text
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/stream_vadd_N1024.riscv \
  --bench-name stream_vadd_N1024 \
  --config o3_stream_axi_functional \
  --stream-segment-bytes 128
```

结果目录：

```text
results/stream_vadd_N1024/o3_stream_axi_functional
```

程序输出：

```text
stream_vadd passed N=1024
```

关键统计：

```text
system.stream_engine.cfgInsts              21
system.stream_engine.sssInsts            1024
system.stream_engine.loadWords           2048
system.stream_engine.storeWords          1024
system.stream_engine.loadRefills           64
system.stream_engine.storeDrains           32
system.stream_engine.fifoLoadConsumes    2048
system.stream_engine.fifoStoreProduces   1024
system.stream_engine.computeOps          1024
system.stream_engine.unsupportedInsts       0
```

在 `streamSegmentBytes=128B`、`streamSegmentWords=32` 时：

- 每个 load stream 需要 `1024 / 32 = 32` 次 refill；
- 两个 load stream 合计 `64` 次 refill；
- store stream 需要 `1024 / 32 = 32` 次 drain；
- load/store word 数分别是 `2 * 1024 = 2048` 和 `1024`。

## v2b 建议目标

v2a 解决的是“访存状态在哪里、FIFO 如何 refill/drain、不同 load FIFO 如何竞争”。
v2b 建议解决的是“O3 里的 stream 计算指令什么时候能发射、什么时候应该等
stream buffer ready”。

建议 v2b 不再扩大功能范围，而是聚焦这些点：

- 保持 CFG 指令 non-speculative，继续假设 CFG 不出现在错误路径上；
- stream 计算指令开始尝试按普通 O3 指令的方式进入 issue/execute；
- 发射前检查 source load FIFO 的 ready map 和 destination store FIFO 的空位；
- source 未 ready 或 destination 满时，让指令等待，而不是像 v2a 一样在函数里同步
  补齐所有访存；
- 计算完成后更新 FIFO ready 状态，store drain 仍由 stream engine 访存侧触发；
- 暂时仍不实现 timing AXI、L2 cache 端口、完整错误路径 FIFO 回滚。

因此，v2b 的核心不是新增更多 stream 指令，而是把 v2a 的功能 buffer 模型接进
O3 的调度/等待行为里。真正完整的错误路径取消、store commit buffer、AXI 请求取消
队列，可以放到 v2c 或之后。
