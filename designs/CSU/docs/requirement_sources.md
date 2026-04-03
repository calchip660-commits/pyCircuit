# CSU — requirement sources (Step 2 detail)

This file is the **detailed** deliverable for **Step 2** of `docs/pycircuit_implementation_method.md`, applied to `designs/CSU`.

---

## 1. Purpose

Enumerate **every** normative artifact for CSU, what to extract from it, and how to record traceability (SRC IDs) in `traceability.md` and `ASSUMPTIONS.md`.

---

## 2. Artifact inventory

| SRC ID | Path (under `designs/CSU/docs/`) | Format | Markdown digest (`converted/`) | Primary extraction |
|--------|----------------------------------|--------|-------------------------------|---------------------|
| **SRC-01** | `CSU 接口Protocol_辅助设计输入.xlsx` | XLSX | `SRC-01_xlsx_CHI_Core_CSU_ALL.md` (+ per-sheet field/opcode files) | Sheet1: per-channel flit packing, MSB/LSB, **REQFLIT_W**, **RSPFLIT_W**, **DATFLIT_W**, perspectives (CSU视角 / HC视角). |
| **SRC-02** | Same | XLSX | `SRC-01_xlsx_CHI_CSU_SoC_Opcode.md` | `REQ_OPCODE[6:0]` / `RESP_OPCODE[4:0]` ↔ transaction name ↔ “P HC supports（950）” / “supports(TX)”. |
| **SRC-03** | Same | XLSX | `SRC-01_xlsx_CHI_CSU_SoC_ReqFlit_field.md` | REQFLIT field table (QoS, TgtID, SrcID, …) with **Field width**, **END BIT**, **START BIT**. |
| **SRC-04** | Same | XLSX | `SRC-01_xlsx_CHI_CSU_SoC_RspFlit_field.md` | TX/RX RSP flit fields. |
| **SRC-05** | Same | XLSX | `SRC-01_xlsx_CHI_CSU_SoC_SnpFlit_field.md` | SNPFLIT fields. |
| **SRC-06** | Same | XLSX | `SRC-01_xlsx_CHI_CSU_SoC_DataFlit_field.md` | DAT flit fields. |
| **SRC-07** | `LinxCore950 CSU Design Specification-AI辅助设计输入.docx` | DOCX | `SRC-07_linxcore950_csu_design_spec.md` + `SRC-07_media/` | Functional blocks, FSMs, performance targets, reset sequences, **SoC boundary** narrative, sidebands not in XLSX. |
| **SRC-08** | `IHI0050H_amba_chi_architecture_spec.pdf` | PDF | `SRC-08_chi_architecture_spec_extract.md` *(pages 1–150 text only)* | CHI channel definitions, ordering, PoS/PoC, credit rules — **full PDF remains normative for figures**. |

**Regenerate digests:** `python3 designs/CSU/scripts/export_specs_to_md.py` (repo root).

---

## 3. Extraction checklist (per SRC)

### SRC-01 (Sheet1)

- [ ] List every **channel header** row (TXREQ, TXREQ_PEND, TXRSP, RXRSP, TXDAT, RXDAT, RXWKUP, RXERR, RXFILL, RXSNP).
- [ ] For each channel, copy **aggregated width** row (`*_W`).
- [ ] Note **CSU视角** vs **HC视角** for each table block (affects `port_list.md` direction column after DOCX confirms).
- [ ] Copy any **TBD** or empty width cells into `ASSUMPTIONS.md`.

### SRC-02 (Sheet2)

- [ ] Build opcode allowlist: REQ opcodes CSU may emit; RESP opcodes CSU must parse.
- [ ] Mark **No** / unsupported rows as **illegal** or **stall** behavior per DOCX.
- [ ] Link rows to **feature_list.md** (F-003 and related).

### SRC-03 — SRC-06

- [ ] For each field: name, width, bit range → append to `port_list.md` **field inventory** sections (or sub-tables).
- [ ] Verify **bit ranges do not overlap** within a flit; verify sum matches `*_W` from Sheet1.

### SRC-07 (DOCX)

- [ ] Table of contents → map sections to **feature IDs** (F-014…).
- [ ] Extract **reset**: synchronous/asynchronous, minimum pulse, register defaults.
- [ ] Extract **clocking**: single vs multiple clocks; CDC boundaries.
- [ ] Extract **ordering rules** between channels (e.g. RSP before DAT).
- [ ] Update `port_list.md` **Direction** column from interconnect diagrams.

### SRC-08 (PDF)

- [ ] For each CSU-visible channel, cross-check **field semantics** (e.g. TxnId, DBID) against CHI.
- [ ] Document any **LinxCore950** narrowing vs full CHI in `ASSUMPTIONS.md`.

---

## 4. Conflict resolution

When SRC-07 contradicts SRC-01:

1. Record both in `ASSUMPTIONS.md` with **section/sheet references**.
2. Default to **no X propagation** on datapath and **explicit stall** on protocol violation until human sign-off.

---

## 5. Deliverable linkage

| Output | Where recorded |
|--------|----------------|
| Aggregated bus widths | `port_list.md` |
| Opcode / mode rules | `feature_list.md` (extend F-003, add F-014+) |
| Field-level maps | `port_list.md` § Field inventories |
| Trace rows SRC → F → T | `traceability.md` |
