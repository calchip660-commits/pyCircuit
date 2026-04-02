"""Store Unit — 2-stage store pipeline for XiangShan-pyc MemBlock.

Pipeline:
  s0  Address generation: compute virtual address, issue TLB lookup
  s1  TLB result: write translated address + data to store queue

Reference: XiangShan/src/main/scala/xiangshan/mem/pipeline/StoreUnit.scala

Key features:
  M-SU-001  2-stage pipelined store execution
  M-SU-002  TLB lookup in s0, store queue write in s1
  M-SU-003  Pipeline kill on redirect
  M-SU-004  Writeback acknowledgement with rob_idx
"""
from __future__ import annotations

import math
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
from top.parameters import *


def build_store_unit(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    data_width: int = XLEN,
    addr_width: int = PC_WIDTH,
    rob_idx_width: int = ROB_IDX_WIDTH,
    sq_idx_width: int = SQ_IDX_WIDTH,
    ppn_width: int = 24,
) -> None:
    """Store Unit: 2-stage pipeline (addr-gen/TLB → store queue write)."""

    # ================================================================
    # s0 — Address Generation + TLB request
    # ================================================================

    flush = cas(domain, m.input("flush", width=1), cycle=0)

    issue_valid = cas(domain, m.input("issue_valid", width=1), cycle=0)
    issue_addr = cas(domain, m.input("issue_addr", width=addr_width), cycle=0)
    issue_data = cas(domain, m.input("issue_data", width=data_width), cycle=0)
    issue_rob_idx = cas(domain, m.input("issue_rob_idx", width=rob_idx_width), cycle=0)
    issue_sq_idx = cas(domain, m.input("issue_sq_idx", width=sq_idx_width), cycle=0)

    # TLB response (arrives in s1)
    tlb_resp_hit = cas(domain, m.input("tlb_resp_hit", width=1), cycle=0)
    tlb_resp_ppn = cas(domain, m.input("tlb_resp_ppn", width=ppn_width), cycle=0)

    s0_fire = issue_valid & (~flush)
    s0_vpn = issue_addr[12:12 + (addr_width - 12)]

    m.output("tlb_req_valid", s0_fire.wire)
    m.output("tlb_req_vpn", s0_vpn.wire)

    # ── Pipeline registers s0 → s1 ───────────────────────────────

    s1_valid_w = domain.cycle(s0_fire.wire, name="s1_v")
    s1_addr_w = domain.cycle(issue_addr.wire, name="s1_addr")
    s1_data_w = domain.cycle(issue_data.wire, name="s1_data")
    s1_rob_idx_w = domain.cycle(issue_rob_idx.wire, name="s1_rob")
    s1_sq_idx_w = domain.cycle(issue_sq_idx.wire, name="s1_sq")

    domain.next()  # ─────────────── s0 → s1 boundary ──────────────

    # ================================================================
    # s1 — TLB result + Store Queue write
    # ================================================================

    s1_kill = flush.wire
    s1_alive = s1_valid_w & (~s1_kill)
    s1_tlb_miss = s1_alive & (~tlb_resp_hit.wire)

    paddr_lo = s1_addr_w[0:12]
    s1_paddr = m.cat(tlb_resp_ppn.wire, paddr_lo)

    s1_sq_fire = s1_alive & tlb_resp_hit.wire

    domain.next()  # ─────────────── s1 → output boundary ─────────

    # ================================================================
    # Output ports
    # ================================================================

    m.output("sq_write_valid", s1_sq_fire)
    m.output("sq_write_idx", s1_sq_idx_w)
    m.output("sq_write_addr", s1_paddr)
    m.output("sq_write_data", s1_data_w)

    m.output("wb_valid", s1_sq_fire)
    m.output("wb_rob_idx", s1_rob_idx_w)

    m.output("tlb_miss", s1_tlb_miss)


build_store_unit.__pycircuit_name__ = "store_unit"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_store_unit, name="store_unit", eager=True,
    ).emit_mlir())
