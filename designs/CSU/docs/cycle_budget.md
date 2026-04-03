# CSU — occurrence / clock-cycle budget（周期预算）

**目的：** 对每个实现阶段（含 **Inc-0…**）给出 **可验证** 的周期指标，并与 `emit_mlir()` 中的 **`pyc.reg`** 数量对齐。

**术语（必读）：**

| 术语 | 含义 |
|------|------|
| **Occurrence（逻辑周期）** | `CycleAwareDomain` 的 `cycle_index`；每调用一次 `domain.next()` 前进 1。与 **同一物理 `clk` 上的拍数** 不同：一个 occurrence 段内的组合逻辑仍在 **同一时钟沿** 之前收敛。 |
| **同步寄存器（`pyc.reg`）** | `domain.state()` / `domain.cycle()` 以及 **周期对齐** 插入的 `_v5_bal_*` 链在 MLIR 中均体现为 `pyc.reg`。 |
| **到端口的稳态延迟** | 自 **主时钟 `clk` 上升沿** 起，输入稳定后，输出 `tx*` 更新所需 **整拍数**；需结合仿真或静态结构数寄存器级数。 |

**权威实现：** `designs/CSU/csu.py`  
**验证：** `csu.assert_inc0_mlir_cycle_contract(mlir)` 与 `test_csu_steps.test_step06_emit_mlir_cycle_aware_shell`。

---

## 1. 方法论步骤与周期文档责任

| Step | 文档 | 周期相关内容 |
|------|------|----------------|
| 1–2 | `step1.md` / `step2.md` | 无 RTL 周期；不写预算。 |
| 3 | `step3.md` | 在 **本文件** 登记 **Inc-0** 预算行（或指向 §2）。 |
| 4 | `step4.md` | 顺序算法 **0** 拍；不写 `domain.next`。 |
| **5** | **`step5.md`** | **必须** 写明计划 **occurrence 段数**、每段寄存器边界。 |
| **6** | **`step6.md`** | 伪代码 / 实现中的 **`domain.next()` 次数** 必须与 Step 5 一致。 |
| 7 | `step7.md` / `traceability.md` | 可将「周期预算 ID」列入追溯表。 |
| 8 | `test_list.md` | 可对关键路径注明 **期望延迟（拍）**（可选）。 |
| **9** | **`incremental_plan.md`** | 每个 **Inc-x** 更新本文件 §2 表格。 |
| 10 | `system_test_spec.md` | 系统场景可验收 **端到端拍数**（可选）。 |

---

## 2. Inc-0（当前 `build_csu` 壳 + stub）— 已锁定预算

以下数字与 **`designs/CSU/csu.py`（Inc-0 baseline）** 一致，变更实现时必须同步改此表与 `csu.py` 内常量。

### 2.1 Occurrence 规划（V5）

| Occurrence 索引 | `build_csu` 中段落 | 行为摘要 |
|------------------|-------------------|----------|
| **0** | `cas(..., cycle=0)` 与 RX/TB 输入上的组合锥 | 输入采样（逻辑）、`digest32` 等组合逻辑 |
| **1** | 第一次 `domain.next()` 之后 | `domain.state`：CHI/侧带 7 项 + `mega_feature_0…7` + `feat_shaft_stub` + `f060`/`f042`/`f047`/`f061` stub + **F-035** `pyc.sync_mem` 组合读口接入 `base_mix` / `feat` |
| **2** | 第二次 `domain.next()` 之后 | `domain.cycle`：`txreq_q`、`txrsp_q`、`txdat_q`、`pend_q` 的 **D**；含与 occ 0 操作数对齐的 **平衡寄存器** |
| **3** | 第三次 `domain.next()` 之后 | `m.output(...)` 绑定到上一段 **寄存器 Q**（组合输出端口名） |

**契约 A — Occurrence 段数：**

- `domain.next()` 调用次数：**3**  
- **Occurrence 段总数：** **4**（索引 **0 … 3**）

### 2.2 显式寄存器（设计意图）

| 类型 | 名称（逻辑） | 个数 |
|------|----------------|------|
| `domain.state` | 上表 7 项 + `mega_feature_0…7`（8）+ `feat_shaft_stub` + `f060_lfsr_stub` + `f042_brq_stub` + `f047_pmu_stub` + `f061_rrip_stub` | **20** |
| `domain.cycle` | `txreq_q`, `txrsp_q`, `txdat_q`, `txreq_pend_q` | **4** |
| `pyc.sync_mem` | `f035_data_ram_stub`（**不计入**下方 `pyc.reg` grep） | **1** |

