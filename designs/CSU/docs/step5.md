# Step 5 — Map sequential algorithm to pipeline / cycle alignment

**Method reference:** `docs/pycircuit_implementation_method.md` § Step 5  
**Prerequisite:** `step4.md`, `function_list.md`

**Converted specs:** Reconcile pipeline depth with timing / latency narratives and figures described in **`converted/SRC-07_*.md`** (e.g. load-to-use, hit/miss paths, §7 clock/reset). If the digest lacks a numeric latency, cite **DOCX section + figure ID** and original binary until extracted into `ASSUMPTIONS.md` or `cycle_budget.md`.

**Large Step 5?** **`workflow_substeps.md`** § Step 5 (**5a–5d**): Inc-0 baseline → LTU → CDC → wide-bus staging.

---

## 1. Goal

Assign each logical operation from Step 4 to a **logical occurrence cycle** on `CycleAwareDomain`, so that:

- Pipeline stages are **explicit**.  
- **Parent/child** cycle relationships are **safe** (push/pop).  
- Register boundaries match **timing** expectations from SRC-07 (when available).

---

## 2. Default CSU pipeline (starting point — revise per DOCX)

**周期预算权威表（Inc-0 及后续增量）：** `cycle_budget.md`。

| Stage ID | Occurrence 索引（V5） | `domain.next()` 累计（进入本段之前） | Operations mapped from Step 4 | Register boundary |
|----------|----------------------|----------------------------------------|------------------------------|-------------------|
| S0 | **0** | 0 | Sample all **RX** inputs via `cas(..., cycle=0)`; `decode_incoming_flits`; `update_reset_and_error_state` (comb part) | Optional: input skid regs if DOCX requires |
| S1 | **1** | 1 | `handle_snoop`, `absorb_rxrsp`, `absorb_rxdat`, `advance_transactions`, `handle_rxwkup`, `handle_rxfill`; compute **next** state | `domain.state` + `.set()` for tracker/buf/dir |
| S2 | **2** | 2 | `build_txreq`, `build_txrsp`, `build_txdat`; credit updates | `domain.cycle` on wide egress mux outputs |
| S3 | **3** | 3 | `pack_all_flits`; drive `m.output` | Optional pipeline for IO timing |

**本表规划的 occurrence 段数：** **4**（索引 **0 … 3**），对应顶层 `build_csu` 中 **`domain.next()` 调用次数 = 3**（每调用一次进入下一 occurrence 段，最后在段 3 上绑定 `m.output`）。

**实现核对：** `designs/CSU/csu.py` 当前为 **3** 次 `domain.next()`、**4** 段 occurrence；`emit_csu_mlir()` 经 `assert_inc0_mlir_cycle_contract` 校验 **`pyc.reg` = 13**、**`_v5_bal_` = 4**，并含 **`pyc.reset_active`**。详见 `cycle_budget.md` §2。

**Rule:** If SRC-07 mandates **2-cycle** RAM read for directory, insert **S1b** at cycle 1.5 equivalent = extra `domain.next()` + `domain.cycle` on partial results — 并同步更新 `cycle_budget.md` 与 `csu.py` 内 Inc-x 常量。

---

## 3. Helper / child function discipline

When refactoring Step 4 functions into Python helpers that use `domain`:

```text
def helper(domain, ...):
    domain.push()
    try:
        domain.next()
        ...  # inner work
    finally:
        domain.pop()
```

**Never** leave `cycle_index` changed for the caller unless intentional (document in `ASSUMPTIONS.md`).

---

## 4. Signal cycle tagging table (fill during implementation)

| Signal group | Produced at cycle | Consumed at cycle | Alignment method |
|--------------|-------------------|-------------------|------------------|
| `decoded` | 0 | 1 | automatic balance or `domain.cycle` |
| `tracker_next` | 1 | 2 | `domain.state` |
| `txreq_q` | 2 | 3 | `domain.cycle` |

*Expand one row per major net.*

---

## 5. Timing closure notes

- Wide buses (**615b**): consider **registered outputs** always on `txdat` to meet fanout.  
- If **critical path** in `advance_transactions`, split into two cycles (document in `step6.md`).  
- **`feature_list.md` F-031 (LTU 20-cycle):** map advertised latency to pipeline depth + SRAM access; update `cycle_budget.md` if extra `domain.next()` is required.  
- **`feature_list.md` F-052:** async FIFO depths (SNP/DAT/RSP) imply **CDC** boundaries — occurrence mapping applies per **clock domain**; document which `build_csu` slice is synchronous-only vs wrapper.

---

## 6. Completion checklist

- [ ] Pipeline table reviewed against **SRC-07** timing (`converted/SRC-07_*.md` + original DOCX for figures)  
- [ ] **Occurrence 段数** 与 **`domain.next()` 次数** 已写入 `cycle_budget.md`（或与 Inc-x 行一致）  
- [ ] Every Step 4 function assigned to ≥1 stage  
- [ ] Push/pop plan for any nested helper documented

**Next step:** `step6.md`
