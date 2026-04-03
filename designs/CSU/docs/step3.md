# Step 3 — Top-level ports, buses, widths, and feature decomposition

**Method reference:** `docs/pycircuit_implementation_method.md` § Step 3  
**Deliverable files:** `port_list.md`, `feature_list.md` (this step **owns** keeping them consistent)

**Converted specs:** Use **`designs/CSU/docs/converted/`** for widths, fields, and opcodes — especially `SRC-01_xlsx_CHI_Core_CSU_ALL.md`, `SRC-01_xlsx_CHI_CSU_SoC_Opcode.md`, and `SRC-07_linxcore950_csu_design_spec.md`. Assumptions and direction rationale: **`ASSUMPTIONS.md`**.

**Large Step 3?** Use **`workflow_substeps.md`** § “Step 3 — ports & features” (**3a–3f**) to do ports first, then feature bands F-001–F-014 → F-015–F-022 → F-023–F-044 → F-045–F-075, then `cycle_budget.md`.

---

## 1. Goal

Freeze the **external contract** (ports) and a **testable feature** set before writing algorithm pseudocode.

---

## 2. Port work

1. Open `port_list.md`.  
2. Fill **Direction** column using SRC-07 narrative in **`converted/SRC-07_*.md`** + CHI naming; record inferences in **`ASSUMPTIONS.md` §1** if interconnect diagrams are ambiguous.  
3. Add **valid/ready** or **credit** signals if not part of packed flit width — note width = 0 in §3 means “inside flit” vs sideband.  
4. Add **clock/reset** rows when polarity/number of clocks known (SRC-07 §7 in digest).

**Width / bit-map source of truth:** **`converted/SRC-01_xlsx_CHI_Core_CSU_ALL.md`** (CSU视角); cross-check SoC field sheets `SRC-01_xlsx_CHI_CSU_SoC_*_field.md` per `ASSUMPTIONS.md` §4.

---

## 3. Feature work

1. Open `feature_list.md`.  
2. Keep **F-001–F-014** as CHI-shell baseline.  
3. Use **`feature_list.md`** § **SRC-07 digest index** + **§ heading checklist (full)** as the master map: **F-001–F-075**. Add **F-076+** only for new DOCX revisions or gaps.  
4. Link each feature to at least one test ID in **`test_list.md`** (use **TBD** only with a dated gap in `traceability.md` §4).

---

## 3b. Cycle / timing contract（本步骤）

端口冻结后，在 **`cycle_budget.md`** 中为 **Inc-0（或当前里程碑）** 保留一行：**规划的 occurrence 段数**、**`domain.next()` 次数**、以及（Inc-0 起）**`emit_csu_mlir()` 断言的 `pyc.reg` 等黄金值**。与 `incremental_plan.md` 中 Inc-x **退出条件** 交叉引用。

---

## 4. Top-level functionality paragraph

Use this template in `README.md` or `port_list.md` § intro when directions are known:

> The CSU (`<full name from DOCX>`) interfaces to `<list neighbors>` via CHI-style flit channels listed in `port_list.md`. It implements `<one-sentence role>`. Reset and clocking: `<from SRC-07>`.

---

## 5. Consistency checks

| Check | Rule |
|-------|------|
| Width | Every port width matches XLSX or DOCX override (document override) |
| Feature coverage | Every DOCX “shall” maps to ≥1 F-xxx |
| Trace prep | Every F-xxx will get a row in `traceability.md` §2 |

---

## 6. Completion checklist

- [ ] `port_list.md` has no unresolved **TBD** for direction (or gaps filed)  
- [ ] `feature_list.md` **heading checklist** matches current **`SRC-07_*.md`** export (F-001–F-075); gaps filed in `traceability.md` §4  
- [ ] **`cycle_budget.md`** 已含当前里程碑（至少 Inc-0）的周期预算行或与 §2 一致  
- [ ] `traceability.md` §4 updated if new gaps found

**Next step:** `step4.md`
