# Stream Engine 功能模型第一版记录

## 目标

这一版的目标是先把 stream 指令到 gem5 O3 的功能路径跑通：

- RISC-V custom-0 stream 指令可以被 gem5 解码；
- CFG 指令可以配置 stream engine 内部 FIFO 描述符；
- SSS add 指令可以从两个 load FIFO 读数据，计算后写入 store FIFO；
- 直连内存访问先用 SE 模式地址翻译后的功能访问实现；
- 先不实现真实 timing AXI、L2 连接、cache 一致性、calstream 进入 CPU 流水线计算部件。

## 当前实现范围

当前支持的指令和行为：

- `cfg_iter`
- `cfg_i_limit`
- `cfg_i_repeat`
- `cfg_stride`
- `cfg_tilestride`
- `cfg_reuse`
- `cfg_load`
- `cfg_axi_load`
- `cfg_store`
- `sss_add`

`cfg_load` 和 `cfg_axi_load` 在第一版功能模型中都作为 load FIFO 配置处理。
`sss_add` 目前只支持 32-bit integer add。

stream 指令被标记为 `IsNonSpeculative`，避免 O3 在错误路径上提前执行带副作用的 stream-engine 操作。

## 主要文件

gem5 内部仓库提交：

- `tools/gem5`: `eed9abe` (`arch-riscv,misc: 实现 stream engine 功能模型第一版`)

顶层仓库相关文件：

- `tools/gem5/src/stream/StreamEngine.py`
- `tools/gem5/src/stream/stream_engine.hh`
- `tools/gem5/src/stream/stream_engine.cc`
- `tools/gem5/src/stream/SConscript`
- `tools/gem5/src/arch/riscv/isa/decoder.isa`
- `tools/gem5/src/arch/riscv/isa/includes.isa`
- `gem5_configs/riscv_o3_baseline.py`
- `benchmarks/common/stream_instr_v06.h`
- `benchmarks/stream_vadd/stream_vadd.c`
- `scripts/build_benchmarks.sh`
- `scripts/run_gem5.py`
- `scripts/run_batch.py`

## 构建说明

这次 `gem5.opt` 最终使用 lld 链接成功。默认 `ld.bfd` 在本机上最终链接非常慢，并且曾留下过非 ELF 的半成品 `gem5.opt`。

推荐构建命令：

```bash
cd tools/gem5
scons build/RISCV/gem5.opt -j4 --linker=lld
```

benchmark 构建命令：

```bash
BENCHMARK=stream_vadd N=1024 ./scripts/build_benchmarks.sh
```

## 测试命令

```bash
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/stream_vadd_N1024.riscv \
  --bench-name stream_vadd_N1024 \
  --config o3_stream_axi_functional
```

## 测试结果

测试通过。

关键输出：

```text
stream_vadd passed N=1024
Exiting @ tick 106304000 because exiting with last active thread context
```

关键 stream-engine 统计：

```text
system.stream_engine.cfgInsts              21
system.stream_engine.sssInsts            1024
system.stream_engine.ssrInsts               0
system.stream_engine.loadWords           2048
system.stream_engine.storeWords          1024
system.stream_engine.computeOps          1024
system.stream_engine.unsupportedInsts       0
```

结果目录：

```text
results/stream_vadd_N1024/o3_stream_axi_functional/
```

## 当前限制

这一版是功能模型，不是精确时序模型：

- stream engine 访问内存使用 `SETranslatingPortProxy`，不是 timing AXI master；
- 目前没有实现和 L2 cache 的连接；
- 目前不保证与 CPU cache 的硬件一致性；
- compute latency / initiation interval 主要作为内部流水记账，尚未真实阻塞 O3 指令提交；
- 只支持 `sss_add` 的 32-bit integer add；
- 尚未实现指令级 difftest；
- SSR 指令入口已经预留，但当前 benchmark 没有覆盖。

## 下一步建议

下一步需要精确一下时序和功能验证

- 允许 ste 指令乱序执行，同时增加 arch、spech两套索引表支持错误路径恢复
- 设计 timing AXI 版本的接口边界；真实的对外 burst 请求
- 增加更小的 directed tests，分别覆盖每类 CFG 指令；
- 增加 `ssr_add` 的软件用例；
- 把 stream-engine 统计加入 `scripts/parse_stats.py`；
- 讨论是否需要在提交点或 checker 路径上做 stream 指令 difftest。
