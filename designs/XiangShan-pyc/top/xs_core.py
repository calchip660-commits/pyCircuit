"""XSCore — Core Integration for XiangShan-pyc.

Top-level integration of Frontend, Backend, and MemBlock subsystems within
a single processor core.  Wires the key inter-module interfaces and exposes
external ports for L2 cache, interrupts, and debug.

Reference: XiangShan/src/main/scala/xiangshan/XSCore.scala

Internal connections:
  Frontend → Backend: decoded uops (decode_width channels)
  Backend  → Frontend: redirect (valid, target)
  Backend  → MemBlock: memory dispatch (load/store uops)
  MemBlock → Backend: load writeback, store completion
  Frontend → L2: ICache miss refill interface

External ports:
  - L2 cache interface (TileLink-like A/D channels)
  - Interrupt inputs (meip, seip, mtip, msip, debug)
  - Debug port

Key features:
  C-XC-001  Frontend ↔ Backend redirect / stall loop
  C-XC-002  Backend → MemBlock memory dispatch path
  C-XC-003  MemBlock → Backend load/store writeback
  C-XC-004  ICache miss → L2 refill request
  C-XC-005  External interrupt routing to backend
"""
from __future__ import annotations

import sys
from pathlib import Path

_XS_ROOT = Path(__file__).resolve().parent.parent
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
    CACHE_LINE_SIZE,
    COMMIT_WIDTH,
    DECODE_WIDTH,
    LOAD_PIPELINE_WIDTH,
    NUM_LDU,
    NUM_STA,
    PC_WIDTH,
    PTAG_WIDTH_INT,
    ROB_IDX_WIDTH,
    STORE_PIPELINE_WIDTH,
    XLEN,
)

FU_TYPE_WIDTH = 3
NUM_WB_PORTS = 4
BLOCK_BITS = CACHE_LINE_SIZE  # 512 bits


