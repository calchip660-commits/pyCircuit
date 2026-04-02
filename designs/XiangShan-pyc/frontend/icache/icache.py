"""ICache — Instruction Cache for XiangShan-pyc.

VIPT (Virtual Index Physical Tag) set-associative instruction cache.
4-stage pipeline: s0 (request), s1 (tag compare), s2 (hit-miss), s3 (response).

Reference: XiangShan/src/main/scala/xiangshan/frontend/icache/

Pipeline:
  s0  Accept fetch request, compute set index, read Tag/Data SRAMs
  s1  Tag compare: match physical tag, generate per-way hit vector
  s2  Data mux on hit; MSHR allocation on miss; refill bypass
  s3  Drive response (valid, data, hit) to IFU

Key parameters (from XiangShan KunMingHu defaults):
  nSets=256, nWays=4, blockBytes=64  →  64 KB, VIPT

Simplified vs full XiangShan:
  - Single MSHR entry (XiangShan has 4 fetch + 10 prefetch MSHRs)
  - No ECC / parity
  - No prefetch pipe or WayLookup queue
  - No TileLink coherence (Probe/Release)
  - Pipeline flush kills in-flight requests; no content invalidation here
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
from top.parameters import ICACHE_SETS, ICACHE_WAYS, ICACHE_BLOCK_BYTES, PC_WIDTH, CACHE_LINE_SIZE


def build_icache(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    n_sets: int = ICACHE_SETS,
    n_ways: int = ICACHE_WAYS,
    block_bytes: int = ICACHE_BLOCK_BYTES,
    pc_width: int = PC_WIDTH,
) -> None:
    """ICache: VIPT set-associative instruction cache with 4-stage pipeline."""

    block_bits = block_bytes * 8
    offset_bits = int(math.log2(block_bytes))
    index_bits = int(math.log2(n_sets))
    tag_bits = pc_width - index_bits - offset_bits
    way_bits = max(1, int(math.log2(n_ways)))
    tag_strobe_w = (tag_bits + 7) // 8
    data_strobe_w = block_bytes

    cd = domain.clock_domain

    # ================================================================
    # s0 — Request: accept fetch, decompose address, read SRAMs
    # ================================================================

    flush = cas(domain, m.input("flush", width=1), cycle=0)
    fetch_valid = cas(domain, m.input("fetch_valid", width=1), cycle=0)
    fetch_vaddr = cas(domain, m.input("fetch_vaddr", width=pc_width), cycle=0)
    fetch_ptag = cas(domain, m.input("fetch_ptag", width=tag_bits), cycle=0)

    refill_valid = cas(domain, m.input("refill_valid", width=1), cycle=0)
    refill_set = cas(domain, m.input("refill_set", width=index_bits), cycle=0)
    refill_tag = cas(domain, m.input("refill_tag", width=tag_bits), cycle=0)
    refill_way = cas(domain, m.input("refill_way", width=way_bits), cycle=0)
    refill_data = cas(domain, m.input("refill_data", width=block_bits), cycle=0)

    s0_set_idx = fetch_vaddr[offset_bits:offset_bits + index_bits]
    s0_fire = fetch_valid & (~flush)

    # ── Feedback state (registers read at cycle 0, updated at end) ──

    valid_regs = [
        domain.state(width=n_sets, reset_value=0, name=f"vld{w}")
        for w in range(n_ways)
    ]

    mshr_valid = domain.state(width=1, reset_value=0, name="mshr_v")
    mshr_set = domain.state(width=index_bits, reset_value=0, name="mshr_set")
    mshr_tag = domain.state(width=tag_bits, reset_value=0, name="mshr_tag")

    # ── Per-way Tag & Data SRAMs (synchronous read) ─────────────────
    # Address presented at s0; read data available one cycle later (s1).

    tag_rd = []
    data_rd = []
    for w in range(n_ways):
        w_const = cas(domain, m.const(w, width=way_bits), cycle=0)
        wr_en_w = (refill_valid & (refill_way == w_const)).wire

        tag_rd.append(m.sync_mem(
            cd.clk, cd.rst,
            ren=s0_fire.wire, raddr=s0_set_idx.wire,
            wvalid=wr_en_w, waddr=refill_set.wire,
            wdata=refill_tag.wire,
            wstrb=m.const((1 << tag_strobe_w) - 1, width=tag_strobe_w),
            depth=n_sets, name=f"tag_w{w}",
        ))

        data_rd.append(m.sync_mem(
            cd.clk, cd.rst,
            ren=s0_fire.wire, raddr=s0_set_idx.wire,
            wvalid=wr_en_w, waddr=refill_set.wire,
            wdata=refill_data.wire,
            wstrb=m.const((1 << data_strobe_w) - 1, width=data_strobe_w),
            depth=n_sets, name=f"data_w{w}",
        ))

    # ── Pipeline registers s0 → s1 ─────────────────────────────────

    s1_valid_w = domain.cycle(s0_fire.wire, name="s1_v")
    s1_set_idx_w = domain.cycle(s0_set_idx.wire, name="s1_set")
    s1_ptag_w = domain.cycle(fetch_ptag.wire, name="s1_ptag")
    s1_vaddr_w = domain.cycle(fetch_vaddr.wire, name="s1_va")

    domain.next()  # ─────────────── s0 → s1 boundary ───────────────

    # ================================================================
    # s1 — Tag Compare: match physical tag against each way
    # ================================================================

    s1_way_hit = []
    for w in range(n_ways):
        vld_bit = valid_regs[w].wire.lshr(amount=s1_set_idx_w)[0:1]
        tag_eq = (tag_rd[w][0:tag_bits] == s1_ptag_w)
        s1_way_hit.append(vld_bit & tag_eq)

    s1_any_hit = s1_way_hit[0]
    for w in range(1, n_ways):
        s1_any_hit = s1_any_hit | s1_way_hit[w]

    s1_miss = s1_valid_w & (~s1_any_hit)

    s1_hit_data = data_rd[0]
    for w in range(1, n_ways):
        s1_hit_data = s1_way_hit[w].select(data_rd[w], s1_hit_data)

    # ── Pipeline registers s1 → s2 ─────────────────────────────────

    s2_valid_w = domain.cycle(s1_valid_w, name="s2_v")
    s2_hit_w = domain.cycle(s1_any_hit, name="s2_hit")
    s2_miss_w = domain.cycle(s1_miss, name="s2_miss")
    s2_data_w = domain.cycle(s1_hit_data, name="s2_data")
    s2_set_idx_w = domain.cycle(s1_set_idx_w, name="s2_set")
    s2_ptag_w = domain.cycle(s1_ptag_w, name="s2_ptag")

    domain.next()  # ─────────────── s1 → s2 boundary ───────────────

    # ================================================================
    # s2 — Data Mux / Hit-Miss: finalize, MSHR allocation, refill bypass
    # ================================================================

    mshr_free = ~mshr_valid.wire
    mshr_alloc = s2_miss_w & s2_valid_w & mshr_free

    s2_refill_match = (
        refill_valid.wire
        & (refill_set.wire == s2_set_idx_w)
        & (refill_tag.wire == s2_ptag_w)
    )

    s2_resp_hit = s2_hit_w | s2_refill_match
    s2_resp_data = s2_refill_match.select(refill_data.wire, s2_data_w)
    s2_resp_valid = s2_valid_w & s2_resp_hit

    # ── Pipeline registers s2 → s3 ─────────────────────────────────

    s3_valid_w = domain.cycle(s2_resp_valid, name="s3_v")
    s3_hit_w = domain.cycle(s2_resp_hit, name="s3_hit")
    s3_data_w = domain.cycle(s2_resp_data, name="s3_data")

    domain.next()  # ─────────────── s2 → s3 boundary ───────────────

    # ================================================================
    # s3 — Response to IFU
    # ================================================================

    # (outputs collected at end of function)

    domain.next()  # ─────────────── s3 → state-update boundary ─────

    # ================================================================
    # State Updates
    # ================================================================

    # Valid bits: set way-valid on refill (no full-flush in simplified model)
    for w in range(n_ways):
        wr_way = refill_valid.wire & (refill_way.wire == m.const(w, width=way_bits))
        one_hot = m.const(1, width=n_sets).shl(amount=refill_set.wire)
        new_vld = valid_regs[w].wire | one_hot
        valid_regs[w].set(wr_way.select(new_vld, valid_regs[w].wire))

    # MSHR: allocate on miss, clear on refill completion, clear on flush
    mshr_clear = refill_valid.wire & mshr_valid.wire
    nv = mshr_clear.select(
        m.const(0, width=1),
        mshr_alloc.select(m.const(1, width=1), mshr_valid.wire),
    )
    nv = flush.wire.select(m.const(0, width=1), nv)
    mshr_valid.set(nv)

    mshr_set.set(mshr_alloc.select(s2_set_idx_w, mshr_set.wire))
    mshr_tag.set(mshr_alloc.select(s2_ptag_w, mshr_tag.wire))

    # ================================================================
    # Output ports
    # ================================================================

    m.output("resp_valid", s3_valid_w)
    m.output("resp_data", s3_data_w)
    m.output("resp_hit", s3_hit_w)

    m.output("miss_valid", mshr_alloc)
    m.output("miss_addr", m.cat(
        s2_ptag_w,
        s2_set_idx_w,
        m.const(0, width=offset_bits),
    ))


build_icache.__pycircuit_name__ = "icache"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_icache, name="icache", eager=True,
        n_sets=ICACHE_SETS, n_ways=ICACHE_WAYS,
        block_bytes=ICACHE_BLOCK_BYTES, pc_width=PC_WIDTH,
    ).emit_mlir())
