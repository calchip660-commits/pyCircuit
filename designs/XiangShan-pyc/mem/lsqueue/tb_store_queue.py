"""Testbench for Store Queue — MLIR smoke (L1) + functional directed (L2).

L2 scenarios:
  T1  Enqueue store, verify state (valid, count, can_enqueue)
  T2  Store-to-load forwarding — write addr/data, then forward lookup
  T3  Commit + drain releases entry

Uses tiny config: size=4, addr_width=16, data_width=16.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pycircuit import CycleAwareTb, Tb, compile_cycle_aware, testbench

_XS_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_XS_ROOT) not in sys.path:
    sys.path.insert(0, str(_XS_ROOT))

from mem.lsqueue.store_queue import build_store_queue  # noqa: E402

SQ_SZ = 4
ADDR_W = 16
DATA_W = 16
ROB_IDX_W = 4
IDX_W = 2   # log2(4)
PTR_W = 3


def _zero_inputs(tb: CycleAwareTb) -> None:
    tb.drive("flush", 0)
    tb.drive("enq_valid", 0)
    tb.drive("enq_rob_idx", 0)
    tb.drive("write_valid", 0)
    tb.drive("write_idx", 0)
    tb.drive("write_addr", 0)
    tb.drive("write_data", 0)
    tb.drive("commit_valid", 0)
    tb.drive("fwd_valid", 0)
    tb.drive("fwd_addr", 0)
    tb.drive("sbuf_ready", 0)
    tb.drive("redirect_valid", 0)


@testbench
def tb_store_queue_functional(t: Tb) -> None:
    tb = CycleAwareTb(t)
    tb.clock("clk")
    tb.reset("rst", cycles_asserted=2, cycles_deasserted=1)
    tb.timeout(50)

    # ── T1: Enqueue store ────────────────────────────────────────
    _zero_inputs(tb)
    tb.expect("count", 0, msg="T1: empty after reset")

    tb.next()
    _zero_inputs(tb)
    tb.drive("enq_valid", 1)
    tb.drive("enq_rob_idx", 3)
    tb.expect("can_enqueue", 1, msg="T1: can enqueue when space available")
    tb.expect("enq_idx", 0, msg="T1: enqueue at idx 0")

    tb.next()
    _zero_inputs(tb)
    tb.expect("count", 1, msg="T1: count=1 after enqueue")

    # ── T2: Store-to-load forwarding ─────────────────────────────
    # Write address and data to entry 0
    tb.drive("write_valid", 1)
    tb.drive("write_idx", 0)
    tb.drive("write_addr", 0x1000)
    tb.drive("write_data", 0xBEEF)

    tb.next()
    _zero_inputs(tb)

    # Forward lookup on same cache line
    tb.drive("fwd_valid", 1)
    tb.drive("fwd_addr", 0x1000)
    tb.expect("fwd_hit", 1, msg="T2: forwarding hit (same line)")
    tb.expect("fwd_data", 0xBEEF, msg="T2: forwarded data matches")

    tb.next()
    _zero_inputs(tb)

    # Forward lookup on different line — no hit
    tb.drive("fwd_valid", 1)
    tb.drive("fwd_addr", 0x2000)
    tb.expect("fwd_hit", 0, msg="T2: no forwarding hit (different line)")

    # ── T3: Commit + drain releases entry ────────────────────────
    tb.next()
    _zero_inputs(tb)
    tb.drive("commit_valid", 1)

    tb.next()
    _zero_inputs(tb)
    # Entry is committed; drain when sbuf_ready
    tb.drive("sbuf_ready", 1)
    tb.expect("sbuf_valid", 1, msg="T3: drain valid after commit")
    tb.expect("sbuf_data", 0xBEEF, msg="T3: drain data matches")

    tb.next()
    _zero_inputs(tb)
    tb.expect("count", 0, msg="T3: count=0 after drain")

    tb.finish()


# ── L1: MLIR smoke ──────────────────────────────────────────────

@pytest.mark.smoke
def test_store_queue_small_emit_mlir():
    mlir = compile_cycle_aware(
        build_store_queue, name="sq_s", eager=True,
        size=SQ_SZ, addr_width=ADDR_W, data_width=DATA_W,
        rob_idx_width=ROB_IDX_W,
    ).emit_mlir()
    assert "func.func" in mlir
    assert "can_enqueue" in mlir
    assert "fwd_hit" in mlir
    assert "sbuf_valid" in mlir


@pytest.mark.smoke
def test_store_queue_default_emit_mlir():
    mlir = compile_cycle_aware(
        build_store_queue, name="store_queue", eager=True,
        size=56, addr_width=36,
    ).emit_mlir()
    assert "func.func" in mlir or "hw." in mlir


@pytest.mark.regcount
def test_store_queue_has_entry_regs():
    import re
    mlir = compile_cycle_aware(
        build_store_queue, name="sq_rc", eager=True,
        size=SQ_SZ, addr_width=ADDR_W, data_width=DATA_W,
        rob_idx_width=ROB_IDX_W,
    ).emit_mlir()
    n = len(re.findall(r"pyc\.reg", mlir))
    # 3 ptrs + 6 fields per entry (valid, addr_valid, committed, addr, data, rob)
    min_regs = 3 + SQ_SZ * 6
    assert n >= min_regs, f"StoreQueue(sz={SQ_SZ}) needs ≥{min_regs} regs; got {n}"


if __name__ == "__main__":
    test_store_queue_small_emit_mlir()
    print("PASS: test_store_queue_small_emit_mlir")
    test_store_queue_default_emit_mlir()
    print("PASS: test_store_queue_default_emit_mlir")
    test_store_queue_has_entry_regs()
    print("PASS: test_store_queue_has_entry_regs")
