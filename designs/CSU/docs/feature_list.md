# CSU — itemized feature list

**Sources:** SRC-07 (primary for F-014+), SRC-02 (opcodes), SRC-08 (CHI rules), `port_list.md`.  
**Related:** `test_list.md`, `traceability.md`, `step3.md`.

Each feature must have **at least one** test in `test_list.md` before the CSU milestone is closed.

---

## Legend

| Column | Meaning |
|--------|---------|
| **ID** | Stable feature id `F-xxx`. |
| **Priority** | P0 = must have for minimal viable CSU; P1 = protocol complete; P2 = optional / performance. |
| **Spec trace** | SRC-xx or DOCX § (fill when extracted). |

---

## P0 — Reset, shell, and safe defaults

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-001 | Reset quiescence | P0 | SRC-07 `# Clock and Reset` / `## Reset domain` (digest) | `SRESET_N` / `SPORRESET_N` → TB `rst` (see `ASSUMPTIONS.md`) | All **out** ports driven to safe 0 or doc-specified idle; no internal X; no spurious transaction starts | — |
| F-014 | Post-reset first cycle | P0 | SRC-07 `# Clock and Reset` | `rst` deasserted | Documented idle state on all channels; tracker empty | F-001 |

---

## P0 — TXREQ path

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-002 | TXREQ flit assembly | P0 | SRC-01, SRC-03 | Internal request selected | `txreq` 97b matches field layout; consistent endian/packing | F-001 |
| F-003 | TXREQ opcode subset enforcement | P0 | SRC-02 → `converted/SRC-01_xlsx_CHI_CSU_SoC_Opcode.md`; allowlist in `csu.LEGAL_REQ_OPCODE_VALUES` | Opcode on TXREQ `[27:21]` | Opcodes **not** marked **Yes** under **P HC supports（950）** → **zero** `txreq` payload (Inc-0); later: stall / error per SRC-07 | F-002 |
| F-012 | TXREQ_PEND / credit back-pressure | P0 | SRC-01, SRC-08 | Credit / pending counters | No counter overflow; obey CHI-style credit return if applicable | F-002 |

---

## P0 — TXRSP / TXDAT path

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-004 | TXRSP emission | P0 | SRC-01, SRC-04, SRC-08 | Transaction state requires response | `txrsp` 30b fields (Opcode, TxnId, DBID, …) legal for current txn | F-002, tracker |
| F-006 | TXDAT emission | P0 | SRC-01, SRC-06 | Data transfer phase | `txdat` 615b beats; BE/poison/resp fields per beat rules | F-004, F-005 |

---

## P0 — RXRSP / RXDAT path

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-005 | RXRSP absorption | P0 | SRC-01, SRC-04 | Valid RXRSP beat | Transaction tracker updated; may complete or advance state | F-001 |
| F-007 | RXDAT absorption | P0 | SRC-01, SRC-06 | Valid RXDAT beat | Data buffer / line state updated; byte enables honored | F-001 |

---

## P0 — RXSNP and side channels

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-008 | RXSNP handling + RSP1 side | P0 | SRC-01, SRC-05 | Valid snoop | Internal snoop processing; **rsp1_side** 4b used per spec | F-001 |
| F-009 | RXWKUP | P1 | SRC-01 | Wakeup flit | Pipeline wake / credit / retry per DOCX | F-001 |
| F-010 | RXERR | P1 | SRC-01 | Error flit (2b) | Fault status visible or logged per DOCX | F-001 |
| F-011 | RXFILL | P1 | SRC-01 | Fill flit (3b) | Interacts with prefetch / fill buffer per DOCX | F-007 |

---

## P1 — Cross-channel ordering and stress

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-013 | Multi-channel ordering & deadlock freedom | P1 | SRC-07, SRC-08 | Concurrent traffic on RX/TX channels | No deadlock; ordering matches PoS/PoC / DOCX rules | F-002–F-008 |

