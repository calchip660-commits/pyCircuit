"""uBTB — Micro Branch Target Buffer for XiangShan-pyc.

Full-associative branch target buffer providing single-cycle (NLP) predictions.
PC tag is matched against all entries; on hit the stored target / taken / branch
attribute are returned.  A saturating useful counter drives the replacement
policy.

Reference: XiangShan/src/main/scala/xiangshan/frontend/bpu/ubtb/MicroBtb.scala

Key features:
  F-UB-001  Full-associative tag match (one-hot hit)
  F-UB-002  Single-cycle lookup (s0 → s1 result)
  F-UB-003  Per-entry saturating useful counter (2-bit, signed-style)
  F-UB-004  PLRU-style replacement on miss (simplified: pick first not-useful)
  F-UB-005  Two-stage training pipeline (t0 read / t1 write-back)
  F-UB-006  Always-taken prediction strategy
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

from top.parameters import (
    BRANCH_TYPE_WIDTH,
    CFI_POSITION_WIDTH,
    PC_WIDTH,
    RAS_ACTION_WIDTH,
    UBTB_NUM_ENTRIES,
    UBTB_TAG_WIDTH,
    UBTB_TARGET_WIDTH,
    UBTB_USEFUL_CNT_WIDTH,
)

ATTR_WIDTH = BRANCH_TYPE_WIDTH + RAS_ACTION_WIDTH


def _r(domain, state_reg):
    """Read a state register as a CAS signal at the current cycle."""
    return cas(domain, state_reg.wire, cycle=0)


def build_ubtb(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    entries: int = UBTB_NUM_ENTRIES,
    tag_width: int = UBTB_TAG_WIDTH,
    target_width: int = UBTB_TARGET_WIDTH,
    useful_cnt_width: int = UBTB_USEFUL_CNT_WIDTH,
    pc_width: int = PC_WIDTH,
    cfi_pos_width: int = CFI_POSITION_WIDTH,
    attr_width: int = ATTR_WIDTH,
) -> None:
    """uBTB: full-associative micro branch target buffer with single-cycle lookup."""
    idx_w = max(1, math.ceil(math.log2(entries))) if entries > 1 else 1
    useful_max = (1 << useful_cnt_width) - 1
    useful_mid = 1 << (useful_cnt_width - 1)

    # ── Cycle 0 (s0): Inputs ─────────────────────────────────────────
    s0_fire = cas(domain, m.input("s0_fire", width=1), cycle=0)
    s0_pc = cas(domain, m.input("s0_pc", width=pc_width), cycle=0)
    enable = cas(domain, m.input("enable", width=1), cycle=0)

    train_valid = cas(domain, m.input("train_valid", width=1), cycle=0)
    train_pc = cas(domain, m.input("train_pc", width=pc_width), cycle=0)
    train_target = cas(domain, m.input("train_target", width=pc_width), cycle=0)
    train_taken = cas(domain, m.input("train_taken", width=1), cycle=0)
    train_cfi_pos = cas(domain, m.input("train_cfi_pos", width=cfi_pos_width), cycle=0)
    train_attr = cas(domain, m.input("train_attr", width=attr_width), cycle=0)

    zero1 = cas(domain, m.const(0, width=1), cycle=0)
    one1 = cas(domain, m.const(1, width=1), cycle=0)
    zero_idx = cas(domain, m.const(0, width=idx_w), cycle=0)
    zero_target_w = cas(domain, m.const(0, width=target_width), cycle=0)
    zero_pos = cas(domain, m.const(0, width=cfi_pos_width), cycle=0)
    zero_attr = cas(domain, m.const(0, width=attr_width), cycle=0)
    zero_useful = cas(domain, m.const(0, width=useful_cnt_width), cycle=0)
    useful_init_val = cas(domain, m.const(useful_mid, width=useful_cnt_width), cycle=0)

    # Tag extraction: pc[tag_width+1 : 1]
    s0_tag = s0_pc[1 : 1 + tag_width]

    # ── Entry storage ─────────────────────────────────────────────────
    ent_valid_r = [domain.state(width=1, reset_value=0, name=f"ev_{i}") for i in range(entries)]
    ent_tag_r = [domain.state(width=tag_width, reset_value=0, name=f"et_{i}") for i in range(entries)]
    ent_target_r = [domain.state(width=target_width, reset_value=0, name=f"etar_{i}") for i in range(entries)]
    ent_cfi_pos_r = [domain.state(width=cfi_pos_width, reset_value=0, name=f"epos_{i}") for i in range(entries)]
    ent_attr_r = [domain.state(width=attr_width, reset_value=0, name=f"eattr_{i}") for i in range(entries)]
    ent_useful_r = [domain.state(width=useful_cnt_width, reset_value=0, name=f"eu_{i}") for i in range(entries)]

    # Read all entries as combinational signals
    ev = [_r(domain, ent_valid_r[i]) for i in range(entries)]
    et = [_r(domain, ent_tag_r[i]) for i in range(entries)]
    etar = [_r(domain, ent_target_r[i]) for i in range(entries)]
    epos = [_r(domain, ent_cfi_pos_r[i]) for i in range(entries)]
    eattr = [_r(domain, ent_attr_r[i]) for i in range(entries)]
    eu = [_r(domain, ent_useful_r[i]) for i in range(entries)]

    # ── s0: Full-associative tag comparison ───────────────────────────
    hit_vec = []
    for i in range(entries):
        tag_match = et[i] == s0_tag
        hit_vec.append(ev[i] & tag_match)

    # One-hot → hit, hit_idx (priority encoder)
    s0_hit = zero1
    for h in hit_vec:
        s0_hit = s0_hit | h

    s0_hit_idx = zero_idx
    for i in reversed(range(entries)):
        s0_hit_idx = mux(hit_vec[i], cas(domain, m.const(i, width=idx_w), cycle=0), s0_hit_idx)

    # Read hit entry via mux chain
    s0_hit_target = zero_target_w
    s0_hit_cfi = zero_pos
    s0_hit_attr = zero_attr
    for i in range(entries):
        s0_hit_target = mux(hit_vec[i], etar[i], s0_hit_target)
        s0_hit_cfi = mux(hit_vec[i], epos[i], s0_hit_cfi)
        s0_hit_attr = mux(hit_vec[i], eattr[i], s0_hit_attr)

    # Reconstruct full target: { pc_upper, target_lower }
    pc_upper = s0_pc[target_width : pc_width]
    s0_full_target = cas(
        domain,
        (pc_upper.wire << target_width) | (s0_hit_target.wire + u(pc_width, 0)),
        cycle=0,
    )[0:pc_width]

    # ── Prediction outputs ────────────────────────────────────────────
    pred_valid = s0_hit & s0_fire & enable
    m.output("pred_valid", pred_valid.wire)
    m.output("pred_taken", pred_valid.wire)
    m.output("pred_target", s0_full_target.wire)
    m.output("pred_cfi_pos", s0_hit_cfi.wire)
    m.output("pred_attr", s0_hit_attr.wire)

    # ── Training: tag / target extraction ─────────────────────────────
    t0_tag = train_pc[1 : 1 + tag_width]
    t0_target_lower = train_target[0 : target_width]

    t0_hit_vec = []
    for i in range(entries):
        t_match = et[i] == t0_tag
        t0_hit_vec.append(ev[i] & t_match)

    t0_hit = zero1
    for h in t0_hit_vec:
        t0_hit = t0_hit | h

    t0_hit_idx = zero_idx
    for i in reversed(range(entries)):
        t0_hit_idx = mux(t0_hit_vec[i], cas(domain, m.const(i, width=idx_w), cycle=0), t0_hit_idx)

    # Victim: first entry with useful == 0, or first invalid
    victim_idx = cas(domain, m.const(entries - 1, width=idx_w), cycle=0)
    for i in reversed(range(entries)):
        not_useful = eu[i] == zero_useful
        not_valid = ~ev[i]
        pick = not_useful | not_valid
        victim_idx = mux(pick, cas(domain, m.const(i, width=idx_w), cycle=0), victim_idx)

    t0_fire = train_valid & enable
    t0_allocate = t0_fire & (~t0_hit) & train_taken
    t0_do_write = t0_fire & (t0_hit | t0_allocate)
    t0_write_idx = mux(t0_hit, t0_hit_idx, victim_idx)

    # ── domain.next() → Cycle 1: entry writes ────────────────────────
    domain.next()

    # Read old useful + target for the selected entry
    t0_old_useful = zero_useful
    t0_old_target = zero_target_w
    for i in range(entries):
        idx_match = t0_write_idx == cas(domain, m.const(i, width=idx_w), cycle=0)
        t0_old_useful = mux(idx_match, eu[i], t0_old_useful)
        t0_old_target = mux(idx_match, etar[i], t0_old_target)

    useful_one = cas(domain, m.const(1, width=useful_cnt_width), cycle=0)
    useful_max_c = cas(domain, m.const(useful_max, width=useful_cnt_width), cycle=0)

    is_max = t0_old_useful == useful_max_c
    is_zero = t0_old_useful == zero_useful

    useful_inc = mux(is_max, useful_max_c,
                     cas(domain, (t0_old_useful.wire + useful_one.wire)[0:useful_cnt_width], cycle=0))
    useful_dec = mux(is_zero, zero_useful,
                     cas(domain, (t0_old_useful.wire - useful_one.wire)[0:useful_cnt_width], cycle=0))

    target_same = t0_old_target == t0_target_lower

    new_useful = mux(t0_hit,
                     mux(train_taken & target_same, useful_inc, useful_dec),
                     useful_init_val)

    for i in range(entries):
        we = t0_do_write & (t0_write_idx == cas(domain, m.const(i, width=idx_w), cycle=0))
        ent_valid_r[i].set(mux(we, one1, ev[i]), when=we)
        ent_tag_r[i].set(mux(we, t0_tag, et[i]), when=we)
        ent_target_r[i].set(mux(we, t0_target_lower, etar[i]), when=we)
        ent_cfi_pos_r[i].set(mux(we, train_cfi_pos, epos[i]), when=we)
        ent_attr_r[i].set(mux(we, train_attr, eattr[i]), when=we)
        ent_useful_r[i].set(mux(we, new_useful, eu[i]), when=we)


build_ubtb.__pycircuit_name__ = "ubtb"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_ubtb, name="ubtb", eager=True,
        entries=UBTB_NUM_ENTRIES,
    ).emit_mlir())
