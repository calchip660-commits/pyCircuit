"""BPU — Branch Prediction Unit top-level for XiangShan-pyc.

Multi-stage overriding predictor pipeline (s0 → s1 → s2 → s3):
  s0: generate PC, launch lookup in all sub-predictors
  s1: NLP (uBTB) result ready — first prediction sent to FTQ
  s2: APD partial results (FTB, TAGE, RAS) ready — pipeline stage
  s3: APD full results (SC, ITTAGE) ready — override s1 if different

Reference: XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala

Key features:
  F-BP-001  4-stage pipeline with overriding predictor logic
  F-BP-002  s0 PC generation: redirect > s3_override > s1_target > fallthrough
  F-BP-003  s1 fast prediction (NLP / uBTB)
  F-BP-004  s3 precise prediction (FTB + TAGE-SC + ITTAGE + RAS) with override
  F-BP-005  Pipeline handshake: fire / valid / flush / ready per stage
  F-BP-006  Prediction output to FTQ with s3 override flag
"""
from __future__ import annotations

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
    CFI_POSITION_WIDTH,
    FETCH_BLOCK_SIZE,
    INST_BYTES,
    PC_WIDTH,
    PREDICT_WIDTH,
    BRANCH_TYPE_WIDTH,
    RAS_ACTION_WIDTH,
)

PRED_BLOCK_BYTES = FETCH_BLOCK_SIZE
ATTR_WIDTH = BRANCH_TYPE_WIDTH + RAS_ACTION_WIDTH


def _r(domain, state_reg):
    """Read a state register as a CAS signal at cycle 0."""
    return cas(domain, state_reg.wire, cycle=0)


