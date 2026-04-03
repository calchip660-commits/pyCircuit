# Step 10 — System test and sign-off

**Method reference:** `docs/pycircuit_implementation_method.md` § Step 10  
**Deliverable files:** `system_test_spec.md`, `traceability.md` sign-off §5

**Converted specs:** **`SRC-08_chi_architecture_spec_extract.md`** is **partial** (text from first PDF pages only). For sign-off disputes on **ordering, PoS/PoC, credits, errors**, use the **full `IHI0050H_amba_chi_architecture_spec.pdf`**; you may extend the extract script page range if the team wants more text in git.

**SRC-07 system scenarios:** Design **SYS-*** cases in `system_test_spec.md` to stress cross-feature behavior called out in **`feature_list.md`**, e.g. **F-055** ordering + **F-056** streaming + **F-048**/`F-049` master/CPU routing + **F-052** async path (as RTL becomes available).

**Large Step 10?** **`workflow_substeps.md`** § Step 10 (**10a–10c**): directed → SYS → sign-off/README.

---

## 1. Goal

Validate **combined** behavior under realistic scenarios and formally close **traceability** (or accept waivers).

---

## 1b. Cycle / timing contract（本步骤）

系统场景（SYS-*）验收时，对照 **`cycle_budget.md`**：**端到端主时钟拍数** 是否在文档给出的结构级范围内；**`emit_csu_mlir()`** 仍须通过当前里程碑的 MLIR 周期断言（Inc-0：`assert_inc0_mlir_cycle_contract`）。

---

## 2. Execution order

1. Run **all** directed tests `T-001` … from `test_list.md`.  
2. Run **SYS-01** … **SYS-05** from `system_test_spec.md` (SYS-05 optional).  
3. Re-open `traceability.md`:  
   - §1–§3: no missing links  
   - §4: all gaps **closed** or **waived** with SRC reference  
4. Fill **sign-off** table in `traceability.md` §5.

---

## 3. Sign-off criteria

| Criterion | Evidence |
|-----------|----------|
| Functional complete | All **P0** features in `feature_list.md` (**F-001–F-075** where marked P0) implemented or formally waived |
| DV complete | `test_list.md` + SYS scenarios PASS |
| Docs complete | `port_list.md` / `ASSUMPTIONS.md` no unresolved TBD for direction/polarity (or waivers in `traceability.md` §4) |
| Risks | Residual items only in `ASSUMPTIONS.md` with approval |

---

## 4. Non-functional (if SRC-07 specifies)

- Fmax / area — record in `SYSTEM_TEST` or project tracker.  
- Power — optional.

---

## 5. Post sign-off

- Tag release or milestone in git.  
- Archive waveforms/logs per retention policy.  
- Update `designs/CSU/README.md` with **how to reproduce** SYS runs.

---

## 6. Completion checklist

- [ ] `system_test_spec.md` scenarios executed  
- [ ] `traceability.md` §5 signed  
- [ ] README updated

**Workflow complete** — return to `csu_implementation_requirements.md` §8 Definition of done.
