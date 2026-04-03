# Step 2 — Read all CSU block-specific requirement documents

**Method reference:** `docs/pycircuit_implementation_method.md` § Step 2 (incl. **Design specification conversion**)  
**Deliverable file:** `requirement_sources.md` (detailed tables)

---

## 1. Goal

Load **every** normative input for **this** block. **Primary working copies for agents and text tools** are the **Markdown digests** under **`designs/CSU/docs/converted/`**; keep the original **.xlsx / .docx / .pdf** as archival/normative where the program requires.

**Regenerate** after any vendor document update:

```bash
python3 designs/CSU/scripts/export_specs_to_md.py   # from repo root
```

Index: `converted/README.md`. Per-SRC paths: `requirement_sources.md` §2.

**Large Step 2?** Use **`workflow_substeps.md`** § “Step 2 — requirement intake” (**2a–2e**) to split **converted/** refresh, SRC-01, SRC-07 halves, SRC-08.

---

## 1b. Cycle / timing contract（本步骤）

本步 **不** 写 occurrence 表。若在 **`converted/SRC-07_linxcore950_csu_design_spec.md`** 中摘录 **多周期 RAM、IO 打拍** 等要求，在 `requirement_sources.md` 或 `ASSUMPTIONS.md` 中 **标注「将映射到 Step 5 / `cycle_budget.md`」**，避免实现阶段隐性加深流水线。

---

## 2. Files to process

| File | Format | Markdown digest (`converted/`) | Action |
|------|--------|----------------------------------|--------|
| `CSU 接口Protocol_辅助设计输入.xlsx` | XLSX | `SRC-01_xlsx_*.md` | Search tables / opcodes in `.md` |
| `LinxCore950 CSU Design Specification-AI辅助设计输入.docx` | DOCX | `SRC-07_linxcore950_csu_design_spec.md` + `SRC-07_media/` | Map sections → F-xxx |
| `IHI0050H_amba_chi_architecture_spec.pdf` | PDF | `SRC-08_chi_architecture_spec_extract.md` *(partial)* | **Figures / full normative text → original PDF** |

---

## 3. Extraction workflow

1. **Ensure digests exist:** Run `export_specs_to_md.py` if `converted/` is missing or stale.  
2. **Inventory:** `requirement_sources.md` §2 links each SRC to its `.md` path.  
3. **Widths first:** `SRC-01_xlsx_CHI_Core_CSU_ALL.md` aggregated `*_W` → `port_list.md`.  
4. **Fields second:** `SRC-01_xlsx_CHI_CSU_SoC_*_field.md` → `port_list.md` § inventories.  
5. **Opcodes:** `SRC-01_xlsx_CHI_CSU_SoC_Opcode.md` → `feature_list.md` F-003 + tests; keep `csu.LEGAL_REQ_OPCODE_VALUES` in sync when **P HC supports（950）** changes.  
6. **Behavior:** `SRC-07_*.md` → F-015+ rows, timing, reset, Master/CPU blocks (`function_list.md` §10).  
7. **CHI:** `SRC-08_*.md` + full PDF → `ASSUMPTIONS.md` when Linx narrows CHI.  
8. **Feature parity:** Run through **`feature_list.md` § “SRC-07 digest heading checklist (full)”** against **`converted/SRC-07_linxcore950_csu_design_spec.md`**; every row must be satisfied (**F-xxx** or **—**). Add **F-076+** or **G-xx** only for new export headings or waivers (`traceability.md` §4).

---

## 4. Quality checks

- [ ] Sum of field widths == `REQFLIT_W` / `DATFLIT_W` / etc. for each channel (verify in converted Sheet1 / field `.md`)  
- [ ] Every **TBD** cell in XLSX has an owner in gap list (`traceability.md` §4)  
- [ ] Conflicts between **SRC-07** digest and **SRC-01** digest logged in `ASSUMPTIONS.md` before coding

---

## 5. Completion criteria

`requirement_sources.md` is up to date; **SRC-01–08** rows point to **concrete** `converted/*.md` paths and **actual** section/sheet references (not placeholders) after extraction pass.

**Next step:** `step3.md`
