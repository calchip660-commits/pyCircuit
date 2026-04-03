# Step 7 — Specification and feature traceability audit

**Method reference:** `docs/pycircuit_implementation_method.md` § Step 7  
**Deliverable file:** `traceability.md` (maintain as source of truth)

**Converted specs:** When tracing **SRC-xx → F-xxx**, prefer citing **`designs/CSU/docs/converted/*.md`** paths (as in `requirement_sources.md` §2) so reviews do not depend on opening XLSX/DOCX/PDF alone.

**Full CSU feature set:** **`feature_list.md`** lists **F-001–F-075** with **digest index** + **§ SRC-07 digest heading checklist (full)**; **`traceability.md` §2** summarizes **F-023–F-075** in batches — expand rows (or add tests) as implementation lands.

**Large Step 7?** **`workflow_substeps.md`** § Step 7 (**7a–7d**): ports → F-001–F-022 → F-023–F-075 → gaps/sign-off.

---

## 1. Goal

Prove **coverage**:

- Every **port** (or bus field group) is driven or consumed in the design.  
- Every **feature** F-xxx appears in pseudocode (`step6.md`) or child modules.  
- Every **test** T-xxx maps back to a feature.

---

## 1b. Cycle / timing contract（本步骤）

追溯矩阵可选列：**周期预算 ID**（指向 **`cycle_budget.md`** 中 Inc-x / 阶段表），确保 **Step 5 规划**、**Step 6 实现**（`domain.next()` 次数）、**MLIR 黄金计数** 三者可追溯。

---

## 2. Audit procedure

1. Open `port_list.md` §3 — for each row, add/update `traceability.md` §1 (port → region → features).  
2. Open `feature_list.md` — for each F-xxx, ensure §2 row exists with function + test IDs.  
3. Open `test_list.md` — for each T-xxx, ensure §3 row exists.  
4. Walk **SRC-07** requirements in **`converted/SRC-07_*.md`**: if no F-xxx, **add feature** or **waive** with **section heading / figure** ref in `traceability.md` §4.

---

## 3. Gap handling

Any item that cannot be closed:

| Gap ID | Description | Action |
|--------|-------------|--------|
| G-xx | Text | Owner + date + resolution path |

Do **not** delete gaps silently; only **close** with sign-off reference.

---

## 4. Review gate

**Before starting Inc-3** in `incremental_plan.md`:

- [ ] §1 port matrix: no empty Feature column  
- [ ] §2 feature matrix: no empty Test column (use `TBD-test` if test not written yet — must be rare)  
- [ ] §4 gap list reviewed by lead

---

## 5. Completion checklist

- [ ] `traceability.md` reflects latest `port_list.md` / `feature_list.md` (incl. **F-023–F-075**) / `test_list.md`  
- [ ] `ASSUMPTIONS.md` lists any waived requirements with SRC id + **heading** in `SRC-07_*.md` where possible

**Next step:** `step8.md`
