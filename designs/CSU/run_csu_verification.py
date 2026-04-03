#!/usr/bin/env python3
"""Run CSU step 1–10 checks without pytest (stdlib only).

Usage (from repo root)::

    PYTHONPATH=compiler/frontend python3 designs/CSU/run_csu_verification.py
"""
from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_FRONT = _REPO / "compiler" / "frontend"
_CSU = Path(__file__).resolve().parent

sys.path.insert(0, str(_FRONT))
sys.path.insert(0, str(_CSU))


def _load_tests():
    spec = importlib.util.spec_from_file_location("csu_tests", _CSU / "test_csu_steps.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


# Methodology order: Step 1–10, then system gate, then full regression (emit smoke).
_TEST_ORDER = (
    "test_step01_style_docs_exist",
    "test_step02_requirement_sources_and_specs",
    "test_step03_port_and_feature_lists",
    "test_feature_implementation_registry_matches_feature_list",
    "test_feature_implementation_status_all_full",
    "test_step04_function_list",
    "test_step05_pipeline_doc",
    "test_step06_emit_mlir_cycle_aware_shell",
    "test_inc1_all_pyc_reg_use_domain_rst",
    "test_tb_csu_present",
    "test_step07_traceability_matrix",
    "test_step08_test_list_covers_ports",
    "test_step09_incremental_plan_and_impl_log_or_stub",
    "test_step10_system_test_spec",
    "test_system_compile_and_port_width_constants",
    "test_all_steps_regression",
)

_STEP_LABELS = {
    "test_step01_style_docs_exist": "Step 1 — 阅读风格与示例文档",
    "test_step02_requirement_sources_and_specs": "Step 2 — 需求源与规格材料",
    "test_step03_port_and_feature_lists": "Step 3 — 端口与特性表",
    "test_feature_implementation_registry_matches_feature_list": "Step 3 — 特性实现登记与主表一致",
    "test_feature_implementation_status_all_full": "Step 3 — 特性实现状态表均为 full",
    "test_step04_function_list": "Step 4 — 算法分解 function_list",
    "test_step05_pipeline_doc": "Step 5 — 流水线 / cycle_budget",
    "test_step06_emit_mlir_cycle_aware_shell": "Step 6 — V5 实现与 MLIR",
    "test_inc1_all_pyc_reg_use_domain_rst": "Step 7 — Inc-1 复位端口结构（F-001）",
    "test_tb_csu_present": "Step 7 — T-001 TB 文件存在",
    "test_step07_traceability_matrix": "Step 7 — 追溯矩阵",
    "test_step08_test_list_covers_ports": "Step 8 — 测试计划",
    "test_step09_incremental_plan_and_impl_log_or_stub": "Step 9 — 增量计划与实现日志",
    "test_step10_system_test_spec": "Step 10 — 系统测试规格",
    "test_system_compile_and_port_width_constants": "System — 宽度与 MLIR 契约",
    "test_all_steps_regression": "Regression — MLIR 体量烟测",
}


def main() -> int:
    mod = _load_tests()
    failed: list[tuple[str, Exception]] = []
    for name in _TEST_ORDER:
        fn = getattr(mod, name, None)
        if fn is None or not callable(fn):
            print(f"SKIP  {name} (not found)")
            continue
        label = _STEP_LABELS.get(name, name)
        print(f"\n--- {label} ---")
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as e:  # noqa: BLE001
            failed.append((name, e))
            print(f"FAIL  {name}: {e}")
            traceback.print_exc()

    print(f"\nTotal failures: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
