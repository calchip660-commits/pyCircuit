"""Testbench for IssueQueue — MLIR smoke (L1) + functional directed (L2).

L2 tests verify enqueue, immediate issue of ready uops, wakeup-triggered
issue of dependent uops, and oldest-first selection via the age matrix.
Uses entries=4, enq=2, issue=1, 4-bit ptag for fast compilation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pycircuit import CycleAwareTb, Tb, compile_cycle_aware, testbench

_XS_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_XS_ROOT) not in sys.path:
    sys.path.insert(0, str(_XS_ROOT))

from backend.issue.issue_queue import build_issue_queue  # noqa: E402

ENTRIES = 4
ENQ_P = 2
ISSUE_P = 1
WB_P = 2
PTAG_W = 4
ROB_W = 4
FU_W = 3


def _drive_idle(tb: CycleAwareTb) -> None:
    for i in range(ENQ_P):
        tb.drive(f"enq_valid_{i}", 0)
        tb.drive(f"enq_pdest_{i}", 0)
        tb.drive(f"enq_psrc1_{i}", 0)
        tb.drive(f"enq_psrc2_{i}", 0)
        tb.drive(f"enq_src1_ready_{i}", 0)
        tb.drive(f"enq_src2_ready_{i}", 0)
        tb.drive(f"enq_rob_idx_{i}", 0)
        tb.drive(f"enq_fu_type_{i}", 0)
    for i in range(WB_P):
        tb.drive(f"wb_valid_{i}", 0)
        tb.drive(f"wb_pdest_{i}", 0)
    tb.drive("flush", 0)


# ── L2: Functional testbench ────────────────────────────────────

@testbench
def tb_issue_queue_functional(t: Tb) -> None:
    tb = CycleAwareTb(t)
    tb.clock("clk")
    tb.reset("rst", cycles_asserted=2, cycles_deasserted=1)
    tb.timeout(40)

    # ── T1: Empty after reset → no issue ──────────────────────────
    _drive_idle(tb)
    tb.expect("issue_valid_0", 0, msg="T1: no issue when empty")
    tb.expect("ready", 1, msg="T1: has room")
    tb.expect("free_count", ENTRIES, msg=f"T1: {ENTRIES} free")

    # ── T2: Enqueue 1 ready uop → issue next cycle ───────────────
    # Enqueue: pdest=5, both sources ready, rob_idx=1, fu=ALU(0)
    tb.next()
    _drive_idle(tb)
    tb.drive("enq_valid_0", 1)
    tb.drive("enq_pdest_0", 5)
    tb.drive("enq_psrc1_0", 1)
    tb.drive("enq_psrc2_0", 2)
    tb.drive("enq_src1_ready_0", 1)
    tb.drive("enq_src2_ready_0", 1)
    tb.drive("enq_rob_idx_0", 1)
    tb.drive("enq_fu_type_0", 0)

    tb.expect("issue_valid_0", 0, msg="T2: no issue on enqueue cycle")

    # Next cycle: entry is in state, both srcs ready → issues
    tb.next()
    _drive_idle(tb)
    tb.expect("issue_valid_0", 1, msg="T2: issue after 1 cycle")
    tb.expect("issue_pdest_0", 5, msg="T2: correct pdest")
    tb.expect("issue_rob_idx_0", 1, msg="T2: correct rob_idx")
    tb.expect("issue_fu_type_0", 0, msg="T2: correct fu_type")

    # ── T3: Dependency chain + wakeup ─────────────────────────────
    # Enqueue A (ready, pdest=6) and B (psrc1=6, NOT ready) together.
    # A issues immediately next cycle, then wakeup tag 6 triggers B.
    tb.next()
    _drive_idle(tb)
    tb.drive("enq_valid_0", 1)
    tb.drive("enq_pdest_0", 6)
    tb.drive("enq_psrc1_0", 1)
    tb.drive("enq_psrc2_0", 2)
    tb.drive("enq_src1_ready_0", 1)
    tb.drive("enq_src2_ready_0", 1)
    tb.drive("enq_rob_idx_0", 2)
    tb.drive("enq_fu_type_0", 0)

    tb.drive("enq_valid_1", 1)
    tb.drive("enq_pdest_1", 7)
    tb.drive("enq_psrc1_1", 6)
    tb.drive("enq_psrc2_1", 2)
    tb.drive("enq_src1_ready_1", 0)
    tb.drive("enq_src2_ready_1", 1)
    tb.drive("enq_rob_idx_1", 3)
    tb.drive("enq_fu_type_1", 1)

    # Next cycle: A ready → issues; B waiting on src1
    tb.next()
    _drive_idle(tb)
    tb.expect("issue_valid_0", 1, msg="T3: A issues (both srcs ready)")
    tb.expect("issue_pdest_0", 6, msg="T3: A pdest=6")

    # Wakeup tag 6 (A's result) → B's src1 becomes ready this cycle
    tb.next()
    _drive_idle(tb)
    tb.drive("wb_valid_0", 1)
    tb.drive("wb_pdest_0", 6)

    tb.expect("issue_valid_0", 1, msg="T3: B issues after wakeup")
    tb.expect("issue_pdest_0", 7, msg="T3: B pdest=7")

    # ── T4: Oldest-first selection with age matrix ────────────────
    # Enqueue C (not ready) in cycle N, then D (not ready) in cycle N+1.
    # C is older.  Wakeup both simultaneously → C selected first.

    # Cycle N: enqueue C (pdest=8, depends on tag 10, not ready)
    tb.next()
    _drive_idle(tb)
    tb.drive("enq_valid_0", 1)
    tb.drive("enq_pdest_0", 8)
    tb.drive("enq_psrc1_0", 10)
    tb.drive("enq_psrc2_0", 2)
    tb.drive("enq_src1_ready_0", 0)
    tb.drive("enq_src2_ready_0", 1)
    tb.drive("enq_rob_idx_0", 4)
    tb.drive("enq_fu_type_0", 1)

    # Cycle N+1: C in state; enqueue D (pdest=9, also depends on tag 10)
    tb.next()
    _drive_idle(tb)
    tb.drive("enq_valid_0", 1)
    tb.drive("enq_pdest_0", 9)
    tb.drive("enq_psrc1_0", 10)
    tb.drive("enq_psrc2_0", 2)
    tb.drive("enq_src1_ready_0", 0)
    tb.drive("enq_src2_ready_0", 1)
    tb.drive("enq_rob_idx_0", 5)
    tb.drive("enq_fu_type_0", 1)

    tb.expect("issue_valid_0", 0, msg="T4: C not ready, no issue")

    # Cycle N+2: both in state. Wakeup tag 10 → both become ready.
    # C is older (enqueued when D wasn't yet present) → C issues first.
    tb.next()
    _drive_idle(tb)
    tb.drive("wb_valid_0", 1)
    tb.drive("wb_pdest_0", 10)

    tb.expect("issue_valid_0", 1, msg="T4: oldest-ready issues")
    tb.expect("issue_pdest_0", 8, msg="T4: C (older) pdest=8")

    # Cycle N+3: C dequeued, D still ready → D issues
    tb.next()
    _drive_idle(tb)
    tb.expect("issue_valid_0", 1, msg="T4: D issues next cycle")
    tb.expect("issue_pdest_0", 9, msg="T4: D pdest=9")

    tb.finish()


# ── L1: MLIR smoke (pytest) ─────────────────────────────────────

@pytest.mark.smoke
def test_issue_queue_emit_mlir():
    mlir = compile_cycle_aware(
        build_issue_queue, name="issue_queue", eager=True,
        entries=8, enq_ports=2, issue_ports=2,
        wb_ports=4, ptag_w=8, rob_idx_w=9, fu_type_width=3,
    ).emit_mlir()
    assert "func.func" in mlir
    assert "@issue_queue" in mlir
    assert "issue_valid" in mlir


@pytest.mark.smoke
def test_issue_queue_small_emit_mlir():
    mlir = compile_cycle_aware(
        build_issue_queue, name="iq_s", eager=True,
        entries=ENTRIES, enq_ports=ENQ_P, issue_ports=ISSUE_P,
        wb_ports=WB_P, ptag_w=PTAG_W, rob_idx_w=ROB_W,
        fu_type_width=FU_W,
    ).emit_mlir()
    assert "func.func" in mlir
    assert "issue_valid" in mlir


@pytest.mark.regcount
def test_issue_queue_has_state_regs():
    import re
    mlir = compile_cycle_aware(
        build_issue_queue, name="iq_rc", eager=True,
        entries=ENTRIES, enq_ports=ENQ_P, issue_ports=ISSUE_P,
        wb_ports=WB_P, ptag_w=PTAG_W, rob_idx_w=ROB_W,
        fu_type_width=FU_W,
    ).emit_mlir()
    n = len(re.findall(r"pyc\.reg", mlir))
    min_regs = ENTRIES * 3 + ENTRIES * ENTRIES
    assert n >= min_regs, (
        f"IssueQueue must have ≥{min_regs} state regs "
        f"(entries×fields + age matrix); got {n}"
    )


if __name__ == "__main__":
    test_issue_queue_small_emit_mlir()
    print("PASS: test_issue_queue_small_emit_mlir")
    test_issue_queue_emit_mlir()
    print("PASS: test_issue_queue_emit_mlir")
    test_issue_queue_has_state_regs()
    print("PASS: test_issue_queue_has_state_regs")
