"""BRU — Branch Resolution Unit for XiangShan-pyc backend.

Single-cycle branch comparator and target computation.  Resolves conditional
and unconditional branches/jumps, producing redirect signals for the frontend.

Reference: XiangShan/src/main/scala/xiangshan/backend/fu/Bru.scala

Operations (4-bit bru_op encoding):
  0000  BEQ     branch if equal
  0001  BNE     branch if not equal
  0010  BLT     branch if less than (signed)
  0011  BGE     branch if greater or equal (signed)
  0100  BLTU    branch if less than (unsigned)
  0101  BGEU    branch if greater or equal (unsigned)
  0110  JAL     jump and link (unconditional)
  0111  JALR    jump and link register (unconditional, indirect)

Key features:
  B-BRU-001  Single-cycle latency (pure combinational)
  B-BRU-002  Signed and unsigned comparison
  B-BRU-003  Target address computation (PC + imm, or src1 + imm for JALR)
  B-BRU-004  Redirect output: taken, target, redirect_valid
  B-BRU-005  Link register output (PC + 4 for JAL/JALR)
"""
from __future__ import annotations

import sys
from pathlib import Path

_XS_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_XS_ROOT) not in sys.path:
    sys.path.insert(0, str(_XS_ROOT))

from pycircuit import (
    CycleAwareCircuit,
    CycleAwareDomain,
    CycleAwareSignal,
    cas,
    compile_cycle_aware,
    mux,
    u,
)

from top.parameters import XLEN, PC_WIDTH

BRU_OP_WIDTH = 4

OP_BEQ  = 0b0000
OP_BNE  = 0b0001
OP_BLT  = 0b0010
OP_BGE  = 0b0011
OP_BLTU = 0b0100
OP_BGEU = 0b0101
OP_JAL  = 0b0110
OP_JALR = 0b0111


def build_bru(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    data_width: int = XLEN,
    pc_width: int = PC_WIDTH,
) -> None:
    """BRU: single-cycle branch resolution unit."""

    op_w = BRU_OP_WIDTH
    ext_w = data_width + 1

    # ── Cycle 0: Inputs ──────────────────────────────────────────
    in_valid = cas(domain, m.input("in_valid", width=1), cycle=0)
    src1 = cas(domain, m.input("src1", width=data_width), cycle=0)
    src2 = cas(domain, m.input("src2", width=data_width), cycle=0)
    pc = cas(domain, m.input("pc", width=pc_width), cycle=0)
    imm = cas(domain, m.input("imm", width=data_width), cycle=0)
    bru_op = cas(domain, m.input("bru_op", width=op_w), cycle=0)
    predicted_taken = cas(domain, m.input("predicted_taken", width=1), cycle=0)

    def _const(val, w=data_width):
        return cas(domain, m.const(val, width=w), cycle=0)

    def _op(val):
        return cas(domain, m.const(val, width=op_w), cycle=0)

    ZERO_1 = cas(domain, m.const(0, width=1), cycle=0)
    ONE_1 = cas(domain, m.const(1, width=1), cycle=0)

    # ── Comparison logic ─────────────────────────────────────────
    eq = (src1 == src2)
    ne = ~eq

    # Subtraction for signed/unsigned comparison
    sub = cas(domain, (src1.wire - src2.wire)[0:data_width], cycle=0)
    sub_sign = sub[data_width - 1:data_width]

    # Signed less-than: check sign bits and subtraction sign
    s1_sign = src1[data_width - 1:data_width]
    s2_sign = src2[data_width - 1:data_width]
    signs_differ = s1_sign ^ s2_sign
    lt_signed = mux(signs_differ, s1_sign, sub_sign)

    # Unsigned less-than: extended subtraction borrow
    ext_sub = cas(domain,
                  (src1.wire + u(ext_w, 0) - src2.wire - u(ext_w, 0))[0:ext_w],
                  cycle=0)
    lt_unsigned = ext_sub[data_width:data_width + 1]

    ge_signed = ~lt_signed
    ge_unsigned = ~lt_unsigned

    # ── Branch taken decision ────────────────────────────────────
    taken = ZERO_1  # default: not taken
    taken = mux(bru_op == _op(OP_BEQ),  eq,          taken)
    taken = mux(bru_op == _op(OP_BNE),  ne,          taken)
    taken = mux(bru_op == _op(OP_BLT),  lt_signed,   taken)
    taken = mux(bru_op == _op(OP_BGE),  ge_signed,   taken)
    taken = mux(bru_op == _op(OP_BLTU), lt_unsigned,  taken)
    taken = mux(bru_op == _op(OP_BGEU), ge_unsigned,  taken)
    taken = mux(bru_op == _op(OP_JAL),  ONE_1,        taken)
    taken = mux(bru_op == _op(OP_JALR), ONE_1,        taken)

    # ── Target address computation ───────────────────────────────
    # Branch/JAL: target = PC + imm
    pc_ext = cas(domain, (pc.wire + u(data_width, 0))[0:data_width], cycle=0)
    branch_target = cas(domain, (pc_ext.wire + imm.wire)[0:pc_width], cycle=0)

    # JALR: target = (src1 + imm) & ~1
    jalr_raw = cas(domain, (src1.wire + imm.wire)[0:pc_width], cycle=0)
    mask = cas(domain, m.const((1 << pc_width) - 2, width=pc_width), cycle=0)
    jalr_target = jalr_raw & mask

    is_jalr = bru_op == _op(OP_JALR)
    target = mux(is_jalr, jalr_target, branch_target)

    # ── Link address (PC + 4 for JAL/JALR) ──────────────────────
    four_pc = cas(domain, m.const(4, width=pc_width), cycle=0)
    link_addr = cas(domain, (pc.wire + four_pc.wire)[0:pc_width], cycle=0)

    is_jal = bru_op == _op(OP_JAL)
    is_link = is_jal | is_jalr

    # ── Redirect: mispredict detection ───────────────────────────
    mispredict = taken ^ predicted_taken
    redirect_valid = in_valid & mispredict

    # ── Outputs ──────────────────────────────────────────────────
    m.output("taken", taken.wire)
    m.output("target", target.wire)
    m.output("redirect_valid", redirect_valid.wire)
    m.output("redirect_target", target.wire)
    m.output("link_addr", link_addr.wire)
    m.output("is_link", is_link.wire)
    m.output("mispredict", mispredict.wire)


build_bru.__pycircuit_name__ = "bru"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_bru, name="bru", eager=True,
        data_width=64, pc_width=39,
    ).emit_mlir())