---

## DOCX-derived microarchitecture (F-015+) — Master / CPU interface (SRC-07 §3)

Bulleted responsibilities are summarized from `converted/SRC-07_linxcore950_csu_design_spec.md` (“Structure” / CPU slave). Map to RTL submodules in later increments.

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-015 | MRB — txn id + request metadata | P1 | SRC-07 §3 (MRB) | Normal transaction (excl. DVM / prefetchTgt) | Stable **TxnID** / node info for CHI `txreq` | F-002 |
| F-016 | Txreq shim — ring → CHI TXREQ | P1 | SRC-07 (Txreq module) | `exp_mst_txreq` from ring | Standard **97b** `txreq` toward SoC | F-002, F-003 |
| F-017 | Txdat / Txrsp shims | P1 | SRC-07 (Txdat, Txrsp modules) | Ring egress | Standard **txdat** / **txrsp** packing | F-004, F-006 |
| F-018 | RxSnp / Rxrsp / Rxdat — CHI → ring | P1 | SRC-07 (RxSnp, Rxrsp, Rxdat) | CHI `rx*` beats | Internal `mst_exp_rx*` flits + routing | F-005, F-007, F-008 |
| F-019 | Rxrsp **retry_buf** | P1 | SRC-07 (`retry_buf`, RetryAck / PCrdGrant) | Retry protocol | Correct merged **RetryAckWithPcrdGrant** behavior | F-005 |
| F-020 | **rsp_div** + **link** (PMU / power) | P2 | SRC-07 CPU slave § | `txrsp1` from ring vs PM | Route to **link** or **int_sys** `rxrsp1` | F-004 |
| F-021 | **rxsnp_ctl** coherency gating | P1 | SRC-07 (coherency enable) | Snoop from ring | **rxsnp** to int_sys **or** loopback **txrsp** | F-008 |
| F-022 | Snoop bypass **u_rxsnp → u_txrsp** | P2 | SRC-07 (wrong master port, SnpDVMop) | Misrouted snoop | Response via **txrsp** with forwarded ids | F-008, F-004 |

---

## SRC-07 digest index → feature IDs

Authoritative headings in **`converted/SRC-07_linxcore950_csu_design_spec.md`**. **F-023–F-075** extend F-001–F-022; see **§ SRC-07 digest heading checklist (full)** for **every `#` / `##` / `###`** in the digest mapped to an **F-xxx** or **— (non-RTL)**.

| SRC-07 section (digest heading) | Feature IDs |
|----------------------------------|-------------|
| `# Overview` / `## Feature list` | F-023–F-031 |
| `# Overview` / `## Compliance` (Tab 2‑1) | F-024 (explicit trace) |
| `# Microarchitecture` / `## Cross Bar` … `## Mixed Data Path` | F-032–F-044 |
| `## Frontend Control` + four `###` subsections | **F-065–F-068** |
| `## Master Interface` (Tab 3‑11 + structure bullets) | F-045–F-048 (+ F-015–F-019 overlap) |
| `## CPU Interface` / `### CPU Slave` | F-049–F-051 (+ F-020–F-022 overlap) |
| `### Asyn_bridge CHI interface` | F-052 |
| `# Feature` (Allocation, Alias, Keep the Order) | F-053–F-055 |
| `# Flow` (Streaming, CMO, Atomic, DVM) | F-056–F-059 |
| `# Algorithm` (LFSR, Arbitration, Snapshot, `## Replacement`) | F-060–F-061 |
| `# Clock and Reset` (`## Clock domain`, `## Reset domain`) | F-001, F-014 |
| `## Reset hierarchy control and sequence` | **F-069** |
| `## PIPE Clock and Reset control` / `### PIPE clock` / `### PIPE reset` | F-062 |
| `# Terminology` | **F-071** |
| `# Interface with CPU core` | **F-072**, **F-073** |
| `# Interface with SoC` | **F-074**, **F-075** |

