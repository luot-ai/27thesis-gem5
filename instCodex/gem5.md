# Codex 任务：分步骤搭建 gem5 O3 / BOOM-like Baseline 评估流程

## 0. 背景

我正在做毕业论文，题目暂定为：

> 面向边缘端信号与智能处理的流式访存优化研究

我前期已经用 RTL / Chisel 做过一个 stream engine 原型，现在需要建立一个更可信的 CPU baseline，用于后续和 stream engine 机制进行性能对比。

本阶段的目标不是实现 stream engine，而是先把 gem5 baseline 跑起来。

---

## 1. 总体目标

请分步骤完成一个可复现的 gem5 RISC-V 性能评估流程。

最终希望做到：

1. 能编译 benchmark 为 RISC-V 可执行文件。
2. 能用 gem5 O3 CPU 跑 benchmark。
3. 能提供 no-prefetch 和 stride-prefetch 两类 baseline。
4. 能参考公开 BOOM 配置，建立一个 BOOM-like O3 baseline。
5. 能收集并整理 gem5 stats。
6. 能生成简单的结果表格。
7. 能写清楚 README，方便我继续扩展。

请注意：

* 不要求精确复现 BOOM。
* 不要实现 stream engine。
* 不要修改 gem5 O3 CPU 核心逻辑。
* 不要新增 RISC-V 自定义指令。
* 不要接入 Chisel RTL。
* 不要做复杂 compiler pass。
* 先做最小可运行版本，再逐步扩展。

---

## 2. 请按阶段推进

请不要一次性把所有功能堆完。按下面顺序做。

---

### Step 1：检查当前环境和仓库结构

先检查当前仓库里是否已经有：

1. benchmark 源码。
2. gem5 相关脚本。
3. RISC-V 工具链。
4. 本地 gem5 仓库或 gem5 可执行文件。

需要输出一个简短说明，写到：

```text
notes/env_check.md
```

内容包括：

```text
- 当前找到的 benchmark 路径
- 当前找到的 RISC-V gcc
- 当前找到的 gem5 路径或 gem5.opt 路径
- 当前缺失的东西
- 下一步准备怎么处理
```

如果本地没有 gem5，不要直接假设路径。请给出清晰的获取和构建建议，例如 clone gem5、选择 RISC-V target、构建 gem5.opt 等，但不要把脚本写死到某个绝对路径。

---

### Step 2：先跑通最小 benchmark：vadd

优先只处理 `vadd`。

如果仓库里已经有 vadd，就复用已有代码。
如果没有，就创建一个最小可运行版本。

要求：

```text
vadd: y[i] = a[i] + b[i]
默认 N = 1024
```

需要保证：

1. 输入数据可初始化。
2. 结果有简单校验。
3. 程序可以正常退出。
4. 不依赖复杂库。

---

### Step 3：建立 RISC-V 编译脚本

请提供一个编译脚本，例如：

```bash
./scripts/build_benchmarks.sh
```

当前阶段至少能编译 vadd。

编译优化等级默认使用：

```bash
-O3
```

原因：本项目是性能评估，主结果应使用较高优化等级。
可以保留 `-O2` 作为可选 sanity check，但默认主线使用 `-O3`。

脚本需要支持环境变量覆盖，例如：

```bash
RISCV_GCC=riscv64-unknown-linux-gnu-gcc OPT=-O3 ./scripts/build_benchmarks.sh
```

如果找不到 RISC-V gcc，请明确报错，并在 README 中说明需要安装或配置工具链。

---

### Step 4：建立 gem5 O3 最小运行脚本

请提供一个 gem5 运行脚本，例如：

```bash
python3 scripts/run_gem5.py \
  --gem5-bin /path/to/gem5.opt \
  --benchmark build/vadd_N1024.riscv \
  --bench-name vadd_N1024 \
  --config o3_nopf
```

当前阶段只要求先跑通：

```text
vadd_N1024 + O3 CPU + no-prefetch
```

运行结果建议放到：

```text
results/
  vadd_N1024/
    o3_nopf/
      stats.txt
      config.json
      simout
      simerr
```

如果 gem5 执行失败，需要保留错误日志，不能静默失败。

---

### Step 5：调研公开 BOOM 配置

请你自己从公开资料中查找 BOOM 配置，而不是依赖我提前给出的固定参数。

需要整理一个文档：

```text
notes/boom_config_survey.md
```

内容包括：

```text
- BOOM 有哪些公开配置，例如 Small / Medium / Large 等
- 这些配置大概关注哪些参数
- 哪些参数可以映射到 gem5 O3 CPU
- 哪些参数不能直接映射
- 最终建议采用哪个 BOOM-like baseline
- 为什么这个 baseline 适合当前论文阶段
```

请注意表述：

```text
This is a BOOM-like O3 baseline inspired by public BOOM configurations.
It is not a cycle-accurate reproduction of BOOM.
```

不要声称 gem5 O3 精确复现 BOOM。

---

### Step 6：根据调研结果建立 BOOM-like O3 配置

在完成 `notes/boom_config_survey.md` 后，再建立 gem5 O3 配置。

可以放在：

```text
gem5_configs/
  riscv_o3_baseline.py
  boom_like_profiles.py
```

要求：

1. 先实现一个主 baseline。
2. 参数来源需要能在 `notes/boom_config_survey.md` 中找到解释。
3. 不要追求完全精确。
4. 能跑通比参数完美更重要。

