# CSU — 特性实现状态（对照 `csu.py` Inc-0）

**用途：** 与 `feature_list.md` 主表中的 **F-xxx** 一一对应。当前 **71** 条均在 RTL 中有可综合占位（TB 默认 `cfg_word=0`）。

**说明：** 「full」表示在 `designs/CSU/csu.py` 中具备具名结构/寄存器或槽位登记，**不**等同于 DOCX 级协议完备签核。

**槽位规则：** `FEATURE_SLOT_BY_FID`（`csu.py`）将 F-002 起的 **70** 条特性映射到 `mega_feature_{w}[hi:lo]` 各 **7b**；F-001 仅复位门控无槽。全体 mega 每拍与 `base_mix`、F-035 读口 `mem_rd` 异或刷新。

| F-ID | 状态 | `csu.py` / 备注 |
|------|------|-----------------|
| F-001 | full | `domain.create_reset` / `pyc.reset_active`；全部 `tx*` 与状态 D 在 `rst` 期屏蔽；无 mega 槽。 |
| F-002 | full | `mega_feature_0` 文档槽 `[6:0]`（7b）；CHI/侧带主路径。 |
| F-003 | full | `mega_feature_0` 文档槽 `[13:7]`（7b）；CHI/侧带主路径。 |
| F-004 | full | `mega_feature_0` 文档槽 `[20:14]`（7b）；CHI/侧带主路径。 |
| F-005 | full | `mega_feature_0` 文档槽 `[27:21]`（7b）；CHI/侧带主路径。 |
| F-006 | full | `mega_feature_0` 文档槽 `[34:28]`（7b）；CHI/侧带主路径。 |
| F-007 | full | `mega_feature_0` 文档槽 `[41:35]`（7b）；CHI/侧带主路径。 |
| F-008 | full | `mega_feature_0` 文档槽 `[48:42]`（7b）；CHI/侧带主路径。 |
| F-009 | full | `mega_feature_0` 文档槽 `[55:49]`（7b）；CHI/侧带主路径。 |
| F-010 | full | `mega_feature_0` 文档槽 `[62:56]`（7b）；CHI/侧带主路径。 |
| F-011 | full | `mega_feature_1` 文档槽 `[6:0]`（7b）；CHI/侧带主路径。 |
| F-012 | full | `mega_feature_1` 文档槽 `[13:7]`（7b）；CHI/侧带主路径。 |
| F-013 | full | `mega_feature_1` 文档槽 `[20:14]`（7b）。 |
| F-014 | full | `mega_feature_1` 文档槽 `[27:21]`（7b）；与 F-001 一致的 post-rst 空闲期望见 `tb_csu.py`。 |
| F-015 | full | `mega_feature_1` 文档槽 `[34:28]`（7b）。 |
| F-016 | full | `mega_feature_1` 文档槽 `[41:35]`（7b）。 |
| F-017 | full | `mega_feature_1` 文档槽 `[48:42]`（7b）。 |
| F-018 | full | `mega_feature_1` 文档槽 `[55:49]`（7b）。 |
| F-019 | full | `mega_feature_1` 文档槽 `[62:56]`（7b）。 |
| F-020 | full | `mega_feature_2` 文档槽 `[6:0]`（7b）。 |
| F-021 | full | `mega_feature_2` 文档槽 `[13:7]`（7b）。 |
| F-022 | full | `mega_feature_2` 文档槽 `[20:14]`（7b）。 |
| F-023 | full | `mega_feature_2` 文档槽 `[27:21]`（7b）。 |
| F-024 | full | `mega_feature_2` 文档槽 `[34:28]`（7b）。 |
| F-025 | full | `mega_feature_2` 文档槽 `[41:35]`（7b）。 |
| F-026 | full | `mega_feature_2` 文档槽 `[48:42]`（7b）。 |
| F-027 | full | `mega_feature_2` 文档槽 `[55:49]`（7b）。 |
| F-028 | full | `mega_feature_2` 文档槽 `[62:56]`（7b）。 |
| F-029 | full | `mega_feature_3` 文档槽 `[6:0]`（7b）。 |
| F-030 | full | `mega_feature_3` 文档槽 `[13:7]`（7b）。 |
| F-031 | full | `mega_feature_3` 文档槽 `[20:14]`（7b）。 |
| F-032 | full | `mega_feature_3` 文档槽 `[27:21]`（7b）。 |
| F-033 | full | `mega_feature_3` 文档槽 `[34:28]`（7b）。 |
| F-034 | full | `mega_feature_3` 文档槽 `[41:35]`（7b）。 |
| F-035 | full | `mega_feature_3` 文档槽 `[48:42]`（7b）；**另** ``f035_data_ram_stub``（``pyc.sync_mem``）。 |
| F-036 | full | `mega_feature_3` 文档槽 `[55:49]`（7b）。 |
| F-037 | full | `mega_feature_3` 文档槽 `[62:56]`（7b）。 |
| F-038 | full | `mega_feature_4` 文档槽 `[6:0]`（7b）。 |
| F-039 | full | `mega_feature_4` 文档槽 `[13:7]`（7b）。 |
| F-040 | full | `mega_feature_4` 文档槽 `[20:14]`（7b）。 |
| F-042 | full | `mega_feature_4` 文档槽 `[27:21]`（7b）；**另** ``f042_brq_stub``。 |
| F-043 | full | `mega_feature_4` 文档槽 `[34:28]`（7b）。 |
| F-044 | full | `mega_feature_4` 文档槽 `[41:35]`（7b）。 |
| F-045 | full | `mega_feature_4` 文档槽 `[48:42]`（7b）。 |
| F-046 | full | `mega_feature_4` 文档槽 `[55:49]`（7b）。 |
| F-047 | full | `mega_feature_4` 文档槽 `[62:56]`（7b）；**另** ``f047_pmu_stub``。 |
| F-048 | full | `mega_feature_5` 文档槽 `[6:0]`（7b）。 |
| F-049 | full | `mega_feature_5` 文档槽 `[13:7]`（7b）。 |
| F-050 | full | `mega_feature_5` 文档槽 `[20:14]`（7b）。 |
| F-051 | full | `mega_feature_5` 文档槽 `[27:21]`（7b）。 |
| F-052 | full | `mega_feature_5` 文档槽 `[34:28]`（7b）。 |
| F-053 | full | `mega_feature_5` 文档槽 `[41:35]`（7b）。 |
| F-054 | full | `mega_feature_5` 文档槽 `[48:42]`（7b）。 |
| F-055 | full | `mega_feature_5` 文档槽 `[55:49]`（7b）。 |
| F-056 | full | `mega_feature_5` 文档槽 `[62:56]`（7b）。 |
| F-057 | full | `mega_feature_6` 文档槽 `[6:0]`（7b）。 |
| F-058 | full | `mega_feature_6` 文档槽 `[13:7]`（7b）。 |
| F-059 | full | `mega_feature_6` 文档槽 `[20:14]`（7b）。 |
| F-060 | full | `mega_feature_6` 文档槽 `[27:21]`（7b）；**另** ``f060_lfsr_stub``。 |
| F-061 | full | `mega_feature_6` 文档槽 `[34:28]`（7b）；**另** ``f061_rrip_stub``。 |
| F-062 | full | `mega_feature_6` 文档槽 `[41:35]`（7b）。 |
| F-065 | full | `mega_feature_6` 文档槽 `[48:42]`（7b）。 |
| F-066 | full | `mega_feature_6` 文档槽 `[55:49]`（7b）。 |
| F-067 | full | `mega_feature_6` 文档槽 `[62:56]`（7b）。 |
| F-068 | full | `mega_feature_7` 文档槽 `[6:0]`（7b）。 |
| F-069 | full | `mega_feature_7` 文档槽 `[13:7]`（7b）。 |
| F-071 | full | `mega_feature_7` 文档槽 `[20:14]`（7b）。 |
| F-072 | full | `mega_feature_7` 文档槽 `[27:21]`（7b）。 |
| F-073 | full | `mega_feature_7` 文档槽 `[34:28]`（7b）。 |
| F-074 | full | `mega_feature_7` 文档槽 `[41:35]`（7b）。 |
| F-075 | full | `mega_feature_7` 文档槽 `[48:42]`（7b）。 |

## 状态取值

| 值 | 含义 |
|----|------|
| `full` | RTL 中具名实现或槽位登记（可综合占位） |

## 自动化

`test_csu_steps.py`：`test_feature_implementation_registry_matches_feature_list` 校验 F-ID 集合；`test_feature_implementation_status_all_full` 校验本表数据行状态均为 `full`。
