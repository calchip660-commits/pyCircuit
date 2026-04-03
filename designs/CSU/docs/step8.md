# Step 8 — Itemized test plan execution prep

**Method reference:** `docs/pycircuit_implementation_method.md` § Step 8  
**Deliverable file:** `test_list.md`

**Converted specs:** Build opcode / transaction matrices from **`converted/SRC-01_xlsx_CHI_CSU_SoC_Opcode.md`** (REQ + RESP columns). Expected flit field values should cite **`converted/SRC-01_xlsx_*_field.md`** or Sheet1 digest.

**Large Step 8?** **`workflow_substeps.md`** § Step 8 (**8a–8d**): baseline TB → golden opcodes → T-015+ schedule → SYS linkage.

---

## 1. Goal

Ensure **no port** and **no feature** lacks a **test case** before tape-out / milestone.

---

## 1b. Cycle / timing contract（本步骤）

对 **多拍路径**（如 RX→TX）的定向测试，可在 `test_list.md` 中注明 **期望稳定输出的最小主时钟拍数**（与 **`cycle_budget.md`** 结构级描述一致）。自动化断言优先使用 **`emit_csu_mlir()`** 内建契约或 `csu.assert_inc0_mlir_cycle_contract`。

---

## 2. Coverage rules

| Rule | Detail |
|------|--------|
| R1 | Each **output** port: ≥1 test asserts legal value in some scenario |
| R2 | Each **input** port: ≥1 test drives non-trivial stimulus |
| R3 | Each **F-xxx**: ≥1 test that **fails** if feature removed (regression sensitivity) |
| R4 | Each **opcode** class in SRC-02: either T-003 style negative or positive path |
| R5 | Each **F-023–F-075** row: add or schedule a **directed or SYS** test before tape-out (use **T-015+** / **SYS-***); until RTL exists, keep **TBD** only with dated **G-xx** in `traceability.md` §4 |

---

## 3. TB structure recommendation

Mirror `designs/BypassUnit/tb_bypass_unit.py`:

1. `compile_cycle_aware` or `compile` for DUT.  
2. `@testbench` driving `clk`/`rst`.  
3. `t.drive` / `t.expect` with `phase=` where needed (`docs/TESTBENCH.md`).  
4. For wide ports: drive **slices** or use helper to pack flits.

---

## 4. Traceability maintenance

When adding **T-015+**:

1. Add full row to `test_list.md`.  
2. Add column in `traceability.md` §3.  
3. Link features in `traceability.md` §2.

---

## 5. Automation (optional)

- Python `pytest` parametrization over opcode list from **`converted/SRC-01_xlsx_CHI_CSU_SoC_Opcode.md`** (or parse XLSX — keep lists consistent with `csu.LEGAL_REQ_OPCODE_VALUES`).  
- Golden vectors in `designs/CSU/golden/` (json or hex) — **do not** commit huge files without policy.

---

## 6. Completion checklist

- [ ] `test_list.md` has rows for all ports in `port_list.md` §3  
- [ ] Every F-001–F-014 maps to a test (see `feature_list.md` summary table); **F-015+** tests added as those features land  
- [ ] SYS scenarios referenced for integration

**Next step:** `step9.md`
