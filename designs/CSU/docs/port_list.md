# CSU — top-level port and bus list

**Sources:** SRC-01 (`CSU 接口Protocol_辅助设计输入.xlsx` Sheet1–6), SRC-07 (DOCX), SRC-08 (PDF). **Markdown digests:** `converted/SRC-01_xlsx_*.md`, `converted/SRC-07_linxcore950_csu_design_spec.md`, `converted/SRC-08_chi_architecture_spec_extract.md` (partial).  
**Related:** `feature_list.md`, `traceability.md`, `ASSUMPTIONS.md`, `step3.md`.

---

## 1. Conventions

- **Width:** total scalar width in bits for one flit (or side-band) as packed on the CSU boundary.
- **Direction (CSU-centric):** `in` = into CSU, `out` = out of CSU. Filled per `ASSUMPTIONS.md` §1 (CHI naming + SRC-07 SoC interface narrative); formal sign-off still required against SRC-07 §9.
- **Clock domain:** default single `clk` / `rst`; override per column when DOCX defines multiple.

---

## 2. Clock and reset

| Port | Direction | Width | Type | Domain | Description |
|------|-----------|-------|------|--------|-------------|
| `clk` | in | 1 | clock | `SCLK` | Primary CSU subsystem clock (SRC-07 §7.1). |
| `rst` | in | 1 | reset | `SCLK` | TB / integration maps SoC **SRESET_N** / **SPORRESET_N** (active‑low, ≥16 cycles) into this single synchronous reset until hierarchy is modeled. |

---

## 3. CHI-style flit buses (aggregated widths from Sheet1)

| Logical name | XLSX channel / note | Width (bits) | Direction (CSU) | Valid/ready | Source |
|--------------|---------------------|-------------|-----------------|-------------|--------|
| `txreq` | TXREQ, REQFLIT_W | **97** | **out** | TBD | SRC-01 |
| `txreq_pend` | TXREQ_PEND, REQPENDFLIT_PA7 | **2** | **in** | TBD | SRC-01 |
| `txrsp` | TXRSP, RSPFLIT_W | **30** | **out** | TBD | SRC-01 |
| `rxrsp` | RXRSP, RSPFLIT_W | **42** | **in** | TBD | SRC-01 |
| `txdat` | TXDAT, DATFLIT_W | **615** | **out** | TBD | SRC-01 |
| `rxdat` | RXDAT, DATFLIT_W | **584** | **in** | TBD | SRC-01 |
| `rxwkup` | RXWKUP, WKUPFLIT_W | **18** | **in** | TBD | SRC-01 |
| `rxerr` | RXERR (ERR_FLIT_*) | **2** | **in** | TBD | SRC-01 |
| `rxfill` | RXFILL, FILLFLIT_W | **3** | **in** | TBD | SRC-01 |
| `rxsnp` | RXSNP, SNPFLIT_W | **82** | **in** | TBD | SRC-01 |
| `rsp1_side` | RXSNP companion, RSP1FLIT_W | **4** | **in** | TBD | SRC-01 |

**Naming in RTL/Python:** use lowercase with underscores; map 1:1 to `m.input` / `m.output` after direction is fixed.

---

## 4. TXREQ field inventory (Sheet1 CSU视角 — illustrative)

*Authoritative bit map: `converted/SRC-01_xlsx_CHI_Core_CSU_ALL.md` (CSU视角). SoC-only field names: `converted/SRC-01_xlsx_CHI_CSU_SoC_ReqFlit_field.md`.*

| Field | Width (bits) | MSB:LSB (Sheet1 CSU视角) | Notes |
|-------|-------------|---------------------------|--------|
| REQFLIT_QOS | 4 | 3:0 | |
| REQFLIT_TGTID | 6 | *TBD in Sheet1 row* | Use `CHI_CSU_SoC_ReqFlit_field` digest + ASSUMPTIONS §4 if conflict |
| REQFLIT_SRCID | 6 | 9:4 | |
| REQFLIT_TXNID | 10 | |
| REQFLIT_ENDIAN | 1 | |
| REQFLIT_OPCODE | 7 | |
| REQFLIT_SIZE | 3 | |
| REQFLIT_ADDR | 36 | |
| REQFLIT_NS | 1 | |
| REQFLIT_NSE | TBD | |
| REQFLIT_ORDER | 2 | |
| REQFLIT_MEMATTR | 4 | |
| REQFLIT_SNPATTR | 1 | |
| REQFLIT_LPID | 2 | |
| REQFLIT_GROUPIDEXT | 1 | |
| REQFLIT_EXCL/SNOOPME | 1 | |
| REQFLIT_EXPCOMPACK | 1 | |
| REQFLIT_TRACETAG | 1 | |
| REQFLIT_MPAM | 4 | |
| REQFLIT_PBHA | 4 | |
| REQFLIT_RSVDC_* | various | ELYDQ_VLD, FLITTYPE, HOTDATA, 128HINT, TGTL3, NCCMO |
| **REQFLIT_W (total)** | **97** | Must equal sum of packed fields |

---

## 5. Other channel field inventories

- **TXRSP / RXRSP:** full field list → SRC-04 + Sheet1 HC视角 blocks → paste tables here or reference “same as XLSX Sheet4”.
- **TXDAT / RXDAT:** SRC-06 + Sheet1 → **wide**; consider `spec.bundle` in pyCircuit for maintainability (`docs/SPEC_STRUCTURES.md`).
- **RXSNP:** SRC-05 + RSP1 4b side channel.

---

## 6. Sidebands and configuration (TBD from SRC-07)

| Port | Width | Direction | Description |
|------|-------|-----------|-------------|
| *TBD* | | | Static IDs, fuse bits, debug, power — list when DOCX extracted |

---

## 7. pyCircuit mapping notes

- For V5 top-level: wrap each bus with `cas(domain, m.input(...), cycle=0)` or `m.output(...)` once direction is known.
- Widths **615** / **584** / **97** exceed practical single literal mux in test; use **parameterized width** constants (`CSU_TXDAT_W = 615`) in `csu.py`.
- If flits are **valid/ready**, add `*_valid`, `*_ready` bits per channel; widths in this file are **payload only** unless XLSX includes handshake (verify SRC-07).

---

## 8. Revision log

| Date | Change |
|------|--------|
| 2026-04-01 | Filled CSU-centric **direction** column from `ASSUMPTIONS.md` §1; clock/reset note from SRC-07 §7 digest; linked `converted/` Markdown tables. |
| *TBD* | Added handshake ports when SRC-07 defines valid/ready |
