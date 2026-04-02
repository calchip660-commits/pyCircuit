"""Load Unit — 3-stage load pipeline for XiangShan-pyc MemBlock.

Pipeline:
  s0  Address generation: compute virtual address, issue TLB lookup
  s1  DCache access: use translated physical address to read DCache
  s2  Data return: select data (cache hit / forwarded), writeback result

Reference: XiangShan/src/main/scala/xiangshan/mem/pipeline/LoadUnit.scala

Key features:
  M-LU-001  3-stage pipelined load execution
  M-LU-002  TLB lookup in s0, DCache access in s1
  M-LU-003  Store-to-load forwarding check in s2
  M-LU-004  Pipeline kill on redirect (branch misprediction)
  M-LU-005  Writeback to register file with rob_idx tracking
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


def build_load_unit(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    data_width: int = XLEN,
    addr_width: int = PC_WIDTH,
    rob_idx_width: int = ROB_IDX_WIDTH,
    lq_idx_width: int = LQ_IDX_WIDTH,
    ppn_width: int = 24,
) -> None:
    """Load Unit: 3-stage pipeline (addr-gen → TLB/DCache → writeback)."""

    offset_bits = int(math.log2(CACHE_LINE_BYTES))

    # ================================================================
    # s0 — Address Generation + TLB request
    # ================================================================

    flush = cas(domain, m.input("flush", width=1), cycle=0)

    issue_valid = cas(domain, m.input("issue_valid", width=1), cycle=0)
    issue_addr = cas(domain, m.input("issue_addr", width=addr_width), cycle=0)
    issue_rob_idx = cas(domain, m.input("issue_rob_idx", width=rob_idx_width), cycle=0)
    issue_lq_idx = cas(domain, m.input("issue_lq_idx", width=lq_idx_width), cycle=0)

    # Store buffer forwarding interface (checked in s2)
    fwd_valid = cas(domain, m.input("fwd_valid", width=1), cycle=0)
    fwd_data = cas(domain, m.input("fwd_data", width=data_width), cycle=0)

    # TLB response (arrives in s1 for s0's request)
    tlb_resp_hit = cas(domain, m.input("tlb_resp_hit", width=1), cycle=0)
    tlb_resp_ppn = cas(domain, m.input("tlb_resp_ppn", width=ppn_width), cycle=0)

    # DCache response (arrives in s2)
    dcache_resp_valid = cas(domain, m.input("dcache_resp_valid", width=1), cycle=0)
    dcache_resp_data = cas(domain, m.input("dcache_resp_data", width=data_width), cycle=0)

    s0_fire = issue_valid & (~flush)
    s0_vpn = issue_addr[12:12 + (addr_width - 12)]

    # TLB request
    m.output("tlb_req_valid", s0_fire.wire)
    m.output("tlb_req_vpn", s0_vpn.wire)

    # ── Pipeline registers s0 → s1 ───────────────────────────────

    s1_valid_w = domain.cycle(s0_fire.wire, name="s1_v")
    s1_addr_w = domain.cycle(issue_addr.wire, name="s1_addr")
    s1_rob_idx_w = domain.cycle(issue_rob_idx.wire, name="s1_rob")
    s1_lq_idx_w = domain.cycle(issue_lq_idx.wire, name="s1_lq")

    domain.next()  # ─────────────── s0 → s1 boundary ──────────────

    # ================================================================
    # s1 — TLB result + DCache access
    # ================================================================

    s1_kill = flush.wire
    s1_alive = s1_valid_w & (~s1_kill)
    s1_tlb_miss = s1_alive & (~tlb_resp_hit.wire)

    paddr_lo = s1_addr_w[0:12]
    s1_paddr = m.cat(tlb_resp_ppn.wire, paddr_lo)
    paddr_width = ppn_width + 12

    s1_dcache_fire = s1_alive & tlb_resp_hit.wire

    m.output("dcache_req_valid", s1_dcache_fire)
    m.output("dcache_req_addr", s1_paddr)

    # Load queue update with translated address
    m.output("lq_update_valid", s1_alive)
    m.output("lq_update_idx", s1_lq_idx_w)
    m.output("lq_update_addr", s1_paddr)

    # ── Pipeline registers s1 → s2 ───────────────────────────────

    s2_valid_w = domain.cycle(s1_dcache_fire, name="s2_v")
    s2_rob_idx_w = domain.cycle(s1_rob_idx_w, name="s2_rob")
    s2_lq_idx_w = domain.cycle(s1_lq_idx_w, name="s2_lq")
    s2_paddr_w = domain.cycle(s1_paddr, name="s2_pa")

    domain.next()  # ─────────────── s1 → s2 boundary ──────────────

    # ================================================================
    # s2 — Data return + forwarding check + writeback
    # ================================================================

    s2_kill = flush.wire
    s2_alive = s2_valid_w & (~s2_kill)

    s2_data = fwd_valid.wire.select(fwd_data.wire, dcache_resp_data.wire)
    s2_hit = dcache_resp_valid.wire | fwd_valid.wire

    wb_valid = s2_alive & s2_hit
    wb_data = s2_data

    domain.next()  # ─────────────── s2 → output boundary ─────────

    # ================================================================
    # Output ports
    # ================================================================

    m.output("wb_valid", wb_valid)
    m.output("wb_data", wb_data)
    m.output("wb_rob_idx", s2_rob_idx_w)
    m.output("wb_lq_idx", s2_lq_idx_w)

    m.output("tlb_miss", s1_tlb_miss)


build_load_unit.__pycircuit_name__ = "load_unit"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_load_unit, name="load_unit", eager=True,
    ).emit_mlir())