### Overview — Feature list & compliance (F-023–F-031)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-023 | **12M Shared L2, 24-way** capacity class | P0 | SRC-07 `## Feature list` | Config / fuse | RAM/tag geometry matches mode | — |
| F-024 | **4 pipelines** (PA\[7:6\]); **4 banks/pipe** (PA\[9:8\]); **28 BEC/pipe**; **## Compliance** Tab 2‑1 counts | P0 | SRC-07 `## Feature list`; `## Compliance` | Address + structure | Matches Tab 2‑1 (#pipe, #bank, #master, …) | F-023 |
| F-025 | **Core IF:** 2× REQ (PA\[6\]); 1× RDAT 64B; 1× TDAT 64B; **shared PFL2** | P0 | SRC-07 `## Feature list` | Core traffic | Port counts & widths per spec | — |
| F-026 | **Master IF:** 2× REQ; 2× RXDAT 32B; 2× TXDAT 32B (plus Tab 3‑1 TX/RX rows) | P0 | SRC-07 `## Feature list`; `### Topology for CSU` | SoC path | Topology matches table | F-016–F-018 |
| F-027 | **NINE** toward **L1I/D** (inclusive performance) | P1 | SRC-07 `## Feature list`; `## Allocation Policy` | Hit/miss | Policy per allocation bullets | F-025 |
| F-028 | **MPAM v1.0** | P2 | SRC-07 `## Feature list` | MPAM fields | MPAM behavior | — |
| F-029 | **Partial Good** 4M granularity (ways 0–7 / 8–15 / 16–23) | P2 | SRC-07 `## Feature list` | PF mode | Partial disable | F-023 |
| F-030 | **Way-isolation** (non-restricted) | P2 | SRC-07 `## Feature list` | Isolation | Way masking | F-023 |
| F-031 | **LTU 20-cycle** latency target | P1 | SRC-07 `## Feature list` | Timing scenario | Meets stated cycle budget where applicable | F-013 |

### Microarchitecture (F-032–F-044)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-032 | **Cross-bar** + **Tab 3‑1** topology (cluster / P-cluster / CHI rows) | P0 | SRC-07 `## Cross Bar` | Flit route | Channel fan-in/out per table | F-026 |
| F-033 | **Coherence + flavor** information storage | P1 | SRC-07 `### Coherence and Flavor Information Storage` | State lookup | Directory / CFE consistent | F-032 |
| F-034 | **Snoop filter** | P1 | SRC-07 `### Snoop Filter` | Lookup | Filter actions + capacity | F-008 |
| F-035 | **Data-RAM** | P0 | SRC-07 `### Data-ram` | RD/WR beat | Line data integrity | F-007 |
| F-036 | **X Write Buffer** | P1 | SRC-07 `### X Write Buffer` | Stores | Merge/retire rules | F-006 |
| F-037 | **Hazard checking** + **on-pipe forwarding** | P1 | SRC-07 `### Hazard Checking and Onpipe Forwarding` | Hazards | Correct bypass | F-036 |
| F-038 | **Serializing** (younger same-addr → flush to CFRQ) | P1 | SRC-07 `### Serializing` | Order needs | BRQ admission order | F-013, F-055 |
| F-039 | **Fill wakeup** pipeline (Fig 3‑43 region) | P1 | SRC-07 `### Fill Wakeup` | Fill + WKUP | Aligns with WKUP/FILL paths | F-009, F-011 |
| F-040 | **Load cancel** | P1 | SRC-07 `### Load Cancel` | Cancel | Pipeline kill / no corrupt arch state | — |
| F-065 | **Frontend Control Flow** | P1 | SRC-07 `### Frontend Control Flow` | Control sequencing | Legal frontend sequencing | F-001 |
| F-066 | **Resource Management** (frontend) | P1 | SRC-07 `### Resource Management` | Resource pressure | Credits/queues per spec | F-065 |
| F-067 | **Sleep and Wakeup Control** | P1 | SRC-07 `### Sleep and Wakeup Control` | Power / wake | Sleep entry/exit safe | F-065, F-009 |
| F-068 | **Flush Control** | P1 | SRC-07 `### Flush Control` | Flush events | Deterministic pipeline flush | F-065 |
| F-042 | **BRQ FSM** | P0 | SRC-07 `### BRQ FSM` | Request queue | Legal FSM; no illegal combine | F-038 |
| F-043 | **BRAM write / read arbitration** | P1 | SRC-07 `### Bram Write Arbitration`; `### Bram Read Arbitration` | Multi-port RAM | Fairness / no starvation | F-042 |
| F-044 | **Mixed data path** | P1 | SRC-07 `## Mixed Data Path` | 32B/64B paths | Correct width handling | F-026, F-025 |

