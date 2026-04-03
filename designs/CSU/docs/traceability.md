# CSU — traceability matrices (Step 7)

**Purpose:** Prove every **port**, **feature**, and **test** is connected. Update this file whenever F-xxx, T-xxx, or ports change.

**Related:** `port_list.md`, `feature_list.md`, `feature_implementation_status.md`, `test_list.md`, `step7.md`.

---

## 1. Port → implementation region → features

| Port / bus | Width | Primary pseudocode region (`step6.md`) | Python symbol (TBD) | Feature IDs |
|------------|-------|----------------------------------------|---------------------|-------------|
| `clk` | 1 | implicit | `m.clock` / domain | — |
| `rst` | 1 | Cycle 0+ | `m.reset` | F-001, F-014 |
| `rxrsp` | 42 | Cycle 0 decode; Cycle 1 advance | `rxrsp` | F-005 |
| `rxdat` | 584 | Cycle 0 decode; Cycle 1 advance | `rxdat` | F-007 |
| `rxsnp` | 82 | Cycle 0 decode; Cycle 1 advance | `rxsnp` | F-008 |
| `rsp1_side` | 4 | with `rxsnp` | `rsp1` | F-008 |
| `rxwkup` | 18 | Cycle 0–1 | `rxwkup` | F-009 |
| `rxerr` | 2 | Cycle 0–1 | `rxerr` | F-010 |
| `rxfill` | 3 | Cycle 0–1 | `rxfill` | F-011 |
| `txreq` | 97 | Cycle 2–3 | `txreq_q` | F-002, F-003, F-012 |
| `txreq_pend` | 2 | Cycle 2–3 | `txreq_pend` | F-012 |
| `txrsp` | 30 | Cycle 2–3 | `txrsp_q` | F-004 |
| `txdat` | 615 | Cycle 2–3 | `txdat_q` | F-006 |

**Directions:** see `port_list.md` §3 and `ASSUMPTIONS.md` §1 (CSU-centric, inferred from SRC-07 narrative + CHI naming).

---

## 2. Feature → pseudocode / function → test

| Feature | `function_list.md` | `step4.md` / `step6.md` | Test IDs |
|---------|-------------------|-------------------------|----------|
| F-001 | `update_reset_and_error_state` | `csu_main_cycle` entry | T-001, T-013 |
| F-002 | `build_txreq`, `pack_all_flits` | Cycle 2 | T-002 |
| F-003 | `build_txreq`, `_req_opcode_supported` (`csu.py`) | Cycle 1–2 | T-003 |
| F-004 | `build_txrsp` | Cycle 2 | T-004, T-011 |
| F-005 | `absorb_rxrsp`, `advance_transactions` | Cycle 1 | T-004 |
| F-006 | `build_txdat` | Cycle 2 | T-004, T-011 |
| F-007 | `absorb_rxdat` | Cycle 1 | T-005 |
| F-008 | `handle_snoop` | Cycle 1 | T-006 |
| F-009 | `handle_rxwkup` | Cycle 1 | T-007 |
| F-010 | `update_reset_and_error_state` | Cycle 0–1 | T-008 |
| F-011 | `handle_rxfill` | Cycle 1 | T-009 |
| F-012 | `update_credit_and_pending_counters` | Cycle 1–2 | T-010, T-012 |
| F-013 | `advance_transactions` | Cycle 1 | T-010, SYS-05 |
| F-014 | reset FSM | Cycle 0 | T-014 |
| F-015 | `mst_mrb_track_request` | future partition | TBD |
| F-016 | `mst_convert_txreq` | future partition | TBD |
| F-017 | `mst_convert_txdat`, `mst_convert_txrsp` | future partition | TBD |
| F-018 | `mst_convert_rxsnp`, `mst_convert_rxrsp`, `mst_convert_rxdat` | future partition | TBD |
| F-019 | `mst_convert_rxrsp` (retry_buf) | future partition | TBD |
| F-020 | `cpu_rsp_div_route`, `cpu_link_pm_handshake` | future partition | TBD |
| F-021 | `cpu_rxsnp_distribute` | future partition | TBD |
| F-022 | `cpu_snoop_bypass_to_txrsp` | future partition | TBD |
| F-023–F-031 | Overview cache/IF/LTU — `csu_main_cycle` + config | `step4.md` / future § | TBD |
| F-032–F-044 | Microarchitecture blocks — see `function_list.md` | future partitions | TBD |
| F-045–F-048 | Master Tab 3‑11 + Link/PMU/rxrsp routing | `mst_*` shims | TBD |
| F-049–F-051 | CPU slave txrsp0_arb / sysco_* | `cpu_*` shims | TBD |
| F-052 | Async FIFO depths | CDC wrapper | TBD |
| F-053–F-055 | Allocation / alias / order | `advance_transactions`, `handle_snoop` | TBD |
| F-056–F-059 | Streaming / CMO / Atomic / DVM flows | flow helpers | TBD |
| F-060–F-061 | LFSR / arb / RRIP | misc ctrl | TBD |
| F-062 | PIPE clk/rst | reset/clock tree | TBD |
| F-065–F-068 | Frontend Control subsections | frontend ctrl | TBD |
| F-069 | Reset hierarchy sequence | reset tree | TBD |
| F-071 | Terminology consistency | docs/TB/RTL naming | TBD |
| F-072–F-073 | CPU IF transaction types + protocol § | port + protocol checkers | TBD |
| F-074–F-075 | SoC IF transaction types + protocol § | port + protocol checkers | TBD |

*Full definitions: `feature_list.md` § “SRC-07 digest index”, **§ SRC-07 digest heading checklist (full)**, and tables **F-023–F-075**.*

---

## 3. Test → ports → features

| Test ID | Ports touched | Features |
|---------|---------------|----------|
| T-001 | all out, rst | F-001 |
| T-002 | txreq | F-002 |
| T-003 | txreq, … | F-003 |
| T-004 | rxrsp, txrsp, txdat | F-004–F-006 |
| T-005 | rxdat | F-007 |
| T-006 | rxsnp, rsp1_side | F-008 |
| T-007 | rxwkup | F-009 |
| T-008 | rxerr | F-010 |
| T-009 | rxfill | F-011 |
| T-010 | all | F-012, F-013 |
| T-011 | txdat | F-006 |
| T-012 | txreq_pend | F-012 |
| T-013 | clk, rst | F-001 |
| T-014 | all | F-014 |

---

## 4. Gap and TBD register

| ID | Description | Owner | Target resolution |
|----|-------------|-------|-------------------|
| G-01 | Port direction for each CHI bus | TBD | SRC-07 diagram |
| G-02 | Valid/ready vs L-credit mapping | TBD | SRC-07 + SRC-08 |
| G-03 | F-015+ from DOCX not yet listed | TBD | SRC-07 pass |
| G-04 | Multi-clock domains | TBD | SRC-07 |

**Status:** Open until all rows removed or accepted with sign-off in `ASSUMPTIONS.md`.

---

## 5. Sign-off (Step 10)

| Role | Name | Date | Notes |
|------|------|------|-------|
| Arch | | | |
| DV | | | |

When signed, mark **Gap list** as closed or waived with document IDs.
