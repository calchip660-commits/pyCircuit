# Step 6 — Cycle-aware detailed pseudocode (V5)

**Method reference:** `docs/pycircuit_implementation_method.md` § Step 6  
**Prerequisite:** `step5.md`, `port_list.md`

**Converted specs:** **Slice positions** and widths for REQ/RSP/DAT/SNP must match **`converted/SRC-01_xlsx_CHI_Core_CSU_ALL.md`** (and SoC field tables where used). **F-003** opcode allowlist in `csu.py` must match **`converted/SRC-01_xlsx_CHI_CSU_SoC_Opcode.md`** column **P HC supports（950）** = Yes. **Directions** follow `port_list.md` / `ASSUMPTIONS.md` (TB may still use `m.input` for all pins until pin-kind is modeled).

**SRC-07 Master capabilities:** When emitting **txreq**/**txdat**/**txrsp** toward SoC, pseudocode comments must reference **`feature_list.md` F-045** ↔ SRC-07 **Tab 3‑11** (`converted/SRC-07_*.md` § Master Interface) for optional CHI behaviors (DCT, poison, persist broadcast, …).

**Large Step 6?** **`workflow_substeps.md`** § Step 6 (**6a–6d**): shell + opcode → state → Tab 3‑11 comments → child modules.

---

## 1. Goal

Produce **implementation-ready** pseudocode using V5 idioms: `cas`, `domain.next()`, `domain.state`, `domain.cycle`, `mux`, `m.input`/`m.output`.

**周期契约（须与 Step 5 一致）：** 见 **`cycle_budget.md`**。**当前 `csu.py`：** `domain.next()` **3** 次 → occurrence **4** 段（索引 0…3）；`emit_csu_mlir()` 在发出 MLIR 前执行 **`assert_inc0_mlir_cycle_contract`**，锁定 **`pyc.reg` = 13**、**`_v5_bal_` = 4**，并校验存在 **`pyc.reset_active`**。任何增删 `domain.next()` / `state` / `cycle` 须同步改 `cycle_budget.md` 与 `csu.py` 中 `INC0_*`（或后续 `INCx_*`）常量。

---

## 2. Width constants (from `port_list.md`)

```python
# Pseudocode constants — keep in csu.py
W_TXREQ = 97
W_TXRSP = 30
W_TXDAT = 615
W_RXRSP = 42
W_RXDAT = 584
W_RXSNP = 82
W_RSP1 = 4
W_RXWKUP = 18
W_RXERR = 2
W_RXFILL = 3
W_TXREQ_PEND = 2
# TXN_TRACKER_WIDTH, DATA_BUF_WIDTH from design
```

---

## 3. Top-level build skeleton

```python
def build_csu(m: CycleAwareCircuit, domain: CycleAwareDomain):
    # --- Cycle 0: inputs (see port_list.md + ASSUMPTIONS.md for CSU-centric in/out) ---
    rxrsp  = cas(domain, m.input("rxrsp", width=W_RXRSP), cycle=0)
    rxdat  = cas(domain, m.input("rxdat", width=W_RXDAT), cycle=0)
    rxsnp  = cas(domain, m.input("rxsnp", width=W_RXSNP), cycle=0)
    rsp1   = cas(domain, m.input("rsp1_side", width=W_RSP1), cycle=0)
    rxwkup = cas(domain, m.input("rxwkup", width=W_RXWKUP), cycle=0)
    rxerr  = cas(domain, m.input("rxerr", width=W_RXERR), cycle=0)
    rxfill = cas(domain, m.input("rxfill", width=W_RXFILL), cycle=0)

    decoded = decode_incoming_flits(rxrsp, rxdat, rxsnp, rsp1, rxwkup, rxerr, rxfill)

    domain.next()  # --- Cycle 1 ---

    fault = latch_fault_from_reset_and_err(decoded.err_part)  # refine

    txn = domain.state(width=TXN_TRACKER_WIDTH, reset_value=0, name="txn")
    buf = domain.state(width=DATA_BUF_WIDTH, reset_value=0, name="buf")
    dir_ = domain.state(width=DIR_WIDTH, reset_value=0, name="dir")

    snoop_d = handle_snoop(rxsnp, rsp1, dir_)
    rsp_d = absorb_rxrsp(rxrsp, txn)
    dat_d = absorb_rxdat(rxdat, buf)

    txn_next, buf_next, dir_next = advance_transactions(
        txn, buf, dir_, snoop_d, rsp_d, dat_d, decoded, fault
    )
    txn.set(txn_next)
    buf.set(buf_next)
    dir_.set(dir_next)

    wk_d = handle_rxwkup(rxwkup, txn)
    fl_d = handle_rxfill(rxfill, buf)
    # merge wk_d, fl_d into txn/buf if needed (same cycle or next — document)

    domain.next()  # --- Cycle 2 ---

    txreq_b = build_txreq(txn, buf, fault)
    txrsp_b = build_txrsp(txn, fault)
    txdat_b = build_txdat(txn, buf, fault)

    txreq_q = domain.cycle(txreq_b, name="txreq_q")
    txrsp_q = domain.cycle(txrsp_b, name="txrsp_q")
    txdat_q = domain.cycle(txdat_b, name="txdat_q")

    pend_b = build_txreq_pend(txn)  # F-012
    pend_q = domain.cycle(pend_b, name="txreq_pend_q")

    domain.next()  # --- Cycle 3 ---

    m.output("txreq", txreq_q)
    m.output("txrsp", txrsp_q)
    m.output("txdat", txdat_q)
    m.output("txreq_pend", pend_q)
    # add remaining outputs when directions finalized
```

---

## 4. Reset / idle behavior in pseudocode

- On **reset active** (map SoC **SRESET_N** / **SPORRESET_N** per `converted/SRC-07_*.md` §7): force `txn_next`, `buf_next` to idle constants; zero egress flits.  
- Implement either **synchronous reset** in `domain.state(..., reset_value=...)` plus mux, or **async** only if DOCX allows (rare in this flow).

---

## 5. Back-pressure

If **valid/ready** exists:

- Add `*_valid` / `*_ready` as separate `m.input`/`m.output`.  
- Gate `txn.set` when downstream not ready (per CHI rules).

---

## 6. Completion checklist

- [ ] Every width matches `port_list.md`  
- [ ] REQ/RSP/DAT/SNP **slices** match **`converted/SRC-01_xlsx_*.md`**; **F-003** allowlist matches **`converted/SRC-01_xlsx_CHI_CSU_SoC_Opcode.md`**  
- [ ] **`domain.next()` 次数** = `step5.md` / `cycle_budget.md` 规划值（Inc-0：**3**）  
- [ ] Every `F-xxx` has a comment pointing to pseudocode region  
- [ ] `emit_csu_mlir()` succeeds（含 Inc-0 MLIR 周期契约断言）

**Next step:** `step7.md`