---

### Step 7：增加 stride-prefetch baseline

在 no-prefetch 跑通后，再增加：

```text
o3_stridepf
```

目标是能对比：

```text
O3 no-prefetch
O3 stride-prefetch
```

请根据当前 gem5 版本自行判断如何开启 stride prefetcher。

如果当前 gem5 版本或配置方式导致 stride prefetcher 无法直接开启，请说明原因，不要硬跳过。

---

### Step 8：实现 stats 整理脚本

请实现一个简单 stats 解析脚本，例如：

```bash
python3 scripts/parse_stats.py --results-dir results
```

不需要一开始就解析非常多字段。

请你根据 gem5 实际输出，自行选择关键指标，例如：

```text
- 指令数
- cycle 或 tick
- IPC / CPI
- cache miss 相关指标
- prefetch 相关指标，如果有
```

要求：

1. 字段缺失时不要崩溃。
2. 输出 CSV 或 Markdown 表格。
3. 在脚本或 README 中说明每个指标来自 stats.txt 的哪个字段。
4. 不要编造不存在的数据。

---

### Step 9：扩展更多 benchmark

在 vadd 跑通后，再逐步扩展：

优先级：

```text
1. fir
2. fft_stockham
3. gemm
```

当前已有或计划 shape：

```text
vadd: N = 1024 或更大
fir: K = 32, N = 1024
fft: stockham-32
gemm: M = N = K = 32
```

如果某个 benchmark 一时跑不通，不要卡死整体流程。
请在 README 或 notes 中说明当前状态。

---

### Step 10：一键运行脚本

在前面步骤都基本跑通后，再提供：

```bash
./scripts/run_all.sh
```

功能：

```text
1. 编译 benchmark
2. 运行 no-prefetch baseline
3. 运行 stride-prefetch baseline
4. 解析 stats
5. 生成结果表格
```

请不要在最开始就优先写大而全的 run_all。
先保证单个 vadd 能跑通。

---

## 3. 建议目录结构

可以参考如下结构，但不强制。如果当前仓库已有结构，请尽量少改动。

```text
.
├── benchmarks/
│   ├── vadd/
│   ├── fir/
│   ├── fft_stockham/
│   └── gemm/
│
├── scripts/
│   ├── build_benchmarks.sh
│   ├── run_gem5.py
│   ├── parse_stats.py
│   └── run_all.sh
│
├── gem5_configs/
│   ├── riscv_o3_baseline.py
│   └── boom_like_profiles.py
│
├── notes/
│   ├── env_check.md
│   └── boom_config_survey.md
│
├── build/
├── results/
├── summary.csv
├── summary.md
└── README.md
```

---

## 4. README 要求

请写一个清楚的 README，至少说明：

```text
1. 当前项目目标
2. 当前已经跑通了哪些 benchmark
3. 如何配置 RISC-V 工具链
4. 如何配置或获取 gem5
5. 如何编译 benchmark
6. 如何运行单个 benchmark
7. 如何切换 no-prefetch / stride-prefetch
8. 如何解析 stats
9. BOOM-like baseline 的含义和限制
10. 当前没有实现 stream engine
11. 后续如何加入 stream engine
```

README 中要明确说明：

```text
本阶段只是建立 baseline，不代表 stream engine 已经完成。
```

---

## 5. 不要做的事情

本阶段不要做：

```text
1. 不要实现 stream engine
2. 不要修改 gem5 O3 CPU 核心逻辑
3. 不要新增 RISC-V 自定义指令
4. 不要接入 Chisel RTL
5. 不要做 Verilator 联合仿真
6. 不要做复杂 compiler pass
7. 不要一次性铺太大
8. 不要为了兼容所有 benchmark 写复杂框架
9. 不要依赖绝对路径
10. 不要编造实验结果
```

---

## 6. 验收标准

### 最低验收

```text
vadd_N1024 能编译成 RISC-V 可执行文件。
vadd_N1024 能在 gem5 O3 no-prefetch 下跑通。
results 中能看到 stats.txt。
```

### 正常验收

```text
vadd_N1024 能分别在 o3_nopf 和 o3_stridepf 下跑通。
能生成简单 summary 表格。
README 说明完整。
notes/boom_config_survey.md 中有 BOOM-like baseline 的来源说明。
```

### 理想验收

```text
vadd / fir / fft_stockham / gemm 都能跑通。
每个 benchmark 都有 no-prefetch 和 stride-prefetch 两组结果。
summary.md 可以直接放进组会材料。
```

---

## 7. 组会展示口径

请在 README 或 notes 中保留以下口径，方便后续写组会材料：

```text
本阶段目标不是完成 stream engine 建模，而是先建立可信的 O3 CPU baseline。

后续 stream engine 的收益不仅要和普通 O3 CPU 比，也要和 gem5 中的 stride prefetcher 比。

stride prefetcher 主要解决数据提前进入 cache 的问题，但不会减少动态 load/store 指令，也不会减少地址生成、rename、issue、commit 等流水线压力。

stream engine 后续要验证的是：能否把规则访存从主指令流中解耦，由硬件维护索引更新、buffer 状态和访存请求，从而降低边缘端 signal / AI 小 kernel 中访存相关指令对计算流水的干扰。
```
