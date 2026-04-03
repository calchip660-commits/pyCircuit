# CSU — incremental implementation backlog (Step 9 detail)

**Parent:** `step9.md`  
**Related:** `feature_list.md`, `test_list.md`, `IMPLEMENTATION_LOG.md` (create at repo root of `designs/CSU/`).

---

## Rules

1. Each increment merges only **one** feature cluster (or minimal glue).  
2. After each increment: run **all** tests T-001… already defined.  
3. Record in `IMPLEMENTATION_LOG.md`: date, git hash, increment id, tests run, pass/fail.

---

## Backlog table

| Inc ID | Feature IDs | Code change summary | New/updated tests | Exit criteria |
|--------|-------------|---------------------|-------------------|---------------|
| Inc-0 | — | `csu.py`：`domain.next()` **3**；`state`×**20** + `cycle`×**4** + `sync_mem`×**1**；**`pyc.reset_active`**；`emit_csu_mlir()` 断言 **`pyc.reg`=26**、**`_v5_bal_`=4**（见 `cycle_budget.md` §2） | T-001 skeleton；`test_step06` / `test_system` 校验周期契约 | MLIR 通过契约；TB 可编译 |
| Inc-1 | F-001, F-014 | 全部状态寄存器挂 `rst` + `init=0`；`cycle_budget.md` §2.5 最小复位脉宽；`tb_csu.py`（T-001/T-014） | T-001, T-013, T-014 | `test_inc1_all_pyc_reg_use_domain_rst` + `tb_csu` 存在；SV/C++ 仿真待接 `pycircuit build` |
| Inc-2 | F-002 | `build_txreq` constant or table-driven pattern | T-002 | 97b alignment |
| Inc-3 | F-003 | Opcode filter / stall | T-003 | Illegal opcodes handled |
| Inc-4 | F-005, F-007 | Tracker + absorb RXRSP/RXDAT stubs | T-004, T-005 | State updates |
| Inc-5 | F-004, F-006 | TXRSP/TXDAT from tracker | T-004, T-011 | Response path |
| Inc-6 | F-008 | Snoop path + rsp1 | T-006 | Snoop green |
| Inc-7 | F-009–F-011 | WKUP, ERR, FILL | T-007–T-009 | Side channels |
| Inc-8 | F-012 | `txreq_pend` / credits | T-012, T-010 partial | Credit bounded |
| Inc-9 | F-013 | Ordering + stress hardening | T-010, SYS-* | Stress green |

---

## Dependency graph

```text
Inc-0 → Inc-1 → Inc-2 → Inc-3
              ↘ Inc-4 → Inc-5 → Inc-6 → Inc-7 → Inc-8 → Inc-9
```

*Adjust if DOCX shows snoop before full read path.*

---

## Commands (template)

```bash
export PYTHONPATH="$REPO/compiler/frontend"
python3 -c "from designs.CSU import csu  # adjust import path
# or: python3 -m pytest designs/CSU/ -q
```

*(Replace with project-standard `tb_csu.py` invocation once added.)*
