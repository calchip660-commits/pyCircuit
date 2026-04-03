# CSU — optional finer workflow substeps

**Purpose:** The canonical methodology remains **Step 1–10** (`step1.md` … `step10.md`, `docs/pycircuit_implementation_method.md`). When a step is too large for one pass, **split it here** into **substeps** (e.g. **3a / 3b**). Each substep should end with a **small, reviewable diff** and an update to **`IMPLEMENTATION_LOG.md`**.

**Verification:** `run_csu_verification.py` still gates **full** Step 1–10 until all parent-step deliverables exist; substeps are **process discipline**, not separate automated markers (unless you add pytest marks later).

---

## When to subdivide

| Situation | Suggested split |
|-----------|-----------------|
| **F-001–F-075** overwhelming | Step **3b–3e** below by feature band |
| **SRC-07** too long for one read | Step **2a–2d** by artifact or chapter |
| **function_list** + **step4** pseudocode huge | Step **4a–4c** by path (core vs master/CPU vs flows) |
| **cycle_budget** changes per block | Step **5a** Inc-0 baseline, **5b+** per new pipeline stage |
| **Inc-x** too big | Split increment in **`incremental_plan.md`** (Inc-xa / Inc-xb) |

---

## Step 2 — requirement intake (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **2a** | Regenerate **`converted/`**; sanity-check `README.md` + file sizes | `export_specs_to_md.py` clean run |
| **2b** | **SRC-01** only: widths + opcode + field `.md` → `port_list.md` / `feature_list` F-003 | Tables consistent with XLSX |
| **2c** | **SRC-07** Overview + Microarchitecture scan → `feature_list` F-023–F-044 notes | Index rows filled or G-xx |
| **2d** | **SRC-07** Master/CPU/Flow/Algorithm/Interfaces → F-045–F-075 + `ASSUMPTIONS.md` | Step 2 § workflow item 8 satisfied |
| **2e** | **SRC-08** PDF vs extract: ordering/credit notes → `ASSUMPTIONS.md` | CHI interpretation logged |

---

## Step 3 — ports & features (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **3a** | **`port_list.md`**: clock/reset, widths, **directions** §3 | No open TBD without G-xx |
| **3b** | **`feature_list.md`**: **F-001–F-014** + P0 CHI rows | Linked to `test_list.md` placeholders |
| **3c** | **`feature_list.md`**: **F-015–F-022** (Master/CPU shims) | `function_list.md` §10 aligned |
| **3d** | **`feature_list.md`**: **F-023–F-044** (Overview + Microarchitecture) | `traceability.md` §2 batch rows |
| **3e** | **`feature_list.md`**: **F-045–F-075** (Master extras, async, flows, iface, frontend, reset hierarchy, terminology) | `traceability.md` + `step8.md` R5 plan |
| **3f** | **`cycle_budget.md`**: Inc-0 line + pointer from `incremental_plan.md` | Matches current `csu.py` |

---

## Step 4 — sequential algorithm (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **4a** | **`csu_main_cycle` skeleton** + RX/TX happy path only | `step4.md` §2 + `function_list` §2–8 |
| **4b** | **Master/CPU** logical paths (`function_list` §10) as named stubs in pseudocode | No orphan F-015–F-022 |
| **4c** | **Flows** (streaming / CMO / alias / order) as explicit branches or TODO with F-id | F-053–F-059 referenced |
| **4d** | State bundles §3 sized / field names from **`converted/SRC-01` / SRC-07** | Peer review note in log |

---

## Step 5 — pipeline mapping (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **5a** | **Inc-0** occurrence table only (`step5.md` + `cycle_budget.md`) | MLIR contract passes |
| **5b** | **F-031 LTU** / critical path: extra `domain.next()` if needed | `cycle_budget.md` + `INCx_*` updated |
| **5c** | **F-052 CDC** boundary: document which logic is sync-only vs async wrapper | `ASSUMPTIONS.md` § CDC |
| **5d** | Wide-bus / multi-beat staging per SRC-07 figures | Signal cycle table §4 expanded |

---

## Step 6 — V5 pseudocode / RTL (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **6a** | Widths + `cas` inputs + **F-003** opcode policy | `emit_csu_mlir()` green |
| **6b** | **Tracker / state** growth per Inc-x | Tests extended |
| **6c** | **Egress** builders match **Tab 3‑11** comments (**F-045**) | Review against `SRC-07` digest |
| **6d** | Child **`@module`** or helpers with `push`/`pop` | Documented in `step5.md` / `ASSUMPTIONS.md` |

---

## Step 7 — traceability (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **7a** | Port matrix §1 | All ports have Feature column |
| **7b** | Feature matrix §2 for **F-001–F-022** | Tests IDs or TBD+G-xx |
| **7c** | Feature matrix §2 for **F-023–F-075** | Batch rows expanded when RTL lands |
| **7d** | Gap register §4 + sign-off prep §5 | Dated owners |

---

## Step 8 — tests (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **8a** | **T-001–T-014** skeleton in TB | Compiles |
| **8b** | Opcode / flit **golden** from `converted/SRC-01` | Parametrize or tables |
| **8c** | **F-023+** directed tests scheduled (`T-015+` in `test_list.md`) | R5 satisfied per milestone |
| **8d** | **SYS-*** steps in `system_test_spec.md` tied to F-055 / F-056 / … | `step10.md` runnable |

---

## Step 9 — increments (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **9a** | Edit **`incremental_plan.md`**: split one Inc into **Inc-xa / Inc-xb** with separate exit criteria | Logged |
| **9b** | After each micro-merge: **full** `run_csu_verification.py` | Green |
| **9c** | Doc refresh: if **F-xxx** set changed, rerun Step **2d** parity check | `IMPLEMENTATION_LOG.md` entry |

---

## Step 10 — system & sign-off (optional substeps)

| Sub | Focus | Done when |
|-----|--------|-----------|
| **10a** | Run directed suite only | All T-xxx PASS |
| **10b** | Run **SYS-01…** per `system_test_spec.md` | Logs archived |
| **10c** | **`traceability.md` §5** sign-off + README reproduction | Milestone closed |

---

## Relationship to `incremental_plan.md`

- **Inc-x** backlog = *implementation* slices.  
- **workflow_substeps** = *documentation / analysis* slices inside a Step.  
- You may reference both in one PR: e.g. “Inc-3b + Step 6b”.

---

**Copyright © 2024–2026 PyCircuit Contributors (workflow note); CSU vendor specs remain property of their respective holders.**
