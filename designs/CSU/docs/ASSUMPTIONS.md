# CSU — assumptions and open items

**Purpose:** Track items not fully closed in binary specs, or inferred pending sign-off.

**Converted specs:** `converted/README.md` (SRC-01 / SRC-07 / SRC-08 Markdown digests).

---

## 1. Port directions (CSU-centric)

Directions below follow CHI-style **TX/RX naming** on the CSU boundary together with SRC-07 text (e.g. CSU driving **txreq** toward **int_sys** / SoC, receiving **rxrsp** / **rxdat**). If SRC-07 interconnect tables contradict this, update `port_list.md` and record the delta here.

| Bus | Direction | Rationale (short) |
|-----|-----------|-------------------|
| `txreq` | **out** | Request channel driven by CSU toward downstream interconnect (SoC / SN). |
| `txreq_pend` | **in** | Pending / credit information toward CSU as requester (CHI-style companion). |
| `txrsp` | **out** | Response flits from CSU toward upstream (cores / ring). |
| `rxrsp` | **in** | Response flits received from downstream. |
| `txdat` | **out** | Data beats driven by CSU. |
| `rxdat` | **in** | Data beats received by CSU. |
| `rxwkup` | **in** | Wakeup sideband into CSU. |
| `rxerr` | **in** | Error indication into CSU. |
| `rxfill` | **in** | Fill / prefetch sideband into CSU. |
| `rxsnp` | **in** | Snoop into CSU. |
| `rsp1_side` | **in** | 4b companion to snoop path (SRC-01). |

**Handshake:** Valid/ready not modeled in SRC-01 aggregated widths; add when SRC-07 + TB define them.

---

## 2. Reset / clock (from SRC-07 digest)

SRC-07 §7 documents **SRESET_N** (warm) and **SPORRESET_N** (cold), active-low, **≥16 SCLK cycles** minimum assertion, **SCLK** domain. Top-level `csu.py` stub still uses a single `rst` from `compile_cycle_aware` until TB wires SoC reset hierarchy.

---

## 3. REQ opcode policy

**F-003:** Illegal TXREQ opcodes are those **not** listed as **Yes** under **P HC supports（950）** in SRC-02 (`converted/SRC-01_xlsx_CHI_CSU_SoC_Opcode.md`). Implemented allowlist: `LEGAL_REQ_OPCODE_VALUES` in `csu.py` (must stay in sync with spreadsheet exports).

**Note:** Core↔CSU vs CSU↔SoC opcode views may differ; this allowlist tracks the **SoC opcode** sheet naming — validate against product mode before tape-out.

---

## 4. XLSX field tables

Some rows in `CHI CSU_SoC_ReqFlit_field` show inconsistent END/START bits (likely spreadsheet errors). **Packed widths** and **CSU视角** bit maps in `CHI_Core_CSU_ALL` take precedence for RTL packing until manually corrected.
