#ifndef BENCHMARKS_COMMON_STREAM_INSTR_V06_H
#define BENCHMARKS_COMMON_STREAM_INSTR_V06_H

#include <stdint.h>

#define STREAM_OPCODE 0x0b

#define STREAM_F3_CFG 0x0
#define STREAM_F3_SSR 0x6
#define STREAM_F3_SSS 0x7

#define STREAM_CFG_ITER 0x00
#define STREAM_CFG_I_LIMIT 0x01
#define STREAM_CFG_I_REPEAT 0x02
#define STREAM_CFG_STRIDE 0x03
#define STREAM_CFG_TILESTRIDE 0x04
#define STREAM_CFG_REUSE 0x05
#define STREAM_CFG_LOAD 0x06
#define STREAM_CFG_AXI_LOAD 0x07
#define STREAM_CFG_STORE 0x08

#define STREAM_OP_ADD 0x00

#define STREAM_FUNCT7_OP(op) ((op) & 0x1f)

#define STREAM_INSTR_V06_STR1(x) #x
#define STREAM_INSTR_V06_STR(x) STREAM_INSTR_V06_STR1(x)

#define STREAM_INSTR_V06_CFG(funct7, value, fifo_id)                 \
    do {                                                            \
        uintptr_t stream_instr_v06_rs1 = (uintptr_t)(value);        \
        uintptr_t stream_instr_v06_rs2 = (uintptr_t)(fifo_id);      \
        __asm__ volatile(                                           \
            ".insn r " STREAM_INSTR_V06_STR(STREAM_OPCODE) ", "    \
            STREAM_INSTR_V06_STR(STREAM_F3_CFG) ", "               \
            STREAM_INSTR_V06_STR(funct7) ", x0, %0, %1"            \
            :                                                       \
            : "r"(stream_instr_v06_rs1), "r"(stream_instr_v06_rs2) \
            : "memory");                                           \
    } while (0)

#define STREAM_INSTR_V06_SSS(op_id, src0_fifo_id, src1_fifo_id, dst_fifo_id) \
    do {                                                                    \
        uintptr_t stream_instr_v06_rs1 =                                    \
            stream_instr_v06_pack_stream_pair(src0_fifo_id, src1_fifo_id);  \
        uintptr_t stream_instr_v06_rs2 = (uintptr_t)(dst_fifo_id);          \
        __asm__ volatile(                                                   \
            ".insn r " STREAM_INSTR_V06_STR(STREAM_OPCODE) ", "            \
            STREAM_INSTR_V06_STR(STREAM_F3_SSS) ", "                       \
            STREAM_INSTR_V06_STR(op_id) ", x0, %0, %1"                     \
            :                                                               \
            : "r"(stream_instr_v06_rs1), "r"(stream_instr_v06_rs2)         \
            : "memory");                                                   \
    } while (0)

static inline uintptr_t stream_instr_v06_pack_iter(int outer_iter, int length)
{
    uintptr_t outer = (uintptr_t)((uint32_t)outer_iter & 0xffffu);
    uintptr_t inner = (uintptr_t)((uint32_t)length & 0xffffu);

    return (inner << 16) | outer;
}

static inline uintptr_t stream_instr_v06_pack_stream_pair(
    int src0_fifo_id,
    int src1_fifo_id
)
{
    uintptr_t src0 = (uintptr_t)src0_fifo_id & 0x3u;
    uintptr_t src1 = (uintptr_t)src1_fifo_id & 0x3u;

    return (src1 << 2) | src0;
}

static inline void cfg_iter(int outer_iter, int length, int fifo_id)
{
    STREAM_INSTR_V06_CFG(
        STREAM_CFG_ITER,
        stream_instr_v06_pack_iter(outer_iter, length),
        fifo_id
    );
}

static inline void cfg_i_limit(int limit, int fifo_id)
{
    STREAM_INSTR_V06_CFG(STREAM_CFG_I_LIMIT, limit, fifo_id);
}

static inline void cfg_i_repeat(int repeat, int fifo_id)
{
    STREAM_INSTR_V06_CFG(STREAM_CFG_I_REPEAT, repeat, fifo_id);
}

static inline void cfg_stride(uint32_t stride, int fifo_id)
{
    STREAM_INSTR_V06_CFG(STREAM_CFG_STRIDE, stride, fifo_id);
}

static inline void cfg_tilestride(uint32_t tilestride, int fifo_id)
{
    STREAM_INSTR_V06_CFG(STREAM_CFG_TILESTRIDE, tilestride, fifo_id);
}

static inline void cfg_reuse(uint32_t reuse, int fifo_id)
{
    STREAM_INSTR_V06_CFG(STREAM_CFG_REUSE, reuse, fifo_id);
}

static inline void cfg_load(uintptr_t base_addr, int fifo_id)
{
    STREAM_INSTR_V06_CFG(STREAM_CFG_LOAD, base_addr, fifo_id);
}

static inline void cfg_axi_load(uintptr_t base_addr, int fifo_id)
{
    STREAM_INSTR_V06_CFG(STREAM_CFG_AXI_LOAD, base_addr, fifo_id);
}

static inline void cfg_store(uintptr_t base_addr, int fifo_id)
{
    STREAM_INSTR_V06_CFG(STREAM_CFG_STORE, base_addr, fifo_id);
}

static inline void sss_add(int src0_fifo_id, int src1_fifo_id, int dst_fifo_id)
{
    STREAM_INSTR_V06_SSS(
        STREAM_OP_ADD,
        src0_fifo_id,
        src1_fifo_id,
        dst_fifo_id
    );
}

#endif
