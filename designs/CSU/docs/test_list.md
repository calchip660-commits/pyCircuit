# CSU — itemized and system test plan

**Sources:** `feature_list.md`, `port_list.md`, `docs/TESTBENCH.md`.  
**Related:** `traceability.md`, `step8.md`, `step10.md`.

Every **port** (or agreed port group) and every **feature** must appear in at least one test below.

---

## 1. Test environment defaults

| Item | Value |
|------|--------|
| DUT | `designs/CSU/csu.py` (when exists) |
| TB | `designs/CSU/tb_csu.py` |
| Python path | `PYTHONPATH=<repo>/compiler/frontend` |
| Compile | `compile_cycle_aware(build_csu, eager=True, name="csu")` until JIT needed |
| Log | MLIR emit + optional C++/Verilator per `docs/QUICKSTART.md` |

---

## 2. Directed tests (T-xxx)

### T-001 — Reset and idle outputs

| Field | Content |
|-------|---------|
| **Type** | reset / smoke |
| **Features** | F-001 |
| **Ports** | All outputs; `rst`, `clk` |
| **Stimulus** | Hold `rst` in asserted state for N cycles (N per SRC-07); then deassert. |
| **Expect** | While reset: each output equals **safe idle** value from `port_list.md` / DOCX; no X. After deassert: idle state per F-014. |
| **Fail if** | Any output toggles illegally during reset; unknown on outputs. |

### T-002 — TXREQ field sanity

| Field | Content |
|-------|---------|
| **Type** | directed |
| **Features** | F-002 |
| **Ports** | `txreq` (97b) |
| **Stimulus** | Force internal mux OR drive minimal scenario so one known REQ appears. |
| **Expect** | Bit slices for QoS, Opcode, Addr match golden (from SRC-03 for one test vector). |
| **Fail if** | Width ≠ 97 or field misaligned. |

### T-003 — Unsupported opcode handling

| Field | Content |
|-------|---------|
| **Type** | directed / negative |
| **Features** | F-003 |
| **Ports** | `txreq`, possibly `txrsp` or stall side |
| **Stimulus** | Inject opcode marked **No** in SRC-02. |
| **Expect** | Stall or error path per DOCX (document which in `ASSUMPTIONS.md`). |
| **Fail if** | Silent acceptance or deadlock without spec allowance. |

### T-004 — RXRSP-driven state + TX response path

| Field | Content |
|-------|---------|
| **Type** | directed |
| **Features** | F-005, F-004, F-006 (partial) |
| **Ports** | `rxrsp`, `txrsp`, optionally `txdat` |
| **Stimulus** | Sequence of RXRSP beats matching one simple transaction (e.g. Comp). |
| **Expect** | Tracker updates; `txrsp`/`txdat` appear when spec says they should. |
| **Fail if** | Wrong TxnId/DBID association. |

### T-005 — RXDAT beat sequence

| Field | Content |
|-------|---------|
| **Type** | directed |
| **Features** | F-007 |
| **Ports** | `rxdat` |
| **Stimulus** | 1–K beats with known BE/data. |
| **Expect** | Internal buffer / line model matches golden. |
| **Fail if** | BE or CCID mishandled. |

### T-006 — RXSNP + RSP1 side

| Field | Content |
|-------|---------|
| **Type** | directed |
| **Features** | F-008 |
| **Ports** | `rxsnp`, `rsp1_side` |
| **Stimulus** | One snoop from SRC-05 example row (when available). |
| **Expect** | Documented internal response or forwarding behavior. |
| **Fail if** | RSP1 ignored when spec requires it. |

### T-007 — RXWKUP

| Field | Content |
|-------|---------|
| **Type** | directed |
| **Features** | F-009 |
| **Ports** | `rxwkup` |
| **Stimulus** | Legal WKUP flit patterns from SRC-01. |
| **Expect** | Defined wake / credit effect. |
| **Fail if** | No observable change when spec requires it. |

### T-008 — RXERR

| Field | Content |
|-------|---------|
| **Type** | corner |
| **Features** | F-010 |
| **Ports** | `rxerr` |
| **Stimulus** | Toggle ERR_FLIT_INDICATE / BITERR independently. |
| **Expect** | Fault handling per DOCX. |
| **Fail if** | Ignored errors. |

