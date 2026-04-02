"""Prefetcher — simple stride prefetcher for XiangShan-pyc MemBlock.

Monitors load addresses and detects stride patterns.  When a consistent
stride is observed for a given PC, a prefetch request is issued for the
predicted next address.

Reference: XiangShan/src/main/scala/xiangshan/mem/prefetch/

Key features:
  M-PF-001  Per-PC stride tracking table
  M-PF-002  Confidence counter: consistent stride increments confidence
  M-PF-003  Prefetch issued when confidence exceeds threshold
  M-PF-004  Table replacement via round-robin pointer
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


PREFETCH_TABLE_SIZE = 16
PREFETCH_CONF_WIDTH = 3
PREFETCH_CONF_THRESHOLD = 4
STRIDE_WIDTH = 12
PREFETCH_PC_TAG_WIDTH = 12


def build_prefetcher(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    table_size: int = PREFETCH_TABLE_SIZE,
    conf_width: int = PREFETCH_CONF_WIDTH,
    conf_threshold: int = PREFETCH_CONF_THRESHOLD,
    stride_width: int = STRIDE_WIDTH,
    pc_tag_width: int = PREFETCH_PC_TAG_WIDTH,
    addr_width: int = 36,
) -> None:
    """Prefetcher: simple stride-based prefetch predictor."""

    idx_w = max(1, math.ceil(math.log2(table_size)))
    conf_max = (1 << conf_width) - 1

    # ── Cycle 0: Inputs ──────────────────────────────────────────────

    train_valid = cas(domain, m.input("train_valid", width=1), cycle=0)
    train_pc = cas(domain, m.input("train_pc", width=PC_WIDTH), cycle=0)
    train_addr = cas(domain, m.input("train_addr", width=addr_width), cycle=0)

    zero1 = cas(domain, m.const(0, width=1), cycle=0)
    one1 = cas(domain, m.const(1, width=1), cycle=0)

    # ── Table storage ─────────────────────────────────────────────────

    e_valid = [domain.state(width=1, reset_value=0, name=f"pf_v_{i}") for i in range(table_size)]
    e_pc_tag = [domain.state(width=pc_tag_width, reset_value=0, name=f"pf_pc_{i}") for i in range(table_size)]
    e_last_addr = [domain.state(width=addr_width, reset_value=0, name=f"pf_la_{i}") for i in range(table_size)]
    e_stride = [domain.state(width=stride_width, reset_value=0, name=f"pf_st_{i}") for i in range(table_size)]
    e_conf = [domain.state(width=conf_width, reset_value=0, name=f"pf_cf_{i}") for i in range(table_size)]

    repl_ptr_r = domain.state(width=idx_w, reset_value=0, name="pf_rptr")
    repl_ptr = cas(domain, repl_ptr_r.wire, cycle=0)

    # ── Lookup: find matching PC tag ────────────────────────────────

    lookup_tag = train_pc[2:2 + pc_tag_width]

    tbl_hit = zero1
    tbl_idx = cas(domain, m.const(0, width=idx_w), cycle=0)
    tbl_last_addr = cas(domain, m.const(0, width=addr_width), cycle=0)
    tbl_stride = cas(domain, m.const(0, width=stride_width), cycle=0)
    tbl_conf = cas(domain, m.const(0, width=conf_width), cycle=0)

    for j in range(table_size):
        ev = cas(domain, e_valid[j].wire, cycle=0)
        ept = cas(domain, e_pc_tag[j].wire, cycle=0)
        tag_eq = ept == lookup_tag
        hit = train_valid & ev & tag_eq
        tbl_hit = mux(hit, one1, tbl_hit)
        tbl_idx = mux(hit, cas(domain, m.const(j, width=idx_w), cycle=0), tbl_idx)
        tbl_last_addr = mux(hit, cas(domain, e_last_addr[j].wire, cycle=0), tbl_last_addr)
        tbl_stride = mux(hit, cas(domain, e_stride[j].wire, cycle=0), tbl_stride)
        tbl_conf = mux(hit, cas(domain, e_conf[j].wire, cycle=0), tbl_conf)

    # Compute new stride from address difference
    new_stride = cas(domain, (train_addr.wire - tbl_last_addr.wire)[0:stride_width], cycle=0)
    stride_match = new_stride == tbl_stride

    # Prefetch output: if confidence above threshold, issue prefetch
    conf_above = tbl_conf == cas(domain, m.const(conf_max, width=conf_width), cycle=0)
    pf_addr = cas(domain, (train_addr.wire + tbl_stride.wire)[0:addr_width], cycle=0)
    pf_valid = train_valid & tbl_hit & conf_above

    m.output("pf_valid", pf_valid.wire)
    m.output("pf_addr", pf_addr.wire)

    # ── domain.next() → Cycle 1: table update ───────────────────────
    domain.next()

    for j in range(table_size):
        j_const = cas(domain, m.const(j, width=idx_w), cycle=0)
        old_v = cas(domain, e_valid[j].wire, cycle=0)
        old_la = cas(domain, e_last_addr[j].wire, cycle=0)
        old_st = cas(domain, e_stride[j].wire, cycle=0)
        old_cf = cas(domain, e_conf[j].wire, cycle=0)

        is_hit_entry = tbl_hit & (tbl_idx == j_const)
        we_hit = train_valid & is_hit_entry

        # Stride match → increment confidence; mismatch → reset
        cf_inc = mux(old_cf == cas(domain, m.const(conf_max, width=conf_width), cycle=0),
                      old_cf,
                      cas(domain, (old_cf.wire + u(conf_width, 1))[0:conf_width], cycle=0))
        new_cf = mux(stride_match, cf_inc, cas(domain, m.const(0, width=conf_width), cycle=0))
        new_st_val = mux(stride_match, old_st, new_stride)

        e_last_addr[j].set(mux(we_hit, train_addr, old_la), when=we_hit)
        e_stride[j].set(mux(we_hit, new_st_val, old_st), when=we_hit)
        e_conf[j].set(mux(we_hit, new_cf, old_cf), when=we_hit)

        # Allocation on miss: use round-robin pointer
        is_victim = (~tbl_hit) & (repl_ptr == j_const)
        we_alloc = train_valid & is_victim
        e_valid[j].set(mux(we_alloc, one1, old_v), when=we_alloc)
        e_pc_tag[j].set(mux(we_alloc, lookup_tag, cas(domain, e_pc_tag[j].wire, cycle=0)), when=we_alloc)
        e_last_addr[j].set(mux(we_alloc, train_addr, old_la), when=we_alloc)
        e_stride[j].set(mux(we_alloc, cas(domain, m.const(0, width=stride_width), cycle=0), old_st), when=we_alloc)
        e_conf[j].set(mux(we_alloc, cas(domain, m.const(0, width=conf_width), cycle=0), old_cf), when=we_alloc)

    # Advance replacement pointer on miss
    at_limit = repl_ptr == cas(domain, m.const(table_size - 1, width=idx_w), cycle=0)
    next_ptr = mux(at_limit,
                   cas(domain, m.const(0, width=idx_w), cycle=0),
                   cas(domain, (repl_ptr.wire + u(idx_w, 1))[0:idx_w], cycle=0))
    repl_ptr_r.set(mux(train_valid & (~tbl_hit), next_ptr, repl_ptr))


build_prefetcher.__pycircuit_name__ = "prefetcher"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_prefetcher, name="prefetcher", eager=True,
        table_size=4, addr_width=36,
    ).emit_mlir())
