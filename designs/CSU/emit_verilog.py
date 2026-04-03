#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSU → Verilog：生成 .pyc（含 pycc 必需属性）→ 调用 pycc --emit=verilog。

用法（从仓库根目录）::

    PYTHONPATH=compiler/frontend python3 designs/CSU/emit_verilog.py

输出  ``designs/CSU/sim_out/verilog/csu.v``
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_THIS = Path(__file__).resolve().parent
_REPO = _THIS.parents[1]
sys.path.insert(0, str(_REPO / "compiler" / "frontend"))
sys.path.insert(0, str(_THIS))

from pycircuit.api_contract import FRONTEND_CONTRACT  # noqa: E402


def _find_pycc() -> Path:
    roots = [
        _REPO / ".pycircuit_out" / "toolchain" / "install" / "bin" / "pycc",
        _REPO / "dist" / "pycircuit" / "bin" / "pycc",
        _REPO / "build-top" / "bin" / "pycc",
        _REPO / "build" / "bin" / "pycc",
        _REPO / "compiler" / "mlir" / "build2" / "bin" / "pycc",
        _REPO / "compiler" / "mlir" / "build" / "bin" / "pycc",
    ]
    for d in sorted(_REPO.glob("compiler/mlir/build*/bin/pycc")):
        roots.append(d)
    env = os.environ.get("PYCC")
    if env:
        roots.insert(0, Path(env))
    for p in roots:
        if p.is_file() and os.access(p, os.X_OK):
            return p
    found = shutil.which("pycc")
    if found:
        return Path(found)
    raise SystemExit("找不到 pycc（请设置 PYCC=... 或 cmake --build 编译 pycc）")


def _stamp_pycc_attrs(raw_mlir: str, *, top: str = "csu") -> str:
    """Inject ``pyc.frontend.contract`` on module and ``pyc.kind`` etc. on func.func."""
    struct_metrics = json.dumps({
        "ast_node_count": 0,
        "collection_count": 0,
        "collection_instance_count": 0,
        "estimated_inline_cost": 0,
        "hardware_call_count": 0,
        "instance_count": 0,
        "loop_count": 0,
        "module_call_count": 0,
        "module_family_collection_count": 0,
        "repeated_body_clusters": [],
        "source_loc": 0,
        "state_alloc_count": 0,
        "state_call_count": 0,
    }, sort_keys=True, separators=(",", ":"))
    struct_collections = "[]"
    params_esc = json.dumps("{}", ensure_ascii=False)
    base_esc = json.dumps(top, ensure_ascii=False)
    struct_m_esc = json.dumps(struct_metrics, ensure_ascii=False)
    struct_c_esc = json.dumps(struct_collections, ensure_ascii=False)

    func_extra = (
        f', pyc.kind = "module", pyc.inline = "false"'
        f", pyc.params = {params_esc}"
        f", pyc.base = {base_esc}"
        f', pyc.value_params = []'
        f', pyc.value_param_types = []'
        f", pyc.struct.metrics = {struct_m_esc}"
        f", pyc.struct.collections = {struct_c_esc}"
    )

    raw_mlir = raw_mlir.replace(
        "module {",
        f'module attributes {{pyc.top = @{top}, pyc.frontend.contract = "{FRONTEND_CONTRACT}"}} {{',
        1,
    )

    def _inject_func_attrs(m: re.Match[str]) -> str:
        before_close = m.group(0)
        idx = before_close.rfind("}")
        return before_close[:idx] + func_extra + before_close[idx:]

    raw_mlir = re.sub(
        r"func\.func @" + re.escape(top) + r"\([^)]*\)[^{]*attributes\s*\{[^}]*\}",
        _inject_func_attrs,
        raw_mlir,
        count=1,
    )

    return raw_mlir


def main() -> None:
    from csu import emit_csu_mlir

    raw = emit_csu_mlir()
    stamped = _stamp_pycc_attrs(raw, top="csu")

    out_dir = _THIS / "sim_out" / "verilog"
    out_dir.mkdir(parents=True, exist_ok=True)

    pyc_path = _THIS / "sim_out" / "csu.pyc"
    pyc_path.write_text(stamped, encoding="utf-8")
    print(f"[emit_verilog] wrote {pyc_path}  ({len(stamped)} chars)")

    pycc = _find_pycc()
    print(f"[emit_verilog] pycc = {pycc}")

    v_path = out_dir / "csu.v"
    cmd = [str(pycc), str(pyc_path), "--emit=verilog", "-o", str(v_path)]
    print(f"[emit_verilog] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout.strip():
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"pycc 失败 (exit {result.returncode})")

    size = v_path.stat().st_size
    print(f"[emit_verilog] 成功 → {v_path}  ({size // 1024} KB)")


if __name__ == "__main__":
    main()
