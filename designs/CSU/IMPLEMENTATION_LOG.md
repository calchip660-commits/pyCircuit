# CSU implementation log

## 2026-04-01 — Inc-0 / Steps 1–6 baseline

- **Features:** Shell + stub tracker, TXREQ latch + opcode gate (F-003 stub), pend counter stub, TXRSP/TXDAT echo.
- **Files:** `designs/CSU/csu.py`, `designs/CSU/test_csu_steps.py`, `designs/CSU/run_csu_verification.py`, `designs/CSU/__init__.py`
- **Tests:** `python3 designs/CSU/run_csu_verification.py` (stdlib runner)
- **Emit:** `PYTHONPATH=compiler/frontend python3 designs/CSU/csu.py`
- **Result:** PASS — MLIR emits; widths match `port_list.md`.

## 2026-04-01 — Cycle budget / Inc-0 MLIR contract

- **Docs:** `docs/cycle_budget.md`（Inc-0：`domain.next()`×3、occurrence 4 段、`pyc.reg`=9、`_v5_bal_`=4）；`step1.md`–`step10.md`、`step5.md`/`step6.md`、`incremental_plan.md`、`csu_implementation_requirements.md` 交叉引用。
- **Code:** `csu.py` 增加 `INC0_*` 常量、`assert_inc0_mlir_cycle_contract`；`emit_csu_mlir()` 发出 MLIR 前断言。
- **Tests:** `test_csu_steps.py` 校验 `cycle_budget.md` 存在、`domain.next()` 次数与 `INC0_*` 一致、系统测试锁定 `pyc.reg` 计数。
- **Result:** PASS — `run_csu_verification.py` 全绿。

## 2026-04-01 — Convert binary specs → Markdown; refresh Steps 2–4 / F-003

- **Script:** `designs/CSU/scripts/export_specs_to_md.py` → `designs/CSU/docs/converted/` (6× XLSX sheets, SRC-07 pandoc+media, SRC-08 pypdf extract pp.1–150).
- **Docs:** `ASSUMPTIONS.md`; `port_list.md` directions; `requirement_sources.md` digest column; `feature_list.md` F-003 trace + F-015–F-022; `function_list.md` §10 master/CPU shims.
- **Code:** `csu.py` — `LEGAL_REQ_OPCODE_VALUES` + `_req_opcode_supported()` (SRC-02 Yes-list) replaces single-opcode stub.
- **Tests:** Step 2 requires `converted/`; system test asserts `len(LEGAL_REQ_OPCODE_VALUES)==25`.

## 2026-04-01 — step1.md … step10.md ↔ converted/

- **Docs:** Each `designs/CSU/docs/stepN.md` now references **`designs/CSU/docs/converted/`** digests, `export_specs_to_md.py`, and/or `ASSUMPTIONS.md` where relevant (Markdown-first spec workflow).

## 2026-04-01 — SRC-07 → feature_list F-023–F-064 + steps 1–10

- **feature_list.md:** Index table + rows for Overview, Microarchitecture, Master/CPU extras, async bridge, Feature/Flow/Algorithm, PIPE, CPU/SoC interface; F-001/F-014 spec traces → SRC-07 Clock/Reset digest.
- **traceability.md §2:** Batch rows F-023–F-064 (TBD tests until RTL).
- **step1.md–step10.md:** Cross-references to F-023–F-064, R5 test rule, SYS hints, §4b chapter map in step4.

## 2026-04-01 — SRC-07 full heading coverage F-065–F-075 + checklist

- **feature_list.md:** Split **Frontend** into **F-065–F-068**; add **F-069** reset hierarchy, **F-071** terminology, **F-072–F-075** CPU/SoC **Transaction Type** + **Protocol Compliance**; **§ SRC-07 digest heading checklist (full)** lists every digest `#`/`##`/`###`.
- **traceability / steps / workflow_substeps:** Ranges updated to **F-001–F-075**; **test_step03** asserts checklist + F-075 present.

## 2026-04-01 — workflow_substeps.md

- **Docs:** `workflow_substeps.md` defines optional **2a–2e, 3a–3f, 4a–4d, 5a–5d, 6a–6d, 7a–7d, 8a–8d, 9a–9c, 10a–10c**; indexed from `csu_implementation_requirements.md`; pointers from `step1.md`, `step2.md`, `step3.md`.

## 2026-04-01 — `pyc.reset_active` + CSU RTL 扩展（F-001 组合清零 + 侧带/snoop 占位）

- **pyCircuit：** `PYC_ResetActiveOp` / `pyc.reset_active`；`dsl.Module.reset_active`；`CycleAwareDomain.create_reset()` 现返回 **i1** `Wire`。Verilog/C++ emit、FuseComb、CombDepGraph、CheckLogicDepth、CheckClockDomains 已处理。
- **csu.py：** 复位时屏蔽状态更新与 `tx*` 输出；增 **4** 个侧带/snoop 状态寄存器；`txrsp` 拼接 `rsp1`；MLIR **`pyc.reg`=13**，**`pyc.reset_active`** 断言；`cycle_budget.md` §2 已同步。
- **Tests:** `run_csu_verification.py` — PASS。

## 2026-04-01 — Inc-1 (option B): F-001 / F-014 baseline

- **RTL 语义：** 不增加 `domain.next()`；所有 `pyc.reg` 已带 `%rst` 与 `init=0`。因前端 `!pyc.reset` 非 `i1`，Inc-1 **未** 做输出侧 `mux(rst,0,reg_q)`；复位 prologue 内组合空闲依赖后续 `reset→i1` 或工具链扩展。
- **验证：** `test_inc1_all_pyc_reg_use_domain_rst`、`test_tb_csu_present`；`tb_csu.py`（`rst` 断言 16 拍 + cycle 0 对 `tx*` 期望 0）。
- **文档：** `cycle_budget.md` §2.5；`feature_implementation_status.md`（F-001/F-014→partial）；`incremental_plan.md` Inc-1 行；`csu.py` 模块注释。
- **Tests:** `PYTHONPATH=compiler/frontend python3 designs/CSU/run_csu_verification.py` — PASS。
