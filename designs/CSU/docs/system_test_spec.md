# CSU — system test specification (Step 10 detail)

**Parent:** `step10.md`  
**Related:** `test_list.md` §3, `traceability.md` sign-off.

---

## 1. Objectives

- Validate **end-to-end** CSU behavior under **combined** stimulus.  
- Confirm **no uncovered** port or feature remains relative to `traceability.md`.  
- Provide **sign-off evidence** (logs, waveforms policy per team).

---

## 2. Scenario SYS-01 — Full read-style flow

| Step | Action | Watch |
|------|--------|-------|
| 1 | Apply reset; wait idle | All outputs idle |
| 2 | Start transaction: assert conditions for TXREQ on DUT internal model | `txreq` opcode/size/addr |
| 3 | Drive RXRSP sequence per SRC-02/SRC-08 | Tracker accepts Comp / separate data rules |
| 4 | Drive RXDAT beats | Data RAM / buffer golden |
| 5 | Observe TX completion channels if applicable | `txrsp`/`txdat` |
| 6 | Drain to idle | Credits returned |

**Pass criteria:** Scoreboard equality on all beats; no protocol violation flags.

---

## 3. Scenario SYS-02 — Snoop + concurrent data

| Step | Action | Watch |
|------|--------|-------|
| 1 | Start long RXDAT transfer | F-007 active |
| 2 | Inject RXSNP mid-transfer | F-008 |
| 3 | Verify ordering: per SRC-07 (e.g. snoop response before line invalidation) | `txrsp`/`txdat`/`rxsnp` |

**Pass criteria:** No deadlock; state matches golden interleaving log.

---

## 4. Scenario SYS-03 — Error and recovery

| Step | Action | Watch |
|------|--------|-------|
| 1 | Normal transaction start | baseline |
| 2 | Assert `rxerr` pattern | F-010 |
| 3 | Apply recovery: soft clear or full reset per DOCX | F-001 |

**Pass criteria:** DUT reaches defined safe state; no lock-up.

---

## 5. Scenario SYS-04 — Wakeup + credit pressure

| Step | Action | Watch |
|------|--------|-------|
| 1 | Exhaust TX credits (if modelled) | F-012 |
| 2 | Send `rxwkup` to release | F-009 |
| 3 | Resume TXREQ flow | progress |

**Pass criteria:** Bounded stall cycles; credits non-negative.

---

## 6. Scenario SYS-05 — Stress / random (optional)

| Item | Description |
|------|-------------|
| Tool | Python constrained random or SV testbench if cosim |
| Constraints | Opcodes from SRC-02 allowlist only |
| Duration | N thousand cycles (project-defined) |
| Invariants | No deadlock; legal flits; credit ≥ 0 |

---

## 7. Final checklist (copy to release notes)

- [ ] SYS-01 … SYS-04 executed green  
- [ ] `traceability.md` gap list empty or waived  
- [ ] `test_list.md` every T-xxx run in regression  
- [ ] Performance / area goals from SRC-07 noted (pass/fail)
