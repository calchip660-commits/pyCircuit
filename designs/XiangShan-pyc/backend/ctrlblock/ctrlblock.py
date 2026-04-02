"""CtrlBlock — Backend Control Block for XiangShan-pyc.

Top-level control integration wiring the Decode → Rename → Dispatch → ROB
commit path.  Generates redirect signals from ROB exceptions or branch
mispredictions, and propagates backpressure (stall) upstream.

Reference: XiangShan/src/main/scala/xiangshan/backend/CtrlBlock.scala

Pipeline (pass-through integration):
  Cycle 0 — Receive decoded uops from frontend, propagate through rename,
            dispatch, ROB enqueue.  Stall and redirect are combinational.
  Cycle 1 — Latch pipeline registers and commit-related state updates.

Key features:
  B-CB-001  Decoded uop pass-through from frontend to dispatch
  B-CB-002  Redirect generation: ROB exception or branch misprediction
  B-CB-003  Stall propagation: backpressure from dispatch → rename → frontend
  B-CB-004  Commit output: ROB retire signals for freelist / arch state update
  B-CB-005  Flush: cancel all in-flight work on exception / redirect
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
    COMMIT_WIDTH,
    DECODE_WIDTH,
    PC_WIDTH,
    PTAG_WIDTH_INT,
    RENAME_WIDTH,
    ROB_IDX_WIDTH,
)


def build_ctrlblock(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    decode_width: int = DECODE_WIDTH,
    commit_width: int = COMMIT_WIDTH,
    ptag_w: int = PTAG_WIDTH_INT,
    pc_width: int = PC_WIDTH,
    rob_idx_w: int = ROB_IDX_WIDTH,
) -> None:
    """CtrlBlock: Decode→Rename→Dispatch→ROB integration with redirect/stall."""

    # ================================================================
    # Cycle 0 — Inputs
    # ================================================================

    # Decoded uops from frontend
    in_valid = [cas(domain, m.input(f"in_valid_{i}", width=1), cycle=0)
                for i in range(decode_width)]
    in_pc = [cas(domain, m.input(f"in_pc_{i}", width=pc_width), cycle=0)
             for i in range(decode_width)]
    in_pdest = [cas(domain, m.input(f"in_pdest_{i}", width=ptag_w), cycle=0)
                for i in range(decode_width)]
    in_psrc1 = [cas(domain, m.input(f"in_psrc1_{i}", width=ptag_w), cycle=0)
                for i in range(decode_width)]
    in_psrc2 = [cas(domain, m.input(f"in_psrc2_{i}", width=ptag_w), cycle=0)
                for i in range(decode_width)]
    in_old_pdest = [cas(domain, m.input(f"in_old_pdest_{i}", width=ptag_w), cycle=0)
                    for i in range(decode_width)]
    in_rob_idx = [cas(domain, m.input(f"in_rob_idx_{i}", width=rob_idx_w), cycle=0)
                  for i in range(decode_width)]

    # Backpressure from downstream (IQ full, ROB full)
    dispatch_stall = cas(domain, m.input("dispatch_stall", width=1), cycle=0)
    rob_full = cas(domain, m.input("rob_full", width=1), cycle=0)

    # Branch misprediction from execution
    bru_redirect_valid = cas(domain, m.input("bru_redirect_valid", width=1), cycle=0)
    bru_redirect_target = cas(domain, m.input("bru_redirect_target", width=pc_width), cycle=0)
    bru_redirect_rob_idx = cas(domain, m.input("bru_redirect_rob_idx", width=rob_idx_w), cycle=0)

    # ROB exception
    rob_exception_valid = cas(domain, m.input("rob_exception_valid", width=1), cycle=0)
    rob_exception_pc = cas(domain, m.input("rob_exception_pc", width=pc_width), cycle=0)

    # ROB commit signals
    rob_commit_valid = [cas(domain, m.input(f"rob_commit_valid_{i}", width=1), cycle=0)
                        for i in range(commit_width)]
    rob_commit_pdest = [cas(domain, m.input(f"rob_commit_pdest_{i}", width=ptag_w), cycle=0)
                        for i in range(commit_width)]
    rob_commit_old_pdest = [cas(domain, m.input(f"rob_commit_old_pdest_{i}", width=ptag_w), cycle=0)
                            for i in range(commit_width)]

    # Writeback from execution units
    wb_valid = [cas(domain, m.input(f"wb_valid_{i}", width=1), cycle=0)
                for i in range(2)]
    wb_rob_idx = [cas(domain, m.input(f"wb_rob_idx_{i}", width=rob_idx_w), cycle=0)
                  for i in range(2)]

    # ── Constants ────────────────────────────────────────────────
    ZERO_1 = cas(domain, m.const(0, width=1), cycle=0)
    ONE_1 = cas(domain, m.const(1, width=1), cycle=0)
    ZERO_PC = cas(domain, m.const(0, width=pc_width), cycle=0)

    # ================================================================
    # Redirect generation
    # ================================================================
    # Priority: ROB exception > branch misprediction
    redirect_valid = bru_redirect_valid | rob_exception_valid
    redirect_target = mux(rob_exception_valid, rob_exception_pc, bru_redirect_target)
    redirect_flush = rob_exception_valid

    m.output("redirect_valid", redirect_valid.wire)
    m.output("redirect_target", redirect_target.wire)
    m.output("redirect_flush", redirect_flush.wire)

    # ================================================================
    # Stall propagation
    # ================================================================
    # Stall if dispatch stalls, ROB is full, or redirect is active
    pipeline_stall = dispatch_stall | rob_full | redirect_valid

    m.output("stall_to_frontend", pipeline_stall.wire)

    # ================================================================
    # Dispatch pass-through (with stall/flush gating)
    # ================================================================
    for i in range(decode_width):
        slot_valid = in_valid[i] & (~pipeline_stall)

        m.output(f"dp_valid_{i}", slot_valid.wire)
        m.output(f"dp_pc_{i}", in_pc[i].wire)
        m.output(f"dp_pdest_{i}", in_pdest[i].wire)
        m.output(f"dp_psrc1_{i}", in_psrc1[i].wire)
        m.output(f"dp_psrc2_{i}", in_psrc2[i].wire)
        m.output(f"dp_old_pdest_{i}", in_old_pdest[i].wire)
        m.output(f"dp_rob_idx_{i}", in_rob_idx[i].wire)

    # ================================================================
    # Commit pass-through
    # ================================================================
    for i in range(commit_width):
        m.output(f"commit_valid_{i}", rob_commit_valid[i].wire)
        m.output(f"commit_pdest_{i}", rob_commit_pdest[i].wire)
        m.output(f"commit_old_pdest_{i}", rob_commit_old_pdest[i].wire)

    # Count committed uops
    cm_cnt_w = max(1, commit_width.bit_length())
    cm_cnt = cas(domain, m.const(0, width=cm_cnt_w), cycle=0)
    ONE_CM = cas(domain, m.const(1, width=cm_cnt_w), cycle=0)
    for i in range(commit_width):
        cm_cnt = mux(rob_commit_valid[i],
                     cas(domain, (cm_cnt.wire + ONE_CM.wire)[0:cm_cnt_w], cycle=0),
                     cm_cnt)
    m.output("commit_count", cm_cnt.wire)

    # ================================================================
    # Writeback forwarding
    # ================================================================
    for i in range(2):
        m.output(f"wb_fwd_valid_{i}", wb_valid[i].wire)
        m.output(f"wb_fwd_rob_idx_{i}", wb_rob_idx[i].wire)

    # ================================================================
    # Cycle 1: pipeline registers for timing closure
    # ================================================================
    domain.next()

    for i in range(decode_width):
        slot_valid = in_valid[i] & (~pipeline_stall)
        domain.cycle(slot_valid.wire, name=f"cb_v_{i}")
        domain.cycle(in_pc[i].wire, name=f"cb_pc_{i}")
        domain.cycle(in_pdest[i].wire, name=f"cb_pdest_{i}")
        domain.cycle(in_psrc1[i].wire, name=f"cb_psrc1_{i}")
        domain.cycle(in_psrc2[i].wire, name=f"cb_psrc2_{i}")

    # Redirect pipeline register
    domain.cycle(redirect_valid.wire, name="cb_redir_v")
    domain.cycle(redirect_target.wire, name="cb_redir_tgt")


build_ctrlblock.__pycircuit_name__ = "ctrlblock"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_ctrlblock, name="ctrlblock", eager=True,
        decode_width=2, commit_width=2,
        ptag_w=4, pc_width=16, rob_idx_w=4,
    ).emit_mlir())