### Master interface — Tab 3‑11 & extras (F-045–F-048)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-045 | **Tab 3‑11** CHI capabilities (Atomic, Stash, DMT, DCT, Poison, CSP conditional, …) | P1 | SRC-07 `### Feature List` (Master) | Capability / fuse | Matches interconnect contract | F-003, SRC-08 |
| F-046 | Master **Link** — activate/deactivate CHI to interconnect | P1 | SRC-07 `### Sturcture` (Link module) | Link state | No tx when inactive | F-017 |
| F-047 | Master **PMU** — master access event count | P2 | SRC-07 `### Sturcture` (PMU module) | Events | Count accuracy | — |
| F-048 | **mst_exp_rxrsp** routing: even/odd sub-node; **RespSepData** / **AllDatSent** / **REGACTION** | P1 | SRC-07 `### Sturcture` (mst_exp_rxrsp bullets) | Rsp type | Correct egress interface | F-018, F-005 |

### CPU slave extensions (F-049–F-051)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-049 | **txrsp0_arb** — arbitrate int_sys **txrsp** vs ring **rxsnp**; credit **pushback FIFO** | P1 | SRC-07 `### CPU Slave` (txrsp0_arb) | Credit pressure | No beat drop | F-021, F-012 |
| F-050 | **sysco_cnt** — identify/count SoC snoop-related **txrsp**/**txdat** | P1 | SRC-07 `### CPU Slave` (sysco_cnt) | SysCo | Correct statistics | F-021 |
| F-051 | **sysco_ctl** — enable/disable **ring ↔ int_sys** coherency | P1 | SRC-07 `### CPU Slave` (sysco_ctl) | Config | Snoop path matches mode | F-021 |

### Async bridge (F-052)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-052 | **Async CHI** FIFO depths: **SNP 3**, **DAT 6**, **RSP 6** | P1 | SRC-07 `### Asyn_bridge CHI interface` | CDC | No overflow under rated load | F-032 |

### Feature chapter — allocation, alias, order (F-053–F-055)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-053 | **Allocation policy** detail (load/store/prefetch NINE rules) | P1 | SRC-07 `## Allocation Policy` | Req class | Allocate/deallocate per bullets | F-027 |
| F-054 | **Alias** (VIPT L1D, self-snoop, streaming, CMO) | P1 | SRC-07 `## Alias` | Alias case | No stale L1 use | F-008 |
| F-055 | **Keep the order** — `### The Order in Xbar` + `### The Order in Home` | P1 | SRC-07 `## Keep the Order` | Same addr / LPID | Order preserved | F-013, F-038 |

### Flow chapter (F-056–F-059)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-056 | **Streaming** write flow (WRNT, color, DBID, WRDATA, Comp) | P1 | SRC-07 `## Streaming` | Streaming store | BIU counter + Comp color | F-054 |
| F-057 | **CMO** flows | P1 | SRC-07 `## CMO` | CMO request | Correct comp / snoop sequence | — |
| F-058 | **Atomic** flow | P2 | SRC-07 `## Atomic` | Atomic op | HLC atomic rules | F-045 |
| F-059 | **DVM** flow | P2 | SRC-07 `## DVM` | DVM op | Core-visible DVM semantics | — |

### Algorithm & replacement (F-060–F-061)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-060 | **LFSR** (`## LFSR`, `### LFSR Overview`, `### LFSR`) + **Arbitration** (`## Arbitration`, `### Arbitration solution`, `### LFSR Generation`) + **Snapshot arbitration** (`## Snapshot Arbitration`) | P2 | SRC-07 `# Algorithm` … | Arb requests | Fair / spec-defined grant | — |
| F-061 | **RRIP** replacement | P1 | SRC-07 `## Replacement` / `### RRIP` | Eviction | Victim line policy | F-023 |

### PIPE clock/reset & reset hierarchy (F-062, F-069)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-062 | **PIPE** clock + **PIPE** reset (`### PIPE clock`, `### PIPE reset`) | P1 | SRC-07 `## PIPE Clock and Reset control` | PIPE domain | Correct enable/reset sequencing | F-001 |
| F-069 | **Reset hierarchy control and sequence** | P0 | SRC-07 `## Reset hierarchy control and sequence` | Hierarchical reset | Order / duration meets spec (with F-001) | F-001 |

### Terminology (F-071)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-071 | **Terminology** applied consistently (RTL comments, TB, docs) | P3 | SRC-07 `# Terminology` | Naming review | Same terms as spec definitions | — |

### Interface with CPU core (F-072, F-073)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-072 | **Transaction Type** (CPU core interface chapter) | P1 | SRC-07 `# Interface with CPU core` → `## Transaction Type` | Core-side txn classes | Encoding matches § | F-025 |
| F-073 | **Protocol Compliance** — incl. `### WriteEvictOrEvict`, `### CMO early comp`, `### DVM feild` | P1 | SRC-07 `# Interface with CPU core` → `## Protocol Compliance` + subsections | Core CHI edge cases | Behaviors per § | F-072, F-057, F-059 |

### Interface with SoC (F-074, F-075)

| ID | Feature | Priority | Spec trace | Trigger / condition | Observable effect | Depends on |
|----|---------|----------|------------|----------------------|-------------------|------------|
| F-074 | **Transaction Type** (SoC interface chapter) | P1 | SRC-07 `# Interface with SoC` → `## Transaction Type` | SoC-side txn classes | Encoding matches § | F-026 |
| F-075 | **Protocol Compliance** (SoC interface chapter) | P1 | SRC-07 `# Interface with SoC` → `## Protocol Compliance` | SoC CHI | Behaviors per § | F-074, F-045 |

### Template for additional DOCX requirements

| ID | Feature | Priority | Spec trace | Trigger | Observable effect | Depends on |
|----|---------|----------|------------|---------|-------------------|------------|
| F-0xx | *name* | P0/P1/P2 | SRC-07 heading in digest | *condition* | *ports / state* | *ids* |

---

## SRC-07 digest heading checklist (full)

Every **`#` / `##` / `###`** title line in **`converted/SRC-07_linxcore950_csu_design_spec.md`** maps below. **—** = document structure or meta (no RTL feature id).

| Digest heading | Map |
|----------------|-----|
| `# About This Document` | — |
| `## Purpose` | — |
| `## Intended Audience` | — |
| `# Contents` | — |
| `# Figures` | — |
| `# Tables` | — |
| `# Terminology` | **F-071** |
| `# Overview` | (container) |
| `## Feature list` | **F-023–F-031** |
| `## Compliance` | **F-024** |
| `# Microarchitecture` | (container) |
| `## Cross Bar` | **F-032** |
| `### Topology for CSU` | **F-032**, **F-026** |
| `## Pipeline` | (container) |
| `### Coherence and Flavor Information Storage` | **F-033** |
| `### Snoop Filter` | **F-034** |
| `### Data-ram` | **F-035** |
| `### X Write Buffer` | **F-036** |
| `### Hazard Checking and Onpipe Forwarding` | **F-037** |
| `### Serializing` | **F-038** |
| `### Fill Wakeup` | **F-039** |
| `### Load Cancel` | **F-040** |
| `## Frontend Control` | (container) |
| `### Frontend Control Flow` | **F-065** |
| `### Resource Management` | **F-066** |
| `### Sleep and Wakeup Control` | **F-067** |
| `### Flush Control` | **F-068** |
| `## Backend Control` | (container) |
| `### BRQ FSM` | **F-042** |
| `### Bram Write Arbitration` | **F-043** |
| `### Bram Read Arbitration` | **F-043** |
| `## Mixed Data Path` | **F-044** |
| `## Master Interface` | (container) |
| `### Feature List` (Master) | **F-045** |
| `### Sturcture` | **F-046–F-048**, **F-015–F-018** |
| `### MRB` | **F-015** |
| `## CPU Interface` | (container) |
| `### CPU Slave` | **F-020–F-022**, **F-049–F-051** |
| `### Asyn_bridge CHI interface` | **F-052** |
| `# Feature` | (container) |
| `## Allocation Policy` | **F-053**, **F-027** |
| `## Alias` | **F-054** |
| `## Keep the Order` | **F-055** |
| `### The Order in Xbar` | **F-055** |
| `### The Order in Home` | **F-055** |
| `# Flow` | (container) |
| `## Streaming` | **F-056** |
| `## CMO` | **F-057** |
| `## Atomic` | **F-058** |
| `## DVM` | **F-059** |
| `# Algorithm` | (container) |
| `## LFSR` | **F-060** |
| `### LFSR Overview` | **F-060** |
| `### LFSR` | **F-060** |
| `## Arbitration` | **F-060** |
| `### Arbitration solution` | **F-060** |
| `### LFSR Generation` | **F-060** |
| `## Snapshot Arbitration` | **F-060** |
| `## Replacement` | **F-061** |
| `### RRIP` | **F-061** |
| `# Clock and Reset` | (container) |
| `## Clock domain` | **F-001**, **F-014** |
| `## Reset domain` | **F-001**, **F-014** |
| `## Reset hierarchy control and sequence` | **F-069** |
| `## PIPE Clock and Reset control` | **F-062** |
| `### PIPE clock` | **F-062** |
| `### PIPE reset` | **F-062** |
| `# Interface with CPU core` | **F-072**, **F-073** |
| `## Transaction Type` | **F-072** |
| `## Protocol Compliance` | **F-073** |
| `### WriteEvictOrEvict` | **F-073** |
| `### CMO early comp` | **F-073** |
| `### DVM feild` | **F-073** |
| `# Interface with SoC` | **F-074**, **F-075** |
| `## Transaction Type` | **F-074** |
| `## Protocol Compliance` | **F-075** |

*If pandoc adds new headings in a future export, extend this table and assign **F-076+** or **G-xx**.*

---

## Feature → test mapping (summary)

| Feature IDs | Primary tests (see `test_list.md`) |
|-------------|-------------------------------------|
| F-001, F-014 | T-001, T-014 |
| F-002 | T-002 |
| F-003 | T-003 |
| F-004, F-006 | T-004, T-011 |
| F-005 | T-004 |
| F-007 | T-005 |
| F-008 | T-006 |
| F-009 | T-007 |
| F-010 | T-008 |
| F-011 | T-009 |
| F-012, F-013 | T-010, SYS-04, SYS-05 |
| F-015–F-022 | TBD (master/CPU slave partition tests) |
| F-023–F-075 | TBD — add directed/SYS tests per `test_list.md` as RTL matures (`step8.md` R5) |
