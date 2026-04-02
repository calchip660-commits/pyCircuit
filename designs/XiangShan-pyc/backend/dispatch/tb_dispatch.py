"""Testbench for Dispatch — MLIR smoke (L1) + functional directed (L2).

L2 tests verify FU-type based routing to int/fp/mem issue queues,
backpressure stall propagation, and output passthrough correctness.
Uses dispatch_width=2, 4-bit ptag, 16-bit PC for fast compilation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pycircuit import CycleAwareTb, Tb, compile_cycle_aware, testbench

_XS_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_XS_ROOT) not in sys.path:
    sys.path.insert(0, str(_XS_ROOT))

from backend.dispatch.dispatch import (  # noqa: E402
    FU_ALU, FU_BRU, FU_FPU, FU_LDU, build_dispatch,
)

DP_W = 2
FU_W = 3
PTAG_W = 4
PC_W = 16
ROB_W = 4


def _drive_idle(tb: CycleAwareTb) -> None:
    for i in range(DP_W):
        tb.drive(f"in_valid_{i}", 0)
        tb.drive(f"in_pdest_{i}", 0)
        tb.drive(f"in_psrc1_{i}", 0)
        tb.drive(f"in_psrc2_{i}", 0)
        tb.drive(f"in_old_pdest_{i}", 0)
        tb.drive(f"in_fu_type_{i}", 0)
        tb.drive(f"in_rob_idx_{i}", 0)
        tb.drive(f"in_pc_{i}", 0)
    tb.drive("iq_int_ready", 1)
    tb.drive("iq_fp_ready", 1)
    tb.drive("iq_mem_ready", 1)
    tb.drive("flush", 0)


# ── L2: Functional testbench ────────────────────────────────────

@testbench
def tb_dispatch_functional(t: Tb) -> None:
    tb = CycleAwareTb(t)
    tb.clock("clk")
    tb.reset("rst", cycles_asserted=2, cycles_deasserted=1)
    tb.timeout(30)

    # ── T1: No valid input → no output valid ──────────────────────
    _drive_idle(tb)
    tb.expect("stall", 0, msg="T1: no stall when idle")
    for i in range(DP_W):
        tb.expect(f"iq_int_valid_{i}", 0, msg=f"T1: int_valid_{i}=0")
        tb.expect(f"iq_fp_valid_{i}", 0, msg=f"T1: fp_valid_{i}=0")
        tb.expect(f"iq_mem_valid_{i}", 0, msg=f"T1: mem_valid_{i}=0")
        tb.expect(f"rob_enq_valid_{i}", 0, msg=f"T1: rob_enq_{i}=0")
    tb.expect("int_dispatch_count", 0, msg="T1: int_cnt=0")
    tb.expect("fp_dispatch_count", 0, msg="T1: fp_cnt=0")
    tb.expect("mem_dispatch_count", 0, msg="T1: mem_cnt=0")

    # ── T2a: ALU (int) + LDU (mem) routing ────────────────────────
    tb.next()
    _drive_idle(tb)
    tb.drive("in_valid_0", 1)
    tb.drive("in_fu_type_0", FU_ALU)
    tb.drive("in_pdest_0", 1)
    tb.drive("in_psrc1_0", 2)
    tb.drive("in_psrc2_0", 3)
    tb.drive("in_pc_0", 0x100)
    tb.drive("in_rob_idx_0", 0)

    tb.drive("in_valid_1", 1)
    tb.drive("in_fu_type_1", FU_LDU)
    tb.drive("in_pdest_1", 4)
    tb.drive("in_pc_1", 0x104)
    tb.drive("in_rob_idx_1", 1)

    tb.expect("stall", 0, msg="T2a: no stall")
    tb.expect("iq_int_valid_0", 1, msg="T2a: slot0→int")
    tb.expect("iq_fp_valid_0", 0, msg="T2a: slot0 not fp")
    tb.expect("iq_mem_valid_0", 0, msg="T2a: slot0 not mem")
    tb.expect("iq_int_valid_1", 0, msg="T2a: slot1 not int")
    tb.expect("iq_fp_valid_1", 0, msg="T2a: slot1 not fp")
    tb.expect("iq_mem_valid_1", 1, msg="T2a: slot1→mem")
    tb.expect("rob_enq_valid_0", 1, msg="T2a: rob_enq_0")
    tb.expect("rob_enq_valid_1", 1, msg="T2a: rob_enq_1")
    tb.expect("out_pdest_0", 1, msg="T2a: passthrough pdest_0")
    tb.expect("out_psrc1_0", 2, msg="T2a: passthrough psrc1_0")
    tb.expect("out_pc_0", 0x100, msg="T2a: passthrough pc_0")
    tb.expect("int_dispatch_count", 1, msg="T2a: int_cnt=1")
    tb.expect("fp_dispatch_count", 0, msg="T2a: fp_cnt=0")
    tb.expect("mem_dispatch_count", 1, msg="T2a: mem_cnt=1")

    # ── T2b: FPU (fp) + BRU (int) routing ─────────────────────────
    tb.next()
    _drive_idle(tb)
    tb.drive("in_valid_0", 1)
    tb.drive("in_fu_type_0", FU_FPU)
    tb.drive("in_pdest_0", 5)

    tb.drive("in_valid_1", 1)
    tb.drive("in_fu_type_1", FU_BRU)
    tb.drive("in_pdest_1", 6)

    tb.expect("stall", 0, msg="T2b: no stall")
    tb.expect("iq_fp_valid_0", 1, msg="T2b: slot0→fp")
    tb.expect("iq_int_valid_0", 0, msg="T2b: slot0 not int")
    tb.expect("iq_mem_valid_0", 0, msg="T2b: slot0 not mem")
    tb.expect("iq_int_valid_1", 1, msg="T2b: slot1→int (BRU)")
    tb.expect("iq_fp_valid_1", 0, msg="T2b: slot1 not fp")
    tb.expect("iq_mem_valid_1", 0, msg="T2b: slot1 not mem")
    tb.expect("int_dispatch_count", 1, msg="T2b: int_cnt=1")
    tb.expect("fp_dispatch_count", 1, msg="T2b: fp_cnt=1")
    tb.expect("mem_dispatch_count", 0, msg="T2b: mem_cnt=0")

    # ── T3a: Backpressure — int IQ full stalls int uop ────────────
    tb.next()
    _drive_idle(tb)
    tb.drive("in_valid_0", 1)
    tb.drive("in_fu_type_0", FU_ALU)
    tb.drive("iq_int_ready", 0)

    tb.expect("stall", 1, msg="T3a: stall when int IQ full")
    tb.expect("iq_int_valid_0", 0, msg="T3a: no int dispatch")
    tb.expect("rob_enq_valid_0", 0, msg="T3a: no rob enq")

    # ── T3b: Backpressure — blocked slot stalls entire group ──────
    tb.next()
    _drive_idle(tb)
    tb.drive("in_valid_0", 1)
    tb.drive("in_fu_type_0", FU_ALU)
    tb.drive("in_valid_1", 1)
    tb.drive("in_fu_type_1", FU_LDU)
    tb.drive("iq_mem_ready", 0)

    tb.expect("stall", 1, msg="T3b: blocked slot1 stalls all")
    tb.expect("iq_int_valid_0", 0, msg="T3b: slot0 int blocked too")
    tb.expect("iq_mem_valid_1", 0, msg="T3b: slot1 mem blocked")
    tb.expect("rob_enq_valid_0", 0, msg="T3b: no rob_enq slot0")
    tb.expect("rob_enq_valid_1", 0, msg="T3b: no rob_enq slot1")
    tb.expect("int_dispatch_count", 0, msg="T3b: int_cnt=0")
    tb.expect("mem_dispatch_count", 0, msg="T3b: mem_cnt=0")

    # ── T3c: Unblock — all IQs ready again → dispatch fires ───────
    tb.next()
    _drive_idle(tb)
    tb.drive("in_valid_0", 1)
    tb.drive("in_fu_type_0", FU_ALU)
    tb.drive("in_valid_1", 1)
    tb.drive("in_fu_type_1", FU_LDU)

    tb.expect("stall", 0, msg="T3c: no stall after unblock")
    tb.expect("iq_int_valid_0", 1, msg="T3c: slot0 dispatches")
    tb.expect("iq_mem_valid_1", 1, msg="T3c: slot1 dispatches")
    tb.expect("rob_enq_valid_0", 1, msg="T3c: rob_enq slot0")
    tb.expect("rob_enq_valid_1", 1, msg="T3c: rob_enq slot1")

    tb.finish()


# ── L1: MLIR smoke (pytest) ─────────────────────────────────────

@pytest.mark.smoke
def test_dispatch_emit_mlir():
    mlir = compile_cycle_aware(
        build_dispatch, name="dispatch", eager=True,
        dispatch_width=4, fu_type_width=3,
        ptag_w=8, pc_width=39, rob_idx_w=9,
    ).emit_mlir()
    assert "func.func" in mlir
    assert "@dispatch" in mlir
    assert "stall" in mlir


@pytest.mark.smoke
def test_dispatch_small_emit_mlir():
    mlir = compile_cycle_aware(
        build_dispatch, name="dispatch_s", eager=True,
        dispatch_width=DP_W, fu_type_width=FU_W,
        ptag_w=PTAG_W, pc_width=PC_W, rob_idx_w=ROB_W,
    ).emit_mlir()
    assert "func.func" in mlir
    assert "stall" in mlir


@pytest.mark.regcount
def test_dispatch_has_pipeline_regs():
    import re
    mlir = compile_cycle_aware(
        build_dispatch, name="dispatch_rc", eager=True,
        dispatch_width=DP_W, fu_type_width=FU_W,
        ptag_w=PTAG_W, pc_width=PC_W, rob_idx_w=ROB_W,
    ).emit_mlir()
    n = len(re.findall(r"pyc\.reg", mlir))
    assert n >= DP_W, (
        f"Dispatch must have ≥{DP_W} pipeline regs "
        f"(dp1 stage per slot); got {n}"
    )


if __name__ == "__main__":
    test_dispatch_small_emit_mlir()
    print("PASS: test_dispatch_small_emit_mlir")
    test_dispatch_emit_mlir()
    print("PASS: test_dispatch_emit_mlir")
    test_dispatch_has_pipeline_regs()
    print("PASS: test_dispatch_has_pipeline_regs")
