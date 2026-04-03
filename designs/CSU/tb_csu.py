# -*- coding: utf-8 -*-
"""CSU testbench — T-001 / T-014 / T-013 oriented (reset + post-reset idle).

DUT: ``csu.build_csu``. Drive all CHI **in** ports to 0; hold TB ``rst`` long
enough (≥16 posedges per SRC-07 digest, mapped in ``ASSUMPTIONS.md``) so the
Inc-0 pipeline drains to **safe idle** (all ``tx*`` = 0).

Run MLIR smoke (repo root)::

    PYTHONPATH=compiler/frontend python3 designs/CSU/tb_csu.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from pycircuit import CycleAwareTb, Tb, compile_cycle_aware, testbench

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from csu import build_csu  # noqa: E402


@testbench
def tb_csu(t: Tb) -> None:
    tb = CycleAwareTb(t)
    tb.clock("clk")
    # ≥4 主时钟沿以排空 occurrence 流水线；16 对齐 SRC-07 对 SoC 复位脉宽的下限叙述。
    tb.reset("rst", cycles_asserted=16, cycles_deasserted=2)
    tb.timeout(512)

    # --- Cycle 0（复位序列结束后的首个 TB 周期）：空闲输入 → 空闲输出（F-014）---
    tb.drive("rxrsp", 0)
    tb.drive("rxdat", 0)
    tb.drive("rxsnp", 0)
    tb.drive("rsp1_side", 0)
    tb.drive("rxwkup", 0)
    tb.drive("rxerr", 0)
    tb.drive("rxfill", 0)
    tb.drive("tb_txreq_seed", 0)
    tb.drive("tb_issue_req", 0)
    tb.drive("cfg_word", 0)

    tb.expect("txreq", 0, phase="post", msg="T-001/T-014: txreq idle after reset")
    tb.expect("txrsp", 0, phase="post", msg="T-001/T-014: txrsp idle after reset")
    tb.expect("txdat", 0, phase="post", msg="T-001/T-014: txdat idle after reset")
    tb.expect("txreq_pend", 0, phase="post", msg="T-001/T-014: txreq_pend idle after reset")

    tb.finish()


if __name__ == "__main__":
    m = compile_cycle_aware(build_csu, name="tb_csu_top", eager=True)
    print(m.emit_mlir())
