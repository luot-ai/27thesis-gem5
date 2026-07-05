#ifndef STREAM_INSTR_H
#define STREAM_INSTR_H

#include <stdint.h>

#define STREAM_INSTR_ATTR static inline __attribute__((unused))

// 000
STREAM_INSTR_ATTR int cfg_i(int outerIter, int length, int fifo_id)
{
    int rs1 = (outerIter & 0xffff) | ((length & 0xffff) << 16);
    asm volatile (
       ".insn r 0x0b, 0, 0, x0, %0, %1"
             :
             : "r"(rs1), "r"(fifo_id)
     );
    return 0;
}

STREAM_INSTR_ATTR int cfg_i_limit(int limit, int fifo_id)
{
    asm volatile (
       ".insn r 0x0b, 0, 1, x0, %0, %1"
             :
             : "r"(limit), "r"(fifo_id)
     );
    return 0;
}

STREAM_INSTR_ATTR int cfg_i_repeat(int repeat, int fifo_id)
{
    asm volatile (
       ".insn r 0x0b, 0, 2, x0, %0, %1"
             :
             : "r"(repeat), "r"(fifo_id)
     );
    return 0;
}

// 001
STREAM_INSTR_ATTR int cfg_store(uint32_t addr, int fifo_id)
{
    asm volatile (
       ".insn r 0x0b, 1, 0, x0, %0, %1"
             :
             : "r"(addr), "r"(fifo_id)
     );
    return 0;
}

// 010
// TODO: src/dst are still partly fixed by hardware; later encode them in the instruction.
STREAM_INSTR_ATTR int cal_stream(int fifo_id_src0, int fifo_id_src1, int fifo_id_dst)
{
    int rs1 = (fifo_id_src0 & 0x3) | ((fifo_id_src1 & 0x3) << 2);
    asm volatile (
       ".insn r 0x0b, 2, 0, x0, %0, %1"
             :
             : "r"(rs1), "r"(fifo_id_dst)
     );
    return 0;
}

// Stream-stream to ping-pong stream.
STREAM_INSTR_ATTR int cal_stream_pp(int fifo_id_src0, int fifo_id_src1, int fifo_id_dst)
{
    int rs1 = (fifo_id_src0 & 0x3) | ((fifo_id_src1 & 0x3) << 2);
    asm volatile (
       ".insn r 0x0b, 2, 1, x0, %0, %1"
             :
             : "r"(rs1), "r"(fifo_id_dst)
     );
    return 0;
}

// 011
STREAM_INSTR_ATTR int cfg_stride(uint32_t stride, int fifo_id)
{
    asm volatile (
       ".insn r 0x0b, 3, 0, x0, %0, %1"
             :
             : "r"(stride), "r"(fifo_id)
     );
    return 0;
}

STREAM_INSTR_ATTR int cfg_tilestride(uint32_t tilestride, int fifo_id)
{
    asm volatile (
       ".insn r 0x0b, 3, 1, x0, %0, %1"
             :
             : "r"(tilestride), "r"(fifo_id)
     );
    return 0;
}

// 100
STREAM_INSTR_ATTR int cfg_reuse(uint32_t reuse, int fifo_id)
{
    asm volatile (
       ".insn r 0x0b, 4, 0, x0, %0, %1"
             :
             : "r"(reuse), "r"(fifo_id)
     );
    return 0;
}

// 101
STREAM_INSTR_ATTR int cfg_load(uint32_t addr, int fifo_id)
{
    asm volatile (
       ".insn r 0x0b, 5, 0, x0, %0, %1"
             :
             : "r"(addr), "r"(fifo_id)
     );
    return 0;
}

STREAM_INSTR_ATTR int cfg_axi_load(uint32_t addr, int fifo_id)
{
    asm volatile (
       ".insn r 0x0b, 5, 1, x0, %0, %1"
             :
             : "r"(addr), "r"(fifo_id)
     );
    return 0;
}

// 110: register-register to ping-pong stream.
STREAM_INSTR_ATTR int cal_rjrk_stream_pp(uint32_t lo, uint32_t hi)
{
    asm volatile (
       ".insn r 0x0b, 6, 0, x0, %0, %1"
             :
             : "r"(lo), "r"(hi)
     );
    return 0;
}

// 111
STREAM_INSTR_ATTR int cal_stream_rd_add(int fifo_id_src0, int fifo_id_src1)
{
    int rd;
    int rs1 = (fifo_id_src0 & 0x3) | ((fifo_id_src1 & 0x3) << 2);
    asm volatile (
       ".insn r 0x0b, 7, 0, %0, %1, x0"
             : "=r"(rd)
             : "r"(rs1)
     );
    return rd;
}

STREAM_INSTR_ATTR int cal_stream_rd_sub(int fifo_id_src0, int fifo_id_src1)
{
    int rd;
    int rs1 = (fifo_id_src0 & 0x3) | ((fifo_id_src1 & 0x3) << 2);
    asm volatile (
       ".insn r 0x0b, 7, 8, %0, %1, x0"
             : "=r"(rd)
             : "r"(rs1)
     );
    return rd;
}

STREAM_INSTR_ATTR int cal_stream_rd_mul(int fifo_id_src0, int fifo_id_src1)
{
    int rd;
    int rs1 = (fifo_id_src0 & 0x3) | ((fifo_id_src1 & 0x3) << 2);
    asm volatile (
       ".insn r 0x0b, 7, 16, %0, %1, x0"
             : "=r"(rd)
             : "r"(rs1)
     );
    return rd;
}

#undef STREAM_INSTR_ATTR

#endif
