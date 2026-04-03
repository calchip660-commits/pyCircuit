# LinxCore950 CSU (pyCircuit V5)

Coherent System Unit bring-up per `docs/` methodology and `designs/CSU/docs/csu_implementation_requirements.md`.

## Specification Markdown (DOCX / XLSX / PDF)

After changing vendor binaries under `docs/`, regenerate agent-readable Markdown:

```bash
cd <repo-root>
python3 designs/CSU/scripts/export_specs_to_md.py
```

Outputs go to `designs/CSU/docs/converted/` (see `converted/README.md`).

## Quick verify

```bash
cd <repo-root>
export PYTHONPATH=compiler/frontend
python3 designs/CSU/run_csu_verification.py   # steps 1–10 + system checks
python3 designs/CSU/csu.py                    # print MLIR head
```

## Ports

See `docs/port_list.md`. This stub adds **verification hooks**:

- `tb_txreq_seed` (97b) — tie `0` in production; TB drives legal/illegal flits.
- `tb_issue_req` (1b) — pulse to load seed into `latched_txreq`.

## pytest (optional)

```bash
pip install pytest
PYTHONPATH=compiler/frontend pytest designs/CSU/test_csu_steps.py -v
```
