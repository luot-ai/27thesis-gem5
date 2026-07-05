# matmul_inner 批量运行结果

## 目的

本文记录 `matmul_inner_M32_N32_K32` 的第一组 gem5 批量运行结果。
这个 benchmark 用三重循环实现矩阵乘：

```text
C[i][j] = sum_k A[i][k] * B[k][j]
```

它比 `vadd` 更偏计算，也有更明显的数据复用，因此适合用来检查 stride
prefetch baseline 在非纯流式 kernel 上的行为。

## Benchmark 配置

| 项目 | 数值 |
| --- | --- |
| 源码 | `benchmarks/matmul_inner/matmul_inner.c` |
| RISC-V binary | `build/matmul_inner_M32_N32_K32.riscv` |
| M | 32 |
| N | 32 |
| K | 32 |
| 编译方式 | `BENCHMARK=matmul_inner MATMUL_M=32 MATMUL_N=32 MATMUL_K=32 ./scripts/build_benchmarks.sh` |
| 运行方式 | `python3 scripts/run_batch.py --benchmark matmul_inner_M32_N32_K32` |
| 结果目录 | `results/matmul_inner_M32_N32_K32/` |

源码中的 `M`、`N`、`K` 是编译期宏，可通过 `MATMUL_M`、`MATMUL_N`、
`MATMUL_K` 传给 `scripts/build_benchmarks.sh`。

## 运行 Config

本次 batch 跑了四组 config：

| config | 说明 |
| --- | --- |
| `o3_nopf` | O3 no-prefetch baseline |
| `o3_stridepf` | L1D-only stride prefetch，默认 degree=4 |
| `o3_stridepf_d8` | L1D-only stride prefetch，degree=8 |
| `o3_stridepf_l1d_l2_l3_d8` | L1D/L2/L3 stride prefetch，degree=8，paper-like cache profile |

四组 run 都通过了 benchmark 自检，输出 checksum 均为 53。

## 核心结果

| config | instructions | cycles | IPC | L1D miss rate | L1D misses | L2 misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `o3_nopf` | 741885 | 1087200 | 0.682381 | 0.086827 | 11089 | 1697 |
| `o3_stridepf` | 741885 | 1024930 | 0.723840 | 0.034394 | 4408 | 1888 |
| `o3_stridepf_d8` | 741885 | 1025120 | 0.723706 | 0.029326 | 3759 | 1893 |
| `o3_stridepf_l1d_l2_l3_d8` | 741885 | 1048332 | 0.707681 | 0.025314 | 3245 | 947 |

相对 `o3_nopf`：

| config | cycle reduction | IPC improvement | L1D miss reduction |
| --- | ---: | ---: | ---: |
| `o3_stridepf` | 5.73% | 6.08% | 60.25% |
| `o3_stridepf_d8` | 5.71% | 6.06% | 66.10% |
| `o3_stridepf_l1d_l2_l3_d8` | 3.58% | 3.71% | 70.74% |

## Prefetch 指标

| config | L1D pfIssued | L1D pfUseful | L1D accuracy | L2 pfIssued | L2 pfUseful | L3 pfIssued | L3 pfUseful |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `o3_stridepf` | 4637 | 608 | 0.131119 | - | - | - | - |
| `o3_stridepf_d8` | 7978 | 691 | 0.086613 | - | - | - | - |
| `o3_stridepf_l1d_l2_l3_d8` | 4544 | 756 | 0.166373 | 6733 | 934 | 6302 | 789 |

## 初步解读

`matmul_inner_M32_N32_K32` 和 `vadd` 的行为不同。`vadd` 是高度规则的线性
streaming kernel，因此 stride prefetch 对 IPC 的帮助很明显。`matmul_inner`
虽然也有规则访存，但它包含更多整数乘加、循环控制和数据复用，且 32x32x32
的工作集较小，能较好落在 cache 中。

因此，本次结果呈现出两个特点：

- L1D miss count / miss rate 下降明显；
- IPC 提升相对温和，约 3.7% 到 6.1%。

三层 Pf-Stride 配置的 L1D miss 最少，但 IPC 并不是最高。这和 `vadd_N16384`
结果一致地提醒我们：多级预取会改变 cache 访问路径和流量，不能只根据 L1D
miss 判断最终性能。

## 后续建议

下一步可以增加更大的矩阵规模，例如 `M=N=K=64`，并考虑 blocked matmul。
普通三重循环 matmul 和 blocked matmul 的 cache 行为不同，对 stream engine
和 prefetch baseline 的压力也不同。