**契约 B — 显式反馈寄存器（state+cycle）：** **24**

### 2.3 MLIR 实测契约（含自动周期平衡）

V5 在 **不同 occurrence** 的操作数组合时插入 **`_v5_bal_*`** 链，因此 **`pyc.reg` 总数 ≥ 显式 7**。

| 指标 | Inc-0 当前黄金值 | 说明 |
|------|------------------|------|
| `pyc.reg` 出现次数 | **26** | `grep -c 'pyc.reg'` on `emit_mlir()` 输出（较显式 24 多 **2** 路隐式对齐寄存器） |
| 名称含 `_v5_bal_` 的线网/寄存器相关出现 | **4** | 对齐 `tb_issue_req` / `tb_txreq_seed` / `rxrsp` / `rxdat` 等到 occurrence 2 |
| `pyc.reset_active` | **≥1** | `!pyc.reset` → `i1`，供 F-001 输出/状态 D 端屏蔽 |

**契约 C — MLIR：** `emit_csu_mlir()` 中 **`pyc.reg` 计数 == 26**；**`pyc.reset_active` 必须出现**（见 `csu.assert_inc0_mlir_cycle_contract`）。

### 2.4 主时钟上到 `tx*` 的寄存器级数（结构级，Inc-0）

在 **Inc-0 stub** 下（无额外 IO 打拍）：

- **`txreq` / `txreq_pend`：** 经 `latched_txreq` 或 `pend` 的 **state** 一拍 + `domain.cycle` 一拍 + 可能 **平衡链** → **至少 2 级同步寄存器** 到 `txreq_q`（不含 balance 时 2 级；含 balance 时路径上 **≥2**）。  
- **`txrsp` / `txdat`：** `rx*` 在 occ 0，在 occ 2 使用 → **平衡链（约 2 级）** + **`domain.cycle`（1 级）** → **约 3 级** 到端口（以 MLIR 为准）。

**说明：** 精确「输入变化到输出变化」的仿真拍数需在 `tb_csu` 中按 `Tb` 相位标定；本文件给出 **结构级下限** 与 **MLIR 寄存器计数**。

### 2.5 Inc-1 — 复位脉宽 vs F-001 / F-014

| 项 | 要求 |
|----|------|
| **结构** | 全部 `pyc.reg`（含 `_v5_bal_*`）的第二个操作数为顶层 `%rst`（`!pyc.reset`）；`init`/复位值均为 **0**。 |
| **TB 最小断言长度** | **≥ 4** 个主时钟上升沿（排空 occurrence **0…3** 上的寄存器链）；**建议 ≥ 16** 以符合 SRC-07 对 SoC 复位脉宽的叙述（见 `ASSUMPTIONS.md` §2）。 |
| **验收** | `tb_csu.py`：长复位后 **cycle 0**、全输入 0 → `txreq`/`txrsp`/`txdat`/`txreq_pend` **post** 相位期望为 0。 |
| **实现** | 方言 **`pyc.reset_active`** + `Module.reset_active` / `CycleAwareDomain.create_reset()` → **i1**；`csu.py` 在 **rst** 时对 `tx*` 输出与状态 **D** 端做 **mux** 清零/保持。 |

---

## 3. 后续 Inc-x

每增加一次 `domain.next()` 或 `domain.cycle` / `state`：

1. 更新 §2 表格或新增 **Inc-x** 子节。  
2. 更新 `csu.py` 中 `INC0_*` 或引入 `INCx_*` 常量。  
3. 扩展 `assert_*_mlir_cycle_contract` 或黄金计数。

---

## 4. 与 Inc-0 实现一致性检查清单

- [ ] `build_csu` 中 `domain.next()` 次数 == **3**  
- [ ] `domain.state` + `domain.cycle` 个数 == **20 + 4 = 24**（另 **1** 路 `pyc.sync_mem`）  
- [ ] `emit_mlir()` 中 `pyc.reg` 计数 == **26** 且含 **`pyc.reset_active`**  
- [ ] 本文 §2.1 与 `step5.md` / `step6.md` 中阶段表一致  
