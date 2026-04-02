"""TLB — Translation Lookaside Buffer for XiangShan-pyc.

Fully-associative TLB for virtual-to-physical address translation.
2-cycle pipeline: cycle 0 (CAM lookup), cycle 1 (result output).

Reference: XiangShan/src/main/scala/xiangshan/cache/mmu/TLB.scala

Pipeline:
  c0  Accept lookup request, compare VPN+ASID against all entries (CAM)
  c1  Output PPN on hit; raise miss signal for PTW request

Key parameters (from XiangShan KunMingHu defaults):
  nWays=48, vpnWidth=27 (Sv39), ppnWidth=24, asidWidth=16

Simplified vs full XiangShan:
  - 4KB pages only (no superpage / 2MB / 1GB support)
  - No separate normal-page / super-page sections
  - Round-robin replacement (no pseudo-LRU)
  - Single lookup port (XiangShan has per-pipeline TLBs)
  - No A/D bit management (handled by page-fault exceptions)
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


def build_tlb(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    n_ways: int = ITLB_WAYS,
    vpn_width: int = 27,
    ppn_width: int = 24,
    asid_width: int = ASID_LENGTH,
) -> None:
    """TLB: fully-associative translation lookaside buffer with 2-cycle pipeline."""

    way_bits = max(1, (n_ways - 1).bit_length())

    cd = domain.clock_domain

    # ================================================================
    # Cycle 0 — CAM Lookup: compare VPN+ASID against all entries
    # ================================================================

    flush = cas(domain, m.input("flush", width=1), cycle=0)
    flush_asid_valid = cas(domain, m.input("flush_asid_valid", width=1), cycle=0)
    flush_asid = cas(domain, m.input("flush_asid", width=asid_width), cycle=0)

    lookup_valid = cas(domain, m.input("lookup_valid", width=1), cycle=0)
    lookup_vpn = cas(domain, m.input("lookup_vpn", width=vpn_width), cycle=0)
    lookup_asid = cas(domain, m.input("lookup_asid", width=asid_width), cycle=0)

    refill_valid = cas(domain, m.input("refill_valid", width=1), cycle=0)
    refill_vpn = cas(domain, m.input("refill_vpn", width=vpn_width), cycle=0)
    refill_ppn = cas(domain, m.input("refill_ppn", width=ppn_width), cycle=0)
    refill_asid = cas(domain, m.input("refill_asid", width=asid_width), cycle=0)

    # ── Entry storage (fully-associative CAM) ─────────────────────

    entry_valid = [
        domain.state(width=1, reset_value=0, name=f"e{i}_v")
        for i in range(n_ways)
    ]
    entry_vpn = [
        domain.state(width=vpn_width, reset_value=0, name=f"e{i}_vpn")
        for i in range(n_ways)
    ]
    entry_ppn = [
        domain.state(width=ppn_width, reset_value=0, name=f"e{i}_ppn")
        for i in range(n_ways)
    ]
    entry_asid = [
        domain.state(width=asid_width, reset_value=0, name=f"e{i}_asid")
        for i in range(n_ways)
    ]

    replace_ptr = domain.state(width=way_bits, reset_value=0, name="repl_ptr")

    # ── Read entries as CAS signals at cycle 0 ────────────────────

    ev = [cas(domain, entry_valid[i].wire, cycle=0) for i in range(n_ways)]
    evpn = [cas(domain, entry_vpn[i].wire, cycle=0) for i in range(n_ways)]
    eppn = [cas(domain, entry_ppn[i].wire, cycle=0) for i in range(n_ways)]
    easid = [cas(domain, entry_asid[i].wire, cycle=0) for i in range(n_ways)]

    # ── Per-entry CAM match ───────────────────────────────────────

    way_hit = []
    for i in range(n_ways):
        vpn_eq = (evpn[i] == lookup_vpn)
        asid_eq = (easid[i] == lookup_asid)
        way_hit.append(ev[i] & vpn_eq & asid_eq)

    any_hit = way_hit[0]
    for i in range(1, n_ways):
        any_hit = any_hit | way_hit[i]

    # ── Select PPN from matching entry ────────────────────────────

    hit_ppn = eppn[0]
    for i in range(1, n_ways):
        hit_ppn = mux(way_hit[i], eppn[i], hit_ppn)

    miss = lookup_valid & (~any_hit)

    # ── Pipeline registers c0 → c1 ───────────────────────────────

    s1_valid_w = domain.cycle(lookup_valid.wire, name="s1_v")
    s1_hit_w = domain.cycle(any_hit.wire, name="s1_hit")
    s1_miss_w = domain.cycle(miss.wire, name="s1_miss")
    s1_ppn_w = domain.cycle(hit_ppn.wire, name="s1_ppn")
    s1_vpn_w = domain.cycle(lookup_vpn.wire, name="s1_vpn")

    domain.next()  # ─────────────── c0 → c1 boundary ──────────────

    # ================================================================
    # Cycle 1 — Output (results already in pipeline registers)
    # ================================================================

    domain.next()  # ─────────────── c1 → state-update boundary ────

    # ================================================================
    # State Updates
    # ================================================================

    rptr = replace_ptr.wire
    zero1 = m.const(0, width=1)
    one1 = m.const(1, width=1)

    for i in range(n_ways):
        i_const = m.const(i, width=way_bits)
        is_victim = (rptr == i_const)
        do_write = refill_valid.wire & is_victim

        asid_match = (entry_asid[i].wire == flush_asid.wire)
        selective_flush = flush_asid_valid.wire & asid_match
        invalidate = flush.wire | selective_flush

        new_valid = do_write.select(one1, entry_valid[i].wire)
        new_valid = invalidate.select(zero1, new_valid)
        entry_valid[i].set(new_valid)

        entry_vpn[i].set(do_write.select(refill_vpn.wire, entry_vpn[i].wire))
        entry_ppn[i].set(do_write.select(refill_ppn.wire, entry_ppn[i].wire))
        entry_asid[i].set(do_write.select(refill_asid.wire, entry_asid[i].wire))

    # Advance replace pointer on refill (wrap at n_ways)
    at_limit = (rptr == m.const(n_ways - 1, width=way_bits))
    next_ptr = at_limit.select(
        m.const(0, width=way_bits),
        (rptr + m.const(1, width=way_bits))[0:way_bits],
    )
    replace_ptr.set(refill_valid.wire.select(next_ptr, rptr))

    # ================================================================
    # Output ports
    # ================================================================

    m.output("resp_valid", s1_valid_w)
    m.output("resp_hit", s1_hit_w)
    m.output("resp_miss", s1_miss_w)
    m.output("resp_ppn", s1_ppn_w)

    m.output("ptw_req_valid", s1_miss_w)
    m.output("ptw_req_vpn", s1_vpn_w)


build_tlb.__pycircuit_name__ = "tlb"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_tlb, name="tlb", eager=True,
        n_ways=ITLB_WAYS, vpn_width=27, ppn_width=24,
        asid_width=ASID_LENGTH,
    ).emit_mlir())
