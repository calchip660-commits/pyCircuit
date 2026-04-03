# Step 4 — Sequential (imperative) behavior without cycle annotations

**Method reference:** `docs/pycircuit_implementation_method.md` § Step 4  
**Deliverable:** This document §2 + `function_list.md`

**Converted specs:** Name fields and sub-behaviors consistently with **`converted/SRC-01_xlsx_*.md`** (flit layouts) and **`converted/SRC-07_*.md`** (Master interface / CPU slave / flows). **`function_list.md` §10** maps SRC-07 “Structure” bullets to function names (MRB, Txreq shim, `retry_buf`, etc.).

**Large Step 4?** **`workflow_substeps.md`** § Step 4 (**4a–4d**): main loop → master/CPU stubs → flows → state bundles.

---

## 1. Goal

Express CSU behavior as a **single-threaded imperative program** (Python/C-like), **without** `domain.next()` and **without** RTL module boundaries. This isolates **what** happens from **when** it registers.

---

## 1b. Cycle / timing contract（本步骤）

顺序模型 **0** 个 RTL 拍；**不** 使用 `domain.next()`。**何时打拍** 仅在 **Step 5 + `cycle_budget.md`** 中规划；Step 6 实现须与之 **数值一致**。

---

## 2. Main routine (expanded pseudocode)

```text
def csu_main_cycle(
    rxrsp_flit, rxdat_flit, rxsnp_flit, rsp1_flit,
    rxwkup_flit, rxerr_flit, rxfill_flit,
    txreq_pend_in, chi_credits_in,
    reset_pin, config_regs,
    transaction_tracker, data_buffer_state, credit_state, directory_state
):
    # Returns: updated states + output flits + txreq_pend_out + credit_out

    fault = update_reset_and_error_state(rxerr_flit, reset_pin, transaction_tracker)

    if fault.global_reset:
        return idle_outputs_and_zeroed_state()

    credit_state2, allow_tx = update_credit_and_pending_counters(
        credit_state, txreq_pend_in, chi_credits_in
    )

    snoop_delta = handle_snoop(rxsnp_flit, rsp1_flit, directory_state)

    rsp_delta = absorb_rxrsp(rxrsp_flit, transaction_tracker)
    dat_delta = absorb_rxdat(rxdat_flit, data_buffer_state)

    tracker2, buf2, dir2 = advance_transactions(
        transaction_tracker,
        data_buffer_state,
        directory_state,
        snoop_delta,
        rsp_delta,
        dat_delta,
        credit_state2,
        allow_tx,
    )

    wk_delta = handle_rxwkup(rxwkup_flit, tracker2)
    fill_delta = handle_rxfill(rxfill_flit, buf2)

    tracker3 = apply_delta(tracker2, wk_delta)
    buf3 = apply_delta(buf2, fill_delta)

    txreq_flit = build_txreq(tracker3, config_regs, allow_tx)
    txrsp_flit = build_txrsp(tracker3)
    txdat_flit = build_txdat(tracker3, buf3)

    txreq_pend_out, credit_out = update_egress_credit_side(tracker3, credit_state2)

    return pack_all_flits(txreq_flit, txrsp_flit, txdat_flit, txreq_pend_out, credit_out, tracker3, buf3, dir2)
```

*Types are conceptual structs; refine field names from **`converted/SRC-01_xlsx_*_field.md`** and behavior from **`converted/SRC-07_*.md`**.*

---

## 3. State bundle definitions (to document before Step 5)

| State name | Role | Suggested fields (TBD) |
|------------|------|------------------------|
| `transaction_tracker` | In-flight CHI transactions | per-txn: TxnId, state enum, beat count, … |
| `data_buffer_state` | Line / beat storage | data array, BE, poison |
| `credit_state` | CHI credits / pend | counters per channel |
| `directory_state` | Coherence directory | presence, dirty, shared |

---

## 4. Rules

- **No** `domain.next()` in this step.  
- **No** partitioning into Verilog modules — only **functions**.  
- Each function in §2 must appear in `function_list.md` with pre/postconditions.

---

## 4b. SRC-07 chapter → behavior (cross-check `feature_list.md` F-023–F-075 + heading checklist)

| SRC-07 digest chapter | Typical decomposition target |
|------------------------|------------------------------|
| Overview / Topology | Config, address decode (F-023–F-026), LTU note (F-031) |
| Microarchitecture pipeline | `advance_transactions`, RAM/arb helpers (F-032–F-044) |
| Master / CPU Interface | `function_list.md` §10 `mst_*` / `cpu_*` (F-015–F-022, F-045–F-051) |
| Feature (Alloc / Alias / Order) | Policy inside `advance_transactions`, `handle_snoop` (F-053–F-055) |
| Flow (Streaming / CMO / …) | Dedicated flow subroutines (F-056–F-059) |
| Algorithm / RRIP | Arb + replacement helpers (F-060–F-061) |
| Clock/Reset / PIPE | `update_reset_and_error_state`, clock enables (F-001, F-014, F-062) |
| CPU / SoC interface § | Port compliance checkers / TB (**F-072–F-075**) |

---

## 5. Completion checklist

- [ ] `function_list.md` call graph matches §2  
- [ ] **F-023–F-075** behaviors either appear in §2 pseudocode, §10 shims, or are explicitly deferred with a **G-xx** gap  
- [ ] Peer review: every RX channel consumed; every TX channel produced  
- [ ] Ambiguities logged in `ASSUMPTIONS.md`

**Next step:** `step5.md`
