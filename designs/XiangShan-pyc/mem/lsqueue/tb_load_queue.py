"""Testbench for Load Queue — MLIR smoke (L1) + functional directed (L2).

L2 scenarios:
  T1  Enqueue load, verify state tracking (valid, count, can_enqueue)
  T2  Address update + lookup for ordering violation detection
  T3  Commit releases entry, pointer advances

Uses tiny config: size=4, addr_width=16.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from pycircuit import CycleAwareTb, Tb, compile_cycle_aware, testbench

_XS_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_XS_ROOT) not in sys.path:
    sys.path.insert(0, str(_XS_ROOT))

from mem.lsqueue.load_queue import build_load_queue  # noqa: E402

LQ_SZ = 4
ADDR_W = 16
DATA_W = 16
ROB_IDX_W = 4
IDX_W = 2   # log2(4)
PTR_W = 3


def _zero_inputs(tb: CycleAwareTb) -> None:
    tb.drive("flush", 0)
    tb.drive("enq_valid", 0)
    tb.drive("enq_rob_idx", 0)
    tb.drive("addr_update_valid", 0)
    tb.drive("addr_update_idx", 0)
    tb.drive("addr_update_addr", 0)
    tb.drive("commit_valid", 0)
    tb.drive("lookup_valid", 0)
    tb.drive("lookup_addr", 0)
    tb.drive("redirect_valid", 0)
    tb.drive("redirect_rob_idx", 0)


@testbench
def tb_load_queue_functional(t: Tb) -> None:
    tb = CycleAwareTb(t)
    tb.clock("clk")
    tb.reset("rst", cycles_asserted=2, cycles_deasserted=1)
    tb.timeout(40)

    # ── T1: Enqueue load, track state ────────────────────────────
    _zero_inputs(tb)
    tb.expect("count", 0, msg="T1: empty after reset")
    tb.expect("can_enqueue", 0, msg="T1: can_enqueue=0 (enq_valid=0)")

    tb.next()
    _zero_inputs(tb)
    tb.drive("enq_valid", 1)
    tb.drive("enq_rob_idx", 5)
    tb.expect("can_enqueue", 1, msg="T1: can enqueue when valid + space")
    tb.expect("enq_idx", 0, msg="T1: enqueue at idx 0")

    tb.next()
    _zero_inputs(tb)
    tb.expect("count", 1, msg="T1: count=1 after enqueue")

    # Enqueue second load
    tb.drive("enq_valid", 1)
    tb.drive("enq_rob_idx", 6)

    tb.next()
    _zero_inputs(tb)
    tb.expect("count", 2, msg="T1: count=2 after second enqueue")

    # ── T2: Address update + lookup ──────────────────────────────
    # Update address for entry 0
    tb.drive("addr_update_valid", 1)
    tb.drive("addr_update_idx", 0)
    tb.drive("addr_update_addr", 0x1000)

    tb.next()
    _zero_inputs(tb)

    # Lookup same cache line — should find violation
    # Cache line bits = log2(64) = 6 for default CACHE_LINE_BYTES
    # For 16-bit addr, line_bits = 6, so tag = addr[6:16]
    # 0x1000 tag = 0x1000 >> 6 = 0x40
    tb.drive("lookup_valid", 1)
    tb.drive("lookup_addr", 0x1000)
    tb.expect("violation_found", 1, msg="T2: violation found (same line)")

    tb.next()
    _zero_inputs(tb)

    # Lookup different cache line — no violation
    tb.drive("lookup_valid", 1)
    tb.drive("lookup_addr", 0x2000)
    tb.expect("violation_found", 0, msg="T2: no violation (different line)")

    # ── T3: Commit releases entry ────────────────────────────────
    tb.next()
    _zero_inputs(tb)
    tb.drive("commit_valid", 1)

    tb.next()
    _zero_inputs(tb)
    tb.expect("count", 1, msg="T3: count=1 after commit (dequeued head)")

    # Commit second entry
    tb.drive("commit_valid", 1)

    tb.next()
    _zero_inputs(tb)
    tb.expect("count", 0, msg="T3: count=0 after second commit")

    tb.finish()


# ── L1: MLIR smoke ──────────────────────────────────────────────

@pytest.mark.smoke
def test_load_queue_small_emit_mlir():
    mlir = compile_cycle_aware(
        build_load_queue, name="lq_s", eager=True,
        size=LQ_SZ, addr_width=ADDR_W, data_width=DATA_W,
        rob_idx_width=ROB_IDX_W,
    ).emit_mlir()
    assert "func.func" in mlir
    assert "can_enqueue" in mlir
    assert "violation_found" in mlir


@pytest.mark.smoke
def test_load_queue_default_emit_mlir():
    mlir = compile_cycle_aware(
        build_load_queue, name="load_queue", eager=True,
        size=72, addr_width=36,
    ).emit_mlir()
    assert "func.func" in mlir or "hw." in mlir


@pytest.mark.regcount
def test_load_queue_has_entry_regs():
    import re
    mlir = compile_cycle_aware(
        build_load_queue, name="lq_rc", eager=True,
        size=LQ_SZ, addr_width=ADDR_W, data_width=DATA_W,
        rob_idx_width=ROB_IDX_W,
    ).emit_mlir()
    n = len(re.findall(r"pyc\.reg", mlir))
    # 2 ptrs + 5 fields per entry (valid, addr_valid, committed, addr, rob)
    min_regs = 2 + LQ_SZ * 5
    assert n >= min_regs, f"LoadQueue(sz={LQ_SZ}) needs ≥{min_regs} regs; got {n}"


if __name__ == "__main__":
    test_load_queue_small_emit_mlir()
    print("PASS: test_load_queue_small_emit_mlir")
    test_load_queue_default_emit_mlir()
    print("PASS: test_load_queue_default_emit_mlir")
    test_load_queue_has_entry_regs()
    print("PASS: test_load_queue_has_entry_regs")
