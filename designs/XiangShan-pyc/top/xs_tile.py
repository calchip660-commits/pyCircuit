"""XSTile — Tile Integration (XSCore + L2 Cache) for XiangShan-pyc.

Combines one XSCore instance with its private L2 cache.  The tile is the
unit of replication in a multi-core XSTop.

Reference: XiangShan/src/main/scala/top/XSTile.scala

Ports:
  Downstream — to L3 / memory bus (TileLink-like A/D channels)
  Interrupt  — meip, seip, mtip, msip, debug
  Hart ID    — static configuration

Internal wiring:
  XSCore.l2_icache_miss → L2.ic_req
  XSCore.l2_dcache_miss → L2.dc_req
  L2.ic_grant → XSCore.l2_refill
  L2.dc_grant → XSCore.l2_data_resp
  L2.ds_req → downstream (output)
  downstream → L2.ds_resp (input)

Key features:
  T-XT-001  Core ↔ L2 miss/refill wiring
  T-XT-002  Downstream TileLink pass-through
  T-XT-003  Hart ID configuration port
  T-XT-004  Interrupt routing
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
    NUM_LDU,
    NUM_STA,
    PC_WIDTH,
    PTAG_WIDTH_INT,
    ROB_IDX_WIDTH,
    XLEN,
)

BLOCK_BITS = CACHE_LINE_SIZE
FU_TYPE_WIDTH = 3
NUM_WB_PORTS = 4
HART_ID_WIDTH = 4


def build_xs_tile(
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
    hart_id_w: int = HART_ID_WIDTH,
) -> None:
    """XSTile: XSCore + L2 cache tile unit."""

    ZERO_1 = cas(domain, m.const(0, width=1), cycle=0)
    ONE_1 = cas(domain, m.const(1, width=1), cycle=0)

    # ================================================================
    # External inputs
    # ================================================================

    # Hart ID (static config)
    hart_id = cas(domain, m.input("hart_id", width=hart_id_w), cycle=0)

    # Interrupts → routed to core
    meip = cas(domain, m.input("meip", width=1), cycle=0)
    seip = cas(domain, m.input("seip", width=1), cycle=0)
    mtip = cas(domain, m.input("mtip", width=1), cycle=0)
    msip = cas(domain, m.input("msip", width=1), cycle=0)
    debug_intr = cas(domain, m.input("debug_interrupt", width=1), cycle=0)

    # Downstream from L3/memory → L2 refill
    ds_resp_valid = cas(domain, m.input("ds_resp_valid", width=1), cycle=0)
    ds_resp_data = cas(domain, m.input("ds_resp_data", width=block_bits), cycle=0)
    ds_resp_source = cas(domain, m.input("ds_resp_source", width=1), cycle=0)

    # Writeback ports (from execution units, pass-through to core)
    wb_valid = [cas(domain, m.input(f"wb_valid_{i}", width=1), cycle=0)
                for i in range(num_wb)]
    wb_data = [cas(domain, m.input(f"wb_data_{i}", width=data_width), cycle=0)
               for i in range(num_wb)]
    wb_rob_idx = [cas(domain, m.input(f"wb_rob_idx_{i}", width=rob_idx_w), cycle=0)
                  for i in range(num_wb)]

    # Branch / exception redirect
    bru_redirect_valid = cas(domain, m.input("bru_redirect_valid", width=1), cycle=0)
    bru_redirect_target = cas(domain, m.input("bru_redirect_target", width=pc_width), cycle=0)
    rob_exception_valid = cas(domain, m.input("rob_exception_valid", width=1), cycle=0)
    rob_exception_pc = cas(domain, m.input("rob_exception_pc", width=pc_width), cycle=0)

    # Issue queue backpressure
    iq_int_ready = cas(domain, m.input("iq_int_ready", width=1), cycle=0)
    iq_fp_ready = cas(domain, m.input("iq_fp_ready", width=1), cycle=0)
    iq_mem_ready = cas(domain, m.input("iq_mem_ready", width=1), cycle=0)

    # Load/store writeback from MemBlock
    ld_wb_valid = [cas(domain, m.input(f"ld{i}_wb_valid", width=1), cycle=0)
                   for i in range(num_load)]
    ld_wb_data = [cas(domain, m.input(f"ld{i}_wb_data", width=data_width), cycle=0)
                  for i in range(num_load)]
    ld_wb_rob_idx = [cas(domain, m.input(f"ld{i}_wb_rob_idx", width=rob_idx_w), cycle=0)
                     for i in range(num_load)]
    st_wb_valid = [cas(domain, m.input(f"st{i}_wb_valid", width=1), cycle=0)
                   for i in range(num_store)]
    st_wb_rob_idx = [cas(domain, m.input(f"st{i}_wb_rob_idx", width=rob_idx_w), cycle=0)
                     for i in range(num_store)]

    # DCache miss from MemBlock
    dcache_miss_valid = cas(domain, m.input("dcache_miss_valid", width=1), cycle=0)
    dcache_miss_addr = cas(domain, m.input("dcache_miss_addr", width=pc_width), cycle=0)

    # ================================================================
    # XSCore logic (simplified inline)
    # ================================================================

    # Frontend fetch PC state
    fetch_pc_r = domain.state(width=pc_width, reset_value=0, name="xt_fetch_pc")
    bpu_valid_r = domain.state(width=1, reset_value=0, name="xt_bpu_v")

    fetch_pc = cas(domain, fetch_pc_r.wire, cycle=0)
    bpu_valid = cas(domain, bpu_valid_r.wire, cycle=0)

    # Redirect
    redirect_valid = bru_redirect_valid | rob_exception_valid
    redirect_target = mux(rob_exception_valid, rob_exception_pc, bru_redirect_target)
    flush = redirect_valid

    # L2 → Core refill: select based on ds_resp_source
    ic_refill_valid = ds_resp_valid & (~ds_resp_source)  # source 0 = IC
    dc_refill_valid = ds_resp_valid & ds_resp_source      # source 1 = DC

    # BPU fallthrough
    fallthrough_c = cas(domain, m.const(64, width=pc_width), cycle=0)
    bpu_pred_target = cas(
        domain, (fetch_pc.wire + fallthrough_c.wire)[0:pc_width], cycle=0
    )

    ibuf_ready = ONE_1  # simplified
    s0_fire = bpu_valid & ibuf_ready & (~flush)

    next_pc = fetch_pc
    next_pc = mux(s0_fire, bpu_pred_target, next_pc)
    next_pc = mux(redirect_valid, redirect_target, next_pc)

    # Pipeline: fetch → ICache → IFU → Decode (3 stages)
    s1_v = domain.cycle(s0_fire.wire, name="xt_s1_v")
    s1_pc = domain.cycle(fetch_pc.wire, name="xt_s1_pc")

    domain.next()

    s1_alive = s1_v & (~redirect_valid.wire)
    # ICache hit when L2 IC refill is available
    s1_resp = s1_alive & ic_refill_valid.wire
    s1_miss = s1_alive & (~ic_refill_valid.wire)

    # Core → L2: ICache miss request
    core_ic_miss_valid = s1_miss
    core_ic_miss_addr = s1_pc

    # Core → L2: DCache miss request (pass-through from MemBlock)
    core_dc_miss_valid = dcache_miss_valid.wire
    core_dc_miss_addr = dcache_miss_addr.wire

    # L2 request queue: arbitrate IC > DC
    l2_enq_valid = core_ic_miss_valid | core_dc_miss_valid
    l2_enq_addr = mux(core_ic_miss_valid,
                      cas(domain, core_ic_miss_addr, cycle=0),
                      cas(domain, core_dc_miss_addr, cycle=0))
    l2_enq_source = mux(core_ic_miss_valid, ZERO_1, ONE_1)

    # L2 → downstream output
    m.output("ds_req_valid", l2_enq_valid)
    m.output("ds_req_addr", l2_enq_addr.wire)
    m.output("ds_req_source", l2_enq_source.wire)

    s2_v = domain.cycle(s1_resp, name="xt_s2_v")
    s2_pc = domain.cycle(s1_pc, name="xt_s2_pc")
    s2_data = domain.cycle(ds_resp_data.wire, name="xt_s2_data")

    domain.next()

    s2_alive = s2_v & (~redirect_valid.wire)

    INST_WIDTH = 32
    s3_v = domain.cycle(s2_alive, name="xt_s3_v")
    s3_pc = domain.cycle(s2_pc, name="xt_s3_pc")
    s3_insts = [domain.cycle(
        s2_data[i * INST_WIDTH:(i + 1) * INST_WIDTH] if (i + 1) * INST_WIDTH <= block_bits
        else m.const(0, width=INST_WIDTH),
        name=f"xt_s3_i{i}")
        for i in range(decode_width)]

    domain.next()

    s3_alive = s3_v & (~redirect_valid.wire)

    # Decode outputs
    INST_BYTES = 2
    for i in range(decode_width):
        inst_pc = (s3_pc + m.const(i * INST_BYTES, width=pc_width))[0:pc_width]
        m.output(f"dec_valid_{i}", s3_alive)
        m.output(f"dec_inst_{i}", s3_insts[i])
        m.output(f"dec_pc_{i}", inst_pc)

    # ================================================================
    # Outputs
    # ================================================================

    m.output("redirect_valid", redirect_valid.wire)
    m.output("redirect_target", redirect_target.wire)

    m.output("hart_id_out", hart_id.wire)
    m.output("interrupt_pending", (meip | seip | mtip | msip | debug_intr).wire)

    # Forward load/store writeback
    for i in range(num_load):
        m.output(f"ld{i}_wb_valid_out", ld_wb_valid[i].wire)
        m.output(f"ld{i}_wb_data_out", ld_wb_data[i].wire)
        m.output(f"ld{i}_wb_rob_idx_out", ld_wb_rob_idx[i].wire)
    for i in range(num_store):
        m.output(f"st{i}_wb_valid_out", st_wb_valid[i].wire)
        m.output(f"st{i}_wb_rob_idx_out", st_wb_rob_idx[i].wire)

    # DC refill to MemBlock
    m.output("dc_refill_valid", dc_refill_valid.wire)
    m.output("dc_refill_data", ds_resp_data.wire)

    # Debug
    m.output("debug_pc", fetch_pc.wire)

    # ================================================================
    # State updates
    # ================================================================

    domain.next()

    bpu_valid_r.set(ONE_1)
    fetch_pc_r.set(next_pc)


build_xs_tile.__pycircuit_name__ = "xs_tile"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_xs_tile, name="xs_tile", eager=True,
        decode_width=2, commit_width=2, num_wb=2,
        num_load=1, num_store=1,
        data_width=16, pc_width=16,
        ptag_w=4, rob_idx_w=4, fu_type_w=3,
        block_bits=128, hart_id_w=4,
    ).emit_mlir())