def build_bpu(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    pc_width: int = PC_WIDTH,
    cfi_pos_width: int = CFI_POSITION_WIDTH,
    attr_width: int = ATTR_WIDTH,
    pred_block_bytes: int = PRED_BLOCK_BYTES,
) -> None:
    """BPU: 4-stage overriding branch prediction pipeline."""
    target_w = pc_width
    c = domain.cycle_index

    # ── Cycle 0 (s0): PC generation & sub-predictor launch ────────────
    redirect_valid = cas(domain, m.input("redirect_valid", width=1), cycle=0)
    redirect_target = cas(domain, m.input("redirect_target", width=pc_width), cycle=0)

    update_valid = cas(domain, m.input("update_valid", width=1), cycle=0)
    update_pc = cas(domain, m.input("update_pc", width=pc_width), cycle=0)
    update_target = cas(domain, m.input("update_target", width=target_w), cycle=0)
    update_taken = cas(domain, m.input("update_taken", width=1), cycle=0)
    update_branch_type = cas(domain, m.input("update_branch_type", width=BRANCH_TYPE_WIDTH), cycle=0)
    update_ras_action = cas(domain, m.input("update_ras_action", width=RAS_ACTION_WIDTH), cycle=0)

    ftq_ready = cas(domain, m.input("ftq_ready", width=1), cycle=0)

    nlp_hit = cas(domain, m.input("nlp_hit", width=1), cycle=0)
    nlp_target = cas(domain, m.input("nlp_target", width=target_w), cycle=0)
    nlp_taken = cas(domain, m.input("nlp_taken", width=1), cycle=0)
    nlp_cfi_pos = cas(domain, m.input("nlp_cfi_pos", width=cfi_pos_width), cycle=0)
    nlp_attr = cas(domain, m.input("nlp_attr", width=attr_width), cycle=0)

    apd_hit = cas(domain, m.input("apd_hit", width=1), cycle=0)
    apd_target = cas(domain, m.input("apd_target", width=target_w), cycle=0)
    apd_taken = cas(domain, m.input("apd_taken", width=1), cycle=0)
    apd_cfi_pos = cas(domain, m.input("apd_cfi_pos", width=cfi_pos_width), cycle=0)
    apd_attr = cas(domain, m.input("apd_attr", width=attr_width), cycle=0)

    zero1 = cas(domain, m.const(0, width=1), cycle=0)
    zero_pc = cas(domain, m.const(0, width=pc_width), cycle=0)
    zero_pos = cas(domain, m.const(0, width=cfi_pos_width), cycle=0)
    zero_attr = cas(domain, m.const(0, width=attr_width), cycle=0)
    one1 = cas(domain, m.const(1, width=1), cycle=0)
    fallthrough_offset = cas(domain, m.const(pred_block_bytes, width=pc_width), cycle=0)

    # ── Pipeline state registers ──────────────────────────────────────
    s1_valid_r = domain.state(width=1, reset_value=0, name="s1_valid")
    s2_valid_r = domain.state(width=1, reset_value=0, name="s2_valid")
    s3_valid_r = domain.state(width=1, reset_value=0, name="s3_valid")

    s0_pc_r = domain.state(width=pc_width, reset_value=0, name="s0_pc")

    s1_pc_r = domain.state(width=pc_width, reset_value=0, name="s1_pc")
    s1_target_r = domain.state(width=target_w, reset_value=0, name="s1_target")
    s1_taken_r = domain.state(width=1, reset_value=0, name="s1_taken")
    s1_hit_r = domain.state(width=1, reset_value=0, name="s1_hit")
    s1_cfi_pos_r = domain.state(width=cfi_pos_width, reset_value=0, name="s1_cfi_pos")
    s1_attr_r = domain.state(width=attr_width, reset_value=0, name="s1_attr")

    s2_pc_r = domain.state(width=pc_width, reset_value=0, name="s2_pc")
    s2_target_r = domain.state(width=target_w, reset_value=0, name="s2_target")
    s2_taken_r = domain.state(width=1, reset_value=0, name="s2_taken")
    s2_cfi_pos_r = domain.state(width=cfi_pos_width, reset_value=0, name="s2_cfi_pos")
    s2_attr_r = domain.state(width=attr_width, reset_value=0, name="s2_attr")

    s3_pc_r = domain.state(width=pc_width, reset_value=0, name="s3_pc")
    s3_target_r = domain.state(width=target_w, reset_value=0, name="s3_target")
    s3_taken_r = domain.state(width=1, reset_value=0, name="s3_taken")
    s3_cfi_pos_r = domain.state(width=cfi_pos_width, reset_value=0, name="s3_cfi_pos")
    s3_attr_r = domain.state(width=attr_width, reset_value=0, name="s3_attr")
    s3_hit_r = domain.state(width=1, reset_value=0, name="s3_hit")

    s3_s1_target_r = domain.state(width=target_w, reset_value=0, name="s3_s1_target")
    s3_s1_taken_r = domain.state(width=1, reset_value=0, name="s3_s1_taken")

    s2_s1_target_r = domain.state(width=target_w, reset_value=0, name="s2_s1_target")
    s2_s1_taken_r = domain.state(width=1, reset_value=0, name="s2_s1_taken")

    # ── Read state as combinational signals ───────────────────────────
    s1_valid = _r(domain, s1_valid_r)
    s2_valid = _r(domain, s2_valid_r)
    s3_valid = _r(domain, s3_valid_r)

    s1_pc = _r(domain, s1_pc_r)
    s1_target = _r(domain, s1_target_r)
    s1_taken = _r(domain, s1_taken_r)
    s1_hit = _r(domain, s1_hit_r)
    s1_cfi_pos = _r(domain, s1_cfi_pos_r)
    s1_attr = _r(domain, s1_attr_r)

    s3_pc = _r(domain, s3_pc_r)
    s3_target = _r(domain, s3_target_r)
    s3_taken = _r(domain, s3_taken_r)
    s3_hit = _r(domain, s3_hit_r)
    s3_s1_target = _r(domain, s3_s1_target_r)
    s3_s1_taken = _r(domain, s3_s1_taken_r)

    # ── Pipeline control ──────────────────────────────────────────────
    # s3 override: APD disagrees with NLP
    target_differs = cas(domain, (s3_target.wire ^ s3_s1_target.wire)[0:1], cycle=0)
    target_nonzero = cas(domain, s3_target.wire | s3_s1_target.wire, cycle=0)[0:1]
    taken_differs = cas(domain, (s3_taken.wire ^ s3_s1_taken.wire)[0:1], cycle=0)
    any_diff = target_differs | taken_differs
    s3_override = s3_valid & s3_hit & any_diff

    s3_flush = redirect_valid
    s2_flush = s3_flush | s3_override
    s1_flush = s2_flush

    s3_fire = s3_valid & (~s3_flush)
    s2_fire = s2_valid & (~s2_flush)
    s1_fire = s1_valid & ftq_ready & (~s1_flush)
    s0_fire = (~s1_valid) | s1_fire | s1_flush

    # ── s1 prediction ─────────────────────────────────────────────────
    s1_ft_target = cas(domain, (s1_pc.wire + fallthrough_offset.wire)[0:pc_width], cycle=0)
    s1_pred_taken = s1_hit & s1_taken
    s1_pred_target = mux(s1_pred_taken, s1_target, s1_ft_target)
    s1_pred_cfi = mux(s1_hit, s1_cfi_pos, zero_pos)
    s1_pred_attr = mux(s1_hit, s1_attr, zero_attr)

    # ── s3 prediction ─────────────────────────────────────────────────
    s3_ft_target = cas(domain, (s3_pc.wire + fallthrough_offset.wire)[0:pc_width], cycle=0)
    s3_pred_taken = s3_hit & s3_taken
    s3_pred_target = mux(s3_pred_taken, s3_target, s3_ft_target)

    # ── s0 PC selection ───────────────────────────────────────────────
    s0_pc = _r(domain, s0_pc_r)
    s0_pc_next = s0_pc
    s0_pc_next = mux(s1_valid, s1_pred_target, s0_pc_next)
    s0_pc_next = mux(s3_override, s3_pred_target, s0_pc_next)
    s0_pc_next = mux(redirect_valid, redirect_target, s0_pc_next)

    # ── Outputs ───────────────────────────────────────────────────────
    pred_out_valid = (s1_valid & ftq_ready) | s3_override
    m.output("pred_valid", pred_out_valid.wire)

    out_pc = mux(s3_override, s3_pc, s1_pc)
    out_target = mux(s3_override, s3_pred_target, s1_pred_target)
    out_taken = mux(s3_override, s3_pred_taken, s1_pred_taken)
    out_cfi_pos = mux(s3_override, _r(domain, s3_cfi_pos_r), s1_pred_cfi)
    out_attr = mux(s3_override, _r(domain, s3_attr_r), s1_pred_attr)

    m.output("pred_pc", out_pc.wire)
    m.output("pred_target", out_target.wire)
    m.output("pred_taken", out_taken.wire)
    m.output("pred_cfi_pos", out_cfi_pos.wire)
    m.output("pred_attr", out_attr.wire)
    m.output("pred_s3_override", s3_override.wire)

    m.output("s0_pc", s0_pc_next.wire)
    m.output("s0_fire", s0_fire.wire)
    m.output("s1_fire", s1_fire.wire)
    m.output("s2_fire", s2_fire.wire)
    m.output("s3_fire", s3_fire.wire)

    m.output("update_valid_out", update_valid.wire)
    m.output("update_pc_out", update_pc.wire)
    m.output("update_target_out", update_target.wire)
    m.output("update_taken_out", update_taken.wire)
    m.output("update_branch_type_out", update_branch_type.wire)
    m.output("update_ras_action_out", update_ras_action.wire)

    # ── domain.next() → Cycle 1: register updates ────────────────────
    domain.next()

    s0_pc_r.set(mux(s0_fire, s0_pc_next, s0_pc))

    s1_v_next = mux(s0_fire, one1, s1_valid)
    s1_v_next = mux(s1_fire & (~s0_fire), zero1, s1_v_next)
    s1_v_next = mux(s1_flush, zero1, s1_v_next)
    s1_valid_r.set(s1_v_next)

    s1_pc_r.set(mux(s0_fire, s0_pc_next, s1_pc))
    s1_target_r.set(mux(s0_fire, nlp_target, s1_target))
    s1_taken_r.set(mux(s0_fire, nlp_taken, s1_taken))
    s1_hit_r.set(mux(s0_fire, nlp_hit, s1_hit))
    s1_cfi_pos_r.set(mux(s0_fire, nlp_cfi_pos, s1_cfi_pos))
    s1_attr_r.set(mux(s0_fire, nlp_attr, s1_attr))

    s2_v_next = mux(s1_fire, one1, s2_valid)
    s2_v_next = mux(s2_fire & (~s1_fire), zero1, s2_v_next)
    s2_v_next = mux(s2_flush, zero1, s2_v_next)
    s2_valid_r.set(s2_v_next)

    s2_pc_r.set(mux(s1_fire, s1_pc, _r(domain, s2_pc_r)))
    s2_target_r.set(mux(s1_fire, s1_pred_target, _r(domain, s2_target_r)))
    s2_taken_r.set(mux(s1_fire, s1_pred_taken, _r(domain, s2_taken_r)))
    s2_cfi_pos_r.set(mux(s1_fire, s1_pred_cfi, _r(domain, s2_cfi_pos_r)))
    s2_attr_r.set(mux(s1_fire, s1_pred_attr, _r(domain, s2_attr_r)))

    s3_v_next = mux(s2_fire, one1, s3_valid)
    s3_v_next = mux(s3_fire & (~s2_fire), zero1, s3_v_next)
    s3_v_next = mux(s3_flush, zero1, s3_v_next)
    s3_valid_r.set(s3_v_next)

    s2_pc = _r(domain, s2_pc_r)
    s3_pc_r.set(mux(s2_fire, s2_pc, s3_pc))
    s3_target_r.set(mux(s2_fire, apd_target, s3_target))
    s3_taken_r.set(mux(s2_fire, apd_taken, s3_taken))
    s3_cfi_pos_r.set(mux(s2_fire, apd_cfi_pos, _r(domain, s3_cfi_pos_r)))
    s3_attr_r.set(mux(s2_fire, apd_attr, _r(domain, s3_attr_r)))
    s3_hit_r.set(mux(s2_fire, apd_hit, s3_hit))

    s2_s1_target_r.set(mux(s1_fire, s1_pred_target, _r(domain, s2_s1_target_r)))
    s2_s1_taken_r.set(mux(s1_fire, s1_pred_taken, _r(domain, s2_s1_taken_r)))

    s2_s1_target = _r(domain, s2_s1_target_r)
    s2_s1_taken = _r(domain, s2_s1_taken_r)
    s3_s1_target_r.set(mux(s2_fire, s2_s1_target, s3_s1_target))
    s3_s1_taken_r.set(mux(s2_fire, s2_s1_taken, s3_s1_taken))


build_bpu.__pycircuit_name__ = "bpu"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_bpu, name="bpu", eager=True,
    ).emit_mlir())
