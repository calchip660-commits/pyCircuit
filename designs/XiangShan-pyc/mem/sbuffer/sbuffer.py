"""SBuffer — Store Buffer (merge buffer) for XiangShan-pyc MemBlock.

Sits between the committed store queue and the DCache.  Committed stores
are enqueued; entries sharing the same cache-line address are merged
(data + byte mask OR).  When the buffer reaches a threshold occupancy or
an entry is evicted, it is drained to DCache.

Reference: XiangShan/src/main/scala/xiangshan/mem/sbuffer/Sbuffer.scala

Key features:
  M-SB-001  Fixed-size buffer with per-entry valid/tag/data/mask
  M-SB-002  Merge on enqueue: matching cache-line tag merges data+mask
  M-SB-003  Drain to DCache: oldest/threshold-triggered eviction
  M-SB-004  Flush drains all valid entries
  M-SB-005  Occupancy counter for threshold-based drain policy
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


def build_sbuffer(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    size: int = STORE_BUFFER_SIZE,
    threshold: int = STORE_BUFFER_THRESHOLD,
    addr_width: int = 36,
    data_width: int = XLEN,
    line_bytes: int = CACHE_LINE_BYTES,
) -> None:
    """SBuffer: merge buffer between committed stores and DCache."""

    idx_w = max(1, math.ceil(math.log2(size)))
    line_bits = int(math.log2(line_bytes))
    tag_w = addr_width - line_bits
    mask_w = data_width // 8
    cnt_w = max(1, math.ceil(math.log2(size + 1)))

    # ── Cycle 0: Inputs ──────────────────────────────────────────────

    flush = cas(domain, m.input("flush", width=1), cycle=0)

    enq_valid = cas(domain, m.input("enq_valid", width=1), cycle=0)
    enq_addr = cas(domain, m.input("enq_addr", width=addr_width), cycle=0)
    enq_data = cas(domain, m.input("enq_data", width=data_width), cycle=0)
    enq_mask = cas(domain, m.input("enq_mask", width=mask_w), cycle=0)

    dcache_ready = cas(domain, m.input("dcache_ready", width=1), cycle=0)

    zero1 = cas(domain, m.const(0, width=1), cycle=0)
    one1 = cas(domain, m.const(1, width=1), cycle=0)

    # ── Entry storage ─────────────────────────────────────────────────

    e_valid = [domain.state(width=1, reset_value=0, name=f"sb_v_{i}") for i in range(size)]
    e_tag = [domain.state(width=tag_w, reset_value=0, name=f"sb_t_{i}") for i in range(size)]
    e_data = [domain.state(width=data_width, reset_value=0, name=f"sb_d_{i}") for i in range(size)]
    e_mask = [domain.state(width=mask_w, reset_value=0, name=f"sb_m_{i}") for i in range(size)]

    # ── Occupancy counter ─────────────────────────────────────────────

    occ_r = domain.state(width=cnt_w, reset_value=0, name="sb_occ")
    occ = cas(domain, occ_r.wire, cycle=0)
    above_thresh = occ == cas(domain, m.const(threshold, width=cnt_w), cycle=0)

    enq_tag = enq_addr[line_bits:addr_width]

    # ── Merge check: does any entry match the incoming tag? ──────────

    merge_hit = zero1
    merge_idx = cas(domain, m.const(0, width=idx_w), cycle=0)
    for j in range(size):
        ev = cas(domain, e_valid[j].wire, cycle=0)
        et = cas(domain, e_tag[j].wire, cycle=0)
        tag_eq = et == enq_tag
        hit = ev & tag_eq & enq_valid
        merge_hit = mux(hit, one1, merge_hit)
        merge_idx = mux(hit, cas(domain, m.const(j, width=idx_w), cycle=0), merge_idx)

    # ── Allocate: find first free slot ───────────────────────────────

    alloc_found = zero1
    alloc_idx = cas(domain, m.const(0, width=idx_w), cycle=0)
    for j in range(size):
        ev = cas(domain, e_valid[j].wire, cycle=0)
        is_free = (~ev) & (~alloc_found)
        alloc_found = mux(is_free, one1, alloc_found)
        alloc_idx = mux(is_free, cas(domain, m.const(j, width=idx_w), cycle=0), alloc_idx)

    can_alloc = alloc_found | merge_hit
    full = (~alloc_found) & (~merge_hit)

    # ── Drain: select oldest valid entry for DCache writeback ────────

    drain_valid = zero1
    drain_idx = cas(domain, m.const(0, width=idx_w), cycle=0)
    drain_tag = cas(domain, m.const(0, width=tag_w), cycle=0)
    drain_data = cas(domain, m.const(0, width=data_width), cycle=0)
    drain_mask = cas(domain, m.const(0, width=mask_w), cycle=0)

    for j in range(size):
        ev = cas(domain, e_valid[j].wire, cycle=0)
        should_drain = ev & (~drain_valid)
        drain_valid = mux(should_drain, one1, drain_valid)
        drain_idx = mux(should_drain, cas(domain, m.const(j, width=idx_w), cycle=0), drain_idx)
        drain_tag = mux(should_drain, cas(domain, e_tag[j].wire, cycle=0), drain_tag)
        drain_data = mux(should_drain, cas(domain, e_data[j].wire, cycle=0), drain_data)
        drain_mask = mux(should_drain, cas(domain, e_mask[j].wire, cycle=0), drain_mask)

    do_drain = drain_valid & dcache_ready & (above_thresh | full | flush)
    drain_addr = cas(domain,
                     m.cat(drain_tag.wire, m.const(0, width=line_bits)),
                     cycle=0)

    m.output("dcache_wr_valid", do_drain.wire)
    m.output("dcache_wr_addr", drain_addr.wire)
    m.output("dcache_wr_data", drain_data.wire)
    m.output("dcache_wr_mask", drain_mask.wire)
    m.output("ready", can_alloc.wire)

    # ── domain.next() → Cycle 1: state updates ──────────────────────
    domain.next()

    # Merge or allocate on enqueue
    do_enq = enq_valid & (~flush)
    for j in range(size):
        j_const = cas(domain, m.const(j, width=idx_w), cycle=0)
        old_v = cas(domain, e_valid[j].wire, cycle=0)
        old_d = cas(domain, e_data[j].wire, cycle=0)
        old_m = cas(domain, e_mask[j].wire, cycle=0)

        # Merge path
        is_merge = do_enq & merge_hit & (merge_idx == j_const)
        merged_data = cas(domain, (old_d.wire & ~enq_data.wire) | enq_data.wire, cycle=0)
        merged_mask = cas(domain, (old_m.wire | enq_mask.wire)[0:mask_w], cycle=0)
        e_data[j].set(mux(is_merge, merged_data, old_d), when=is_merge)
        e_mask[j].set(mux(is_merge, merged_mask, old_m), when=is_merge)

        # Allocate path
        is_alloc = do_enq & (~merge_hit) & (alloc_idx == j_const) & alloc_found
        e_valid[j].set(mux(is_alloc, one1, old_v), when=is_alloc)
        e_tag[j].set(mux(is_alloc, enq_tag, cas(domain, e_tag[j].wire, cycle=0)), when=is_alloc)
        e_data[j].set(mux(is_alloc, enq_data, old_d), when=is_alloc)
        e_mask[j].set(mux(is_alloc, enq_mask, old_m), when=is_alloc)

        # Drain: invalidate drained entry
        is_drain = do_drain & (drain_idx == j_const)
        e_valid[j].set(mux(is_drain, zero1, old_v), when=is_drain)

    # Flush: invalidate all
    for j in range(size):
        e_valid[j].set(zero1, when=flush)

    # Occupancy update
    enq_inc = do_enq & (~merge_hit) & alloc_found
    net = mux(enq_inc & (~do_drain),
              cas(domain, (occ.wire + u(cnt_w, 1))[0:cnt_w], cycle=0),
              mux(do_drain & (~enq_inc),
                  cas(domain, (occ.wire - u(cnt_w, 1))[0:cnt_w], cycle=0),
                  occ))
    net = mux(flush, cas(domain, m.const(0, width=cnt_w), cycle=0), net)
    occ_r.set(net)


build_sbuffer.__pycircuit_name__ = "sbuffer"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_sbuffer, name="sbuffer", eager=True,
        size=4, threshold=2, addr_width=36,
    ).emit_mlir())
