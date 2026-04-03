# CSU — functional decomposition (algorithmic functions)

**Purpose:** Catalog **logical subroutines** for the CSU behavior (Step 4 / Step 5). These are **not** necessarily 1:1 RTL modules; they are **clean partitions** for implementation and review.

**Related:** `step4.md`, `step5.md`, `step6.md`, `feature_list.md`.

---

## 1. Naming convention

- **Pure** = no implicit persistent state; all state passed in/out.
- **Stateful** = reads/writes conceptual registers (`transaction_tracker`, `data_buffer_state`, etc.).
- **HW mapping** = suggested pyCircuit construct (V5 `domain.state`, `@module` child, etc.).

---

## 2. Top-level orchestrator

| Name | Kind | Purpose | Inputs (conceptual) | Outputs | Reads state | Writes state | HW mapping |
|------|------|---------|---------------------|---------|-------------|--------------|------------|
| `csu_main_cycle` | Stateful | One conceptual “cycle” of CSU work | All RX flits, reset, config | All TX flits + sidebands | tracker, buf, credits | tracker, buf, credits | `build_csu()` body in `csu.py` |

---

## 3. Reset and fault

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `update_reset_and_error_state` | Stateful | Latch reset; process `rxerr` | `rst`, `rxerr_flit` | `fault_status`, `global_stall` mask | F-001, F-010 |

**Precondition:** Inputs stable for current sample time.  
**Postcondition:** If reset active, downstream logic sees **idle** semantics.

---

## 4. Credit and pending

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `update_credit_and_pending_counters` | Stateful | TXREQ_PEND, CHI credits, return paths | `txreq_pend_in/out`, credit signals TBD | `allow_txreq`, `credit_avail` | F-012 |

**Invariant:** Counters never exceed DOCX maximums.

---

## 5. Snoop path

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `handle_snoop` | Stateful | Decode RXSNP + RSP1 side | `rxsnp_flit`, `rsp1_side`, directory snapshot | `snoop_reaction` struct | F-008 |

**`snoop_reaction` fields (example):** `invalidate_line`, `probe_ack_needed`, `fwd_tgt_id`, etc. — refine per SRC-07.

---

## 6. Response and data absorption

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `absorb_rxrsp` | Stateful | Parse RXRSP, update txn | `rxrsp_flit`, `tracker` | `rsp_delta` | F-005 |
| `absorb_rxdat` | Stateful | Parse RXDAT beats | `rxdat_flit`, `buf` | `dat_delta` | F-007 |

---

## 7. Transaction advancement

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `advance_transactions` | Stateful | Merge deltas + advance FSM | `tracker`, `buf`, `snoop_reaction`, `rsp_delta`, `dat_delta`, credits | `tracker_next`, `buf_next` | F-002–F-008, F-013 |

**Complexity note:** This is the **largest** function; consider splitting into `advance_read_txns`, `advance_write_txns`, `advance_snoop_txns` after DOCX clarifies classes.

---

## 8. Egress flit builders

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `build_txreq` | Pure/Stateful | Assemble 97b REQ flit | `tracker`, internal request sources | `txreq_flit` | F-002, F-003 |
| `build_txrsp` | Pure/Stateful | Assemble 30b RSP flit | `tracker` | `txrsp_flit` | F-004 |
| `build_txdat` | Pure/Stateful | Assemble 615b DAT flit | `tracker`, `buf` | `txdat_flit` | F-006 |

---

## 9. Wakeup and fill

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `handle_rxwkup` | Stateful | Wakeup processing | `rxwkup_flit`, `tracker` | `tracker_next` delta | F-009 |
| `handle_rxfill` | Stateful | Fill processing | `rxfill_flit`, `buf` | `buf_next` delta | F-011 |

---

## 10. Master / CPU interface shims (SRC-07 §3)

These mirror **Master interface** / **CPU slave** sub-blocks in `converted/SRC-07_linxcore950_csu_design_spec.md`. Logical partitions only; `csu.py` may fold them until Inc-x introduces child modules.

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `mst_mrb_track_request` | Stateful | MRB: TxnID + CPU metadata | Internal request, CPU ids | `mrb_txn_ctx` | F-015 |
| `mst_convert_txreq` | Pure/Stateful | Ring `exp_mst_txreq` → CHI **txreq** | Ring flit, `mrb_txn_ctx` | 97b REQ | F-016, F-002, F-003 |
| `mst_convert_txdat` | Pure/Stateful | Ring → CHI **txdat** | Ring data beat | 615b DAT | F-017, F-006 |
| `mst_convert_txrsp` | Pure/Stateful | Ring → CHI **txrsp** | Ring rsp beat | 30b RSP | F-017, F-004 |
| `mst_convert_rxsnp` | Pure/Stateful | CHI **rxsnp** → ring | `rxsnp`, `rsp1_side` | `mst_exp_rxsnp` | F-018, F-008 |
| `mst_convert_rxrsp` | Stateful | CHI **rxrsp** → ring + **retry_buf** | `rxrsp` | `mst_exp_rxrsp`, retry state | F-018, F-019, F-005 |
| `mst_convert_rxdat` | Stateful | CHI **rxdat** → ring | `rxdat` | `mst_exp_rxdat` | F-018, F-007 |
| `cpu_rsp_div_route` | Stateful | **rsp_div** PM vs datapath | Ring `txrsp1` | link vs int_sys `rxrsp1` | F-020 |
| `cpu_link_pm_handshake` | Stateful | **link** PMU / `allow_req` / `slc_pwr_stat` | PM packets | `txreq` sideband / ack | F-020 |
| `cpu_rxsnp_distribute` | Stateful | **rxsnp_ctl** coherency on/off | Ring snoop | `rxsnp` or loopback `txrsp` | F-021 |
| `cpu_snoop_bypass_to_txrsp` | Stateful | **u_rxsnp → u_txrsp** | Misrouted snoop | `txrsp` with forwarded ids | F-022 |

---

## 11. Output packing

| Name | Kind | Purpose | Inputs | Outputs | Features |
|------|------|---------|--------|---------|----------|
| `pack_all_flits` | Pure | Concatenate / align to `port_list` widths | Built flits, side effects | Final port vectors | F-002–F-006 |

---

## 12. Decode helper (combinational)

| Name | Kind | Purpose | Inputs | Outputs | Used in |
|------|------|---------|--------|---------|---------|
| `decode_incoming_flits` | Pure | Field extract + valid decode | All RX buses | `decoded` struct | `step6.md` Cycle 0 |

---

## 13. Call graph (summary)

```text
csu_main_cycle
├── update_reset_and_error_state
├── update_credit_and_pending_counters
├── handle_snoop
├── absorb_rxrsp
├── absorb_rxdat
├── advance_transactions
├── build_txreq
├── build_txrsp
├── build_txdat
├── handle_rxwkup
├── handle_rxfill
└── pack_all_flits
```

---

## 14. Implementation order suggestion

1. `decode_incoming_flits` + `pack_all_flits` (width checks).  
2. `update_reset_and_error_state`.  
3. `absorb_rxrsp` / `absorb_rxdat` with **stub** tracker.  
4. `advance_transactions` (grow with FSM).  
5. `build_txreq` / `build_txrsp` / `build_txdat`.  
6. `handle_snoop`, credit, WKUP, FILL.
