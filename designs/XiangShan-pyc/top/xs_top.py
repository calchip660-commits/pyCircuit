"""XSTop — SoC Top-Level Wrapper for XiangShan-pyc.

Top-level SoC integrating multiple XSTile instances with a shared memory
bus and peripheral interface.  This is the outermost module that maps to
the chip boundary.

Reference: XiangShan/src/main/scala/top/XSTop.scala

Ports:
  - AXI4 memory port (simplified TileLink-to-AXI bridge)
  - Per-tile interrupt inputs (meip, seip, mtip, msip)
  - Debug port / JTAG interface
  - Peripheral access port

Internal:
  - Replicate XSTile per core
  - Shared downstream bus arbiter (round-robin simplified)
  - Interrupt distributor

Key features:
  S-XT-001  Multi-core tile instantiation
  S-XT-002  Shared memory bus arbitration
  S-XT-003  Per-core interrupt routing
  S-XT-004  AXI4 memory port output
  S-XT-005  Debug / JTAG interface
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
    PC_WIDTH,
    XLEN,
)

BLOCK_BITS = CACHE_LINE_SIZE
HART_ID_WIDTH = 4
AXI_ID_WIDTH = 8
AXI_ADDR_WIDTH = PC_WIDTH
AXI_DATA_WIDTH = XLEN


def build_xs_top(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    num_cores: int = 2,
    data_width: int = AXI_DATA_WIDTH,
    addr_width: int = AXI_ADDR_WIDTH,
    block_bits: int = BLOCK_BITS,
    hart_id_w: int = HART_ID_WIDTH,
    axi_id_w: int = AXI_ID_WIDTH,
) -> None:
    """XSTop: top-level SoC with multiple tiles + peripherals."""

    core_sel_w = max(1, (num_cores - 1).bit_length())

    ZERO_1 = cas(domain, m.const(0, width=1), cycle=0)
    ONE_1 = cas(domain, m.const(1, width=1), cycle=0)

    # ================================================================
    # External inputs
    # ================================================================

    # Per-core interrupt inputs
    core_meip = [cas(domain, m.input(f"core{i}_meip", width=1), cycle=0)
                 for i in range(num_cores)]
    core_seip = [cas(domain, m.input(f"core{i}_seip", width=1), cycle=0)
                 for i in range(num_cores)]
    core_mtip = [cas(domain, m.input(f"core{i}_mtip", width=1), cycle=0)
                 for i in range(num_cores)]
    core_msip = [cas(domain, m.input(f"core{i}_msip", width=1), cycle=0)
                 for i in range(num_cores)]

    # Debug / JTAG
    debug_req_valid = cas(domain, m.input("debug_req_valid", width=1), cycle=0)
    debug_req_addr = cas(domain, m.input("debug_req_addr", width=addr_width), cycle=0)
    debug_req_data = cas(domain, m.input("debug_req_data", width=data_width), cycle=0)
    debug_req_op = cas(domain, m.input("debug_req_op", width=2), cycle=0)

    # AXI4 memory port — read response from external memory
    axi_r_valid = cas(domain, m.input("axi_r_valid", width=1), cycle=0)
    axi_r_data = cas(domain, m.input("axi_r_data", width=data_width), cycle=0)
    axi_r_id = cas(domain, m.input("axi_r_id", width=axi_id_w), cycle=0)
    axi_r_last = cas(domain, m.input("axi_r_last", width=1), cycle=0)

    # AXI4 write response
    axi_b_valid = cas(domain, m.input("axi_b_valid", width=1), cycle=0)
    axi_b_id = cas(domain, m.input("axi_b_id", width=axi_id_w), cycle=0)

    # Per-tile downstream request (from tiles → to shared bus)
    tile_ds_req_valid = [cas(domain, m.input(f"tile{i}_ds_req_valid", width=1), cycle=0)
                         for i in range(num_cores)]
    tile_ds_req_addr = [cas(domain, m.input(f"tile{i}_ds_req_addr", width=addr_width), cycle=0)
                        for i in range(num_cores)]
    tile_ds_req_source = [cas(domain, m.input(f"tile{i}_ds_req_source", width=1), cycle=0)
                          for i in range(num_cores)]

    # ================================================================
    # Shared bus arbiter (round-robin simplified)
    # ================================================================

    arb_sel_r = domain.state(width=core_sel_w, reset_value=0, name="xs_arb_sel")
    arb_sel = cas(domain, arb_sel_r.wire, cycle=0)

    # Priority select: check current arb_sel first, then wrap
    bus_req_valid = ZERO_1
    bus_req_addr = cas(domain, m.const(0, width=addr_width), cycle=0)
    bus_req_source = ZERO_1
    bus_req_core = cas(domain, m.const(0, width=core_sel_w), cycle=0)

    for i in range(num_cores):
        i_c = cas(domain, m.const(i, width=core_sel_w), cycle=0)
        is_selected = (arb_sel == i_c) & tile_ds_req_valid[i]
        bus_req_valid = mux(is_selected, ONE_1, bus_req_valid)
        bus_req_addr = mux(is_selected, tile_ds_req_addr[i], bus_req_addr)
        bus_req_source = mux(is_selected, tile_ds_req_source[i], bus_req_source)
        bus_req_core = mux(is_selected, i_c, bus_req_core)

    # Fallback: if current selection has no request, try others
    for i in range(num_cores):
        i_c = cas(domain, m.const(i, width=core_sel_w), cycle=0)
        fallback = tile_ds_req_valid[i] & (~bus_req_valid)
        bus_req_valid = mux(fallback, ONE_1, bus_req_valid)
        bus_req_addr = mux(fallback, tile_ds_req_addr[i], bus_req_addr)
        bus_req_source = mux(fallback, tile_ds_req_source[i], bus_req_source)
        bus_req_core = mux(fallback, i_c, bus_req_core)

    # ================================================================
    # AXI4 read request output (TileLink → AXI bridge, simplified)
    # ================================================================

    m.output("axi_ar_valid", bus_req_valid.wire)
    m.output("axi_ar_addr", bus_req_addr.wire)
    # Encode {core_id, source} into AXI ID
    axi_out_id = cas(domain,
                     m.cat(bus_req_core.wire, bus_req_source.wire,
                           m.const(0, width=max(1, axi_id_w - core_sel_w - 1))),
                     cycle=0)
    m.output("axi_ar_id", axi_out_id.wire)
    m.output("axi_ar_len", m.const(0, width=8))  # single beat
    m.output("axi_ar_size", m.const(3, width=3))  # 8 bytes

    # ================================================================
    # AXI4 read response → route to correct tile
    # ================================================================

    # Decode core_id from AXI R ID
    resp_core = axi_r_id[1:1 + core_sel_w]
    resp_source = axi_r_id[0:1]

    for i in range(num_cores):
        i_c = cas(domain, m.const(i, width=core_sel_w), cycle=0)
        is_this_core = resp_core == i_c
        m.output(f"tile{i}_ds_resp_valid", (axi_r_valid & is_this_core).wire)
        m.output(f"tile{i}_ds_resp_data", axi_r_data.wire)
        m.output(f"tile{i}_ds_resp_source", resp_source.wire)

    # ================================================================
    # Per-core interrupt routing
    # ================================================================

    for i in range(num_cores):
        m.output(f"tile{i}_meip", core_meip[i].wire)
        m.output(f"tile{i}_seip", core_seip[i].wire)
        m.output(f"tile{i}_mtip", core_mtip[i].wire)
        m.output(f"tile{i}_msip", core_msip[i].wire)
        m.output(f"tile{i}_hart_id", m.const(i, width=hart_id_w))

    # ================================================================
    # Debug port output
    # ================================================================

    m.output("debug_resp_valid", debug_req_valid.wire)
    m.output("debug_resp_data", debug_req_data.wire)

    # ================================================================
    # Pipeline register + arbiter state update
    # ================================================================

    s1_bus_valid = domain.cycle(bus_req_valid.wire, name="xs_s1_bv")
    s1_bus_core = domain.cycle(bus_req_core.wire, name="xs_s1_bc")

    domain.next()

    # Round-robin: advance selector when a request fires
    one_sel = cas(domain, m.const(1, width=core_sel_w), cycle=0)
    max_sel = cas(domain, m.const(num_cores - 1, width=core_sel_w), cycle=0)
    next_sel = cas(domain, (arb_sel.wire + one_sel.wire)[0:core_sel_w], cycle=0)
    wrap_sel = mux(arb_sel == max_sel,
                   cas(domain, m.const(0, width=core_sel_w), cycle=0),
                   next_sel)
    arb_sel_r.set(mux(bus_req_valid, wrap_sel, arb_sel))

    # AXI write channel (simplified: no write support yet)
    m.output("axi_aw_valid", ZERO_1.wire)
    m.output("axi_w_valid", ZERO_1.wire)
    m.output("axi_b_ready", ONE_1.wire)


build_xs_top.__pycircuit_name__ = "xs_top"


if __name__ == "__main__":
    print(compile_cycle_aware(
        build_xs_top, name="xs_top", eager=True,
        num_cores=2, data_width=16, addr_width=16,
        block_bits=128, hart_id_w=4, axi_id_w=4,
    ).emit_mlir())