def build_xs_core(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    decode_width: int = DECODE_WIDTH,
    commit_width: int = COMMIT_WIDTH,
    num_wb: int = NUM_WB_PORTS,
    num_load: int = NUM_LDU,
    num_store: int = NUM_STA,
    data_width: int = XLEN,
    pc_width: int = PC_WIDTH,
    ptag_w: int = PTAG_WIDTH_INT,
    rob_idx_w: int = ROB_IDX_WIDTH,
    fu_type_w: int = FU_TYPE_WIDTH,
    block_bits: int = BLOCK_BITS,
) -> None:
    """XSCore: Frontend + Backend + MemBlock interconnect."""

    ZERO_1 = cas(domain, m.const(0, width=1), cycle=0)
    ONE_1 = cas(domain, m.const(1, width=1), cycle=0)
    ZERO_PC = cas(domain, m.const(0, width=pc_width), cycle=0)

    # ================================================================
    # External inputs
    # ================================================================

    # L2 refill response (ICache miss path)
    l2_refill_valid = cas(domain, m.input("l2_refill_valid", width=1), cycle=0)
    l2_refill_data = cas(domain, m.input("l2_refill_data", width=block_bits), cycle=0)

    # L2 data response (DCache miss path)
    l2_data_resp_valid = cas(domain, m.input("l2_data_resp_valid", width=1), cycle=0)
    l2_data_resp_data = cas(domain, m.input("l2_data_resp_data", width=data_width), cycle=0)

    # Interrupt inputs
    meip = cas(domain, m.input("meip", width=1), cycle=0)
    seip = cas(domain, m.input("seip", width=1), cycle=0)
    mtip = cas(domain, m.input("mtip", width=1), cycle=0)
    msip = cas(domain, m.input("msip", width=1), cycle=0)
    debug_intr = cas(domain, m.input("debug_interrupt", width=1), cycle=0)

    # ================================================================
    # Frontend interface (simplified)
    # Cycle 0: BPU prediction + redirect handling
    # ================================================================

    # Frontend state: fetch PC
    fetch_pc_r = domain.state(width=pc_width, reset_value=0, name="xc_fetch_pc")
    bpu_valid_r = domain.state(width=1, reset_value=0, name="xc_bpu_valid")

    fetch_pc = cas(domain, fetch_pc_r.wire, cycle=0)
    bpu_valid = cas(domain, bpu_valid_r.wire, cycle=0)

    # Backend redirect (computed below, forward-declared via state)
    redirect_valid_r = domain.state(width=1, reset_value=0, name="xc_redir_v")
    redirect_target_r = domain.state(width=pc_width, reset_value=0, name="xc_redir_t")
    redirect_valid = cas(domain, redirect_valid_r.wire, cycle=0)
    redirect_target = cas(domain, redirect_target_r.wire, cycle=0)

    # Backend stall (forward-declared via state)
    be_stall_r = domain.state(width=1, reset_value=0, name="xc_be_stall")
    be_stall = cas(domain, be_stall_r.wire, cycle=0)

    # Frontend ibuf ready = ~stall
    ibuf_ready = ~be_stall

    # BPU simplified: fallthrough prediction
    fallthrough_c = cas(domain, m.const(64, width=pc_width), cycle=0)
    bpu_pred_target = cas(
        domain, (fetch_pc.wire + fallthrough_c.wire)[0:pc_width], cycle=0
    )

    flush = redirect_valid
    s0_fire = bpu_valid & ibuf_ready & (~flush)

    next_pc = fetch_pc
    next_pc = mux(s0_fire, bpu_pred_target, next_pc)
    next_pc = mux(redirect_valid, redirect_target, next_pc)

    # ── Frontend pipeline: cycle 0 → 1 (ICache) ──────────────────
    s1_valid_w = domain.cycle(s0_fire.wire, name="xc_s1_v")
    s1_pc_w = domain.cycle(fetch_pc.wire, name="xc_s1_pc")

    domain.next()

    # Cycle 1: ICache fetch (simplified hit model using L2 refill)
    s1_valid = s1_valid_w & (~redirect_valid.wire)
    s1_resp_valid = s1_valid & l2_refill_valid.wire
    s1_miss = s1_valid & (~l2_refill_valid.wire)

    m.output("l2_icache_miss_valid", s1_miss)
    m.output("l2_icache_miss_addr", s1_pc_w)

    s2_valid_w = domain.cycle(s1_resp_valid, name="xc_s2_v")
    s2_pc_w = domain.cycle(s1_pc_w, name="xc_s2_pc")
    s2_data_w = domain.cycle(l2_refill_data.wire, name="xc_s2_data")

    domain.next()

    # Cycle 2: IFU instruction extraction
    s2_valid = s2_valid_w & (~redirect_valid.wire)

    INST_WIDTH = 32
    ifu_insts = []
    for i in range(decode_width):
        lo = i * INST_WIDTH
        hi = lo + INST_WIDTH
        if hi <= block_bits:
            ifu_insts.append(s2_data_w[lo:hi])
        else:
            ifu_insts.append(m.const(0, width=INST_WIDTH))

    s3_valid_w = domain.cycle(s2_valid, name="xc_s3_v")
    s3_pc_w = domain.cycle(s2_pc_w, name="xc_s3_pc")
    s3_insts_w = [domain.cycle(ifu_insts[i], name=f"xc_s3_inst_{i}")
                  for i in range(decode_width)]

    domain.next()

    # Cycle 3: Decode → Backend dispatch
    s3_valid = s3_valid_w & (~redirect_valid.wire)

    # ================================================================
    # Backend: dispatch classification + redirect
    # ================================================================

    # Writeback from execution units
    wb_valid = [cas(domain, m.input(f"wb_valid_{i}", width=1), cycle=0)
                for i in range(num_wb)]
    wb_data = [cas(domain, m.input(f"wb_data_{i}", width=data_width), cycle=0)
               for i in range(num_wb)]
    wb_rob_idx = [cas(domain, m.input(f"wb_rob_idx_{i}", width=rob_idx_w), cycle=0)
                  for i in range(num_wb)]

    # Branch redirect from execution
    bru_redirect_valid = cas(domain, m.input("bru_redirect_valid", width=1), cycle=0)
    bru_redirect_target = cas(domain, m.input("bru_redirect_target", width=pc_width), cycle=0)

    # ROB exception
    rob_exception_valid = cas(domain, m.input("rob_exception_valid", width=1), cycle=0)
    rob_exception_pc = cas(domain, m.input("rob_exception_pc", width=pc_width), cycle=0)

    # Issue queue backpressure
    iq_int_ready = cas(domain, m.input("iq_int_ready", width=1), cycle=0)
    iq_fp_ready = cas(domain, m.input("iq_fp_ready", width=1), cycle=0)
    iq_mem_ready = cas(domain, m.input("iq_mem_ready", width=1), cycle=0)

    # Redirect: priority ROB exception > BRU
    new_redir_valid = bru_redirect_valid | rob_exception_valid
    new_redir_target = mux(rob_exception_valid, rob_exception_pc, bru_redirect_target)

    # Interrupt aggregation → treat as exception
    any_interrupt = meip | seip | mtip | msip | debug_intr
    m.output("interrupt_pending", any_interrupt.wire)

    # FU type classification
    FU_FPU = 4
    FU_LDU = 6
    FU_STU = 7
    FU_FPU_C = cas(domain, m.const(FU_FPU, width=fu_type_w), cycle=0)
    FU_LDU_C = cas(domain, m.const(FU_LDU, width=fu_type_w), cycle=0)
    FU_STU_C = cas(domain, m.const(FU_STU, width=fu_type_w), cycle=0)

    # Simplified fu_type: default ALU for decoded instructions
    dec_fu_type = [cas(domain, m.const(0, width=fu_type_w), cycle=0)
                   for _ in range(decode_width)]

    # Dispatch stall check — use .wire on cycle-0 signals in cycle-3 context
    any_blocked = ZERO_1.wire
    for i in range(decode_width):
        is_fp = dec_fu_type[i].wire == FU_FPU_C.wire
        is_mem = (dec_fu_type[i].wire == FU_LDU_C.wire) | (dec_fu_type[i].wire == FU_STU_C.wire)
        is_int = (~is_fp) & (~is_mem)
        slot_ready = is_int.select(iq_int_ready.wire, ZERO_1.wire)
        slot_ready = is_fp.select(iq_fp_ready.wire, slot_ready)
        slot_ready = is_mem.select(iq_mem_ready.wire, slot_ready)
        blocked = s3_valid & (~slot_ready)
        any_blocked = any_blocked | blocked

    pipeline_stall = any_blocked | new_redir_valid.wire

    # ================================================================
    # Decoded uop outputs (Frontend → Backend path)
    # ================================================================

    INST_BYTES = 2
    for i in range(decode_width):
        slot_valid = s3_valid & (~pipeline_stall)
        inst_pc = (s3_pc_w + m.const(i * INST_BYTES, width=pc_width))[0:pc_width]
        m.output(f"dec_valid_{i}", slot_valid)
        m.output(f"dec_inst_{i}", s3_insts_w[i])
        m.output(f"dec_pc_{i}", inst_pc)

    # ================================================================
    # Memory dispatch (Backend → MemBlock path)
    # ================================================================

    for i in range(decode_width):
        is_mem = (dec_fu_type[i].wire == FU_LDU_C.wire) | (dec_fu_type[i].wire == FU_STU_C.wire)
        slot_valid = s3_valid & (~pipeline_stall) & is_mem
        m.output(f"mem_dp_valid_{i}", slot_valid)
        m.output(f"mem_dp_fu_type_{i}", dec_fu_type[i].wire)

    # ================================================================
    # MemBlock → Backend: load/store writeback
    # ================================================================

    # Load writeback from MemBlock
    for i in range(num_load):
        ld_wb_v = cas(domain, m.input(f"ld{i}_wb_valid", width=1), cycle=0)
        ld_wb_d = cas(domain, m.input(f"ld{i}_wb_data", width=data_width), cycle=0)
        ld_wb_r = cas(domain, m.input(f"ld{i}_wb_rob_idx", width=rob_idx_w), cycle=0)
        m.output(f"ld{i}_wb_valid_out", ld_wb_v.wire)
        m.output(f"ld{i}_wb_data_out", ld_wb_d.wire)
        m.output(f"ld{i}_wb_rob_idx_out", ld_wb_r.wire)

    # Store completion from MemBlock
    for i in range(num_store):
        st_wb_v = cas(domain, m.input(f"st{i}_wb_valid", width=1), cycle=0)
        st_wb_r = cas(domain, m.input(f"st{i}_wb_rob_idx", width=rob_idx_w), cycle=0)
        m.output(f"st{i}_wb_valid_out", st_wb_v.wire)
        m.output(f"st{i}_wb_rob_idx_out", st_wb_r.wire)

    # ================================================================
    # L2 cache interface: DCache miss path
    # ================================================================

    dcache_miss_valid = cas(domain, m.input("dcache_miss_valid", width=1), cycle=0)
    dcache_miss_addr = cas(domain, m.input("dcache_miss_addr", width=pc_width), cycle=0)

    m.output("l2_dcache_miss_valid", dcache_miss_valid.wire)
    m.output("l2_dcache_miss_addr", dcache_miss_addr.wire)
    m.output("l2_data_resp_valid_out", l2_data_resp_valid.wire)
    m.output("l2_data_resp_data_out", l2_data_resp_data.wire)

    # ================================================================
    # Redirect / stall outputs
    # ================================================================

    m.output("redirect_valid", new_redir_valid.wire)
    m.output("redirect_target", new_redir_target.wire)
    m.output("stall_to_frontend", pipeline_stall)

    # Writeback forwarding
    wb_cnt_w = max(1, num_wb.bit_length()) if isinstance(num_wb, int) and num_wb > 0 else 3
    for i in range(num_wb):
        m.output(f"rob_wb_valid_{i}", wb_valid[i].wire)
        m.output(f"rob_wb_rob_idx_{i}", wb_rob_idx[i].wire)

    # Debug port
    m.output("debug_pc", fetch_pc.wire)

    # ================================================================
    # State updates
    # ================================================================

    domain.next()

    bpu_valid_r.set(ONE_1)
    fetch_pc_r.set(next_pc)
    redirect_valid_r.set(new_redir_valid)
    redirect_target_r.set(new_redir_target)
    be_stall_r.set(pipeline_stall)


build_xs_core.__pycircuit_name__ = "xs_core"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_xs_core, name="xs_core", eager=True,
        decode_width=2, commit_width=2, num_wb=2,
        num_load=1, num_store=1,
        data_width=16, pc_width=16,
        ptag_w=4, rob_idx_w=4, fu_type_w=3,
        block_bits=128,
    ).emit_mlir())