### T-009 — RXFILL

| Field | Content |
|-------|---------|
| **Type** | directed |
| **Features** | F-011 |
| **Ports** | `rxfill` |
| **Stimulus** | Legal fill encodings. |
| **Expect** | Buffer / prefetch interaction. |
| **Fail if** | Violates SRC-07 fill rules. |

### T-010 — Multi-channel stress

| Field | Content |
|-------|---------|
| **Type** | stress |
| **Features** | F-012, F-013 |
| **Ports** | All major flit buses |
| **Stimulus** | Back-to-back overlapping transactions (bounded). |
| **Expect** | Progress / no deadlock; credits sane. |
| **Fail if** | Hang or credit underflow/overflow. |

### T-011 — TXDAT wide flit integrity

| Field | Content |
|-------|---------|
| **Type** | directed |
| **Features** | F-006 |
| **Ports** | `txdat` (615b) |
| **Stimulus** | Single beat with known data + poison/BE if applicable. |
| **Expect** | Bit-exact match at output slice. |
| **Fail if** | Truncation or misaligned fields. |

### T-012 — TXREQ_PEND (2b side-band)

| Field | Content |
|-------|---------|
| **Type** | directed |
| **Features** | F-012 |
| **Ports** | `txreq_pend` |
| **Stimulus** | Exercise both pending states per SRC-07. |
| **Expect** | Consistent with TXREQ gating. |
| **Fail if** | Pend counter mismatch. |

### T-013 — Clock/reset polarity (when defined)

| Field | Content |
|-------|---------|
| **Type** | reset |
| **Features** | F-001 |
| **Ports** | `clk`, `rst` |
| **Stimulus** | Verify active level per SRC-07. |
| **Expect** | Same as T-001 under correct polarity. |
| **Fail if** | Wrong polarity assumption. |

### T-014 — Post-reset first active cycle

| Field | Content |
|-------|---------|
| **Type** | smoke |
| **Features** | F-014 |
| **Ports** | all |
| **Stimulus** | First cycle after reset release. |
| **Expect** | Documented idle / wait-for-credit state. |
| **Fail if** | Illegal first transaction. |

---

## 3. System scenarios (SYS-xxx)

### SYS-01 — Full read flow

| Field | Content |
|-------|---------|
| **Features** | F-002, F-004, F-005, F-006, F-007 |
| **Narrative** | Issue read-like TXREQ → accept RXRSP progression → RXDAT beats → completion on TX channels. |
| **Pass** | End state idle; scoreboard matches golden transaction log. |

### SYS-02 — Snoop interleaved with data

| Field | Content |
|-------|---------|
| **Features** | F-004–F-008 |
| **Narrative** | Overlap snoop handling with ongoing read/write data beats per ordering rules. |
| **Pass** | Ordering matches SRC-07 + SRC-08; no protocol violation. |

### SYS-03 — Error and recovery

| Field | Content |
|-------|---------|
| **Features** | F-010, F-001 |
| **Narrative** | Inject `rxerr`; reset or soft recovery per spec. |
| **Pass** | Defined recovery; no stuck fault. |

### SYS-04 — Wakeup + credit pressure

| Field | Content |
|-------|---------|
| **Features** | F-009, F-012 |
| **Narrative** | Hold TX path until credits exhausted; WKUP releases or returns credits. |
| **Pass** | Forward progress within bounded cycles. |

### SYS-05 — Pseudo-random multi-txn (optional)

| Field | Content |
|-------|---------|
| **Features** | F-013 |
| **Narrative** | Constrained random opcodes (from allowlist) and interleavings. |
| **Pass** | Invariants: no deadlock, credit ≥ 0, legal flits only. |

---

## 4. Coverage checklist (maintenance)

- [ ] Each row in `port_list.md` §3 appears in ≥1 test.  
- [ ] Each `F-xxx` in `feature_list.md` maps to ≥1 test ID.  
- [ ] SYS scenarios scheduled in CI or nightly per project policy.
