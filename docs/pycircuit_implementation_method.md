# PyCircuit implementation method (10-step workflow)

This document describes a **repeatable workflow** for implementing a hardware block in the pyCircuit repository using **PyCircuit V5 cycle-aware** style and/or the **pyc4.0 `@module` / `Circuit`** style. It is written for human engineers and for autonomous agents.

**Typo note:** “Pypto V5” in informal requests means **PyCircuit V5** (cycle-aware APIs in `compiler/frontend/pycircuit/v5.py`).

---

## Where programming style and APIs are documented

All normative and tutorial material for authoring lives under the repository **`docs/`** directory (path: `/docs` relative to repo root). Use these in **Step 1** and keep them open while coding:

| Topic | Primary documents |
|--------|-------------------|
| **V5 cycle-aware API** (signatures, `domain.next()`, `cycle`, `state`, `cas`, `mux`, `compile_cycle_aware`) | `docs/PyCurcit V5_CYCLE_AWARE_API.md` |
| **V5 narrative tutorial** (patterns, modules, signals) | `docs/PyCircuit V5 Programming Tutorial.md` |
| **pyc4.0 `@module` / `Circuit` frontend** | `docs/FRONTEND_API.md`, `docs/tutorial/unified-signal-model.md` |
| **Occurrence cycles on named wires** (`ClockHandle`, `clk.next()`, `m.assign`) | `docs/tutorial/cycle-aware-computing.md`, `docs/cycle_balance_improvement.md` |
| **Testbenches** | `docs/TESTBENCH.md` |
| **IR / lowering expectations** | `docs/IR_SPEC.md`, `docs/PIPELINE.md` |
| **Primitives vs generated code** | `docs/PRIMITIVES.md` |
| **Compiler upgrade rules (agents)** | `docs/updatePLAN.md`, `docs/rfcs/pyc4.0-decisions.md`, root `AGENTS.md` |
| **Diagnostics** | `docs/DIAGNOSTICS.md` |
| **API index** | `docs/api/index.md`, `docs/index.md` |

**Package import:** the Python package name is **`pycircuit`** (lowercase). `PYTHONPATH` must include `compiler/frontend` when running CLI or tests outside an installed package.

---

## Where example designs live

Illustrations of **grammar and structure** are under **`designs/`** and subfolders (path: `/designs` relative to repo root). Study these in **Step 1**:

| Area | Examples (non-exhaustive) |
|------|---------------------------|
| **V5 / cycle-aware style** | `designs/BypassUnit/`, `designs/RegisterFile/`, `designs/IssueQueue/`, many `designs/examples/*/`, `docs/designs_upgrade_to_v5.md` (migration notes) |
| **`@module` + JIT** | `designs/examples/counter/`, `designs/examples/jit_control_flow/`, `designs/examples/hier_modules/` |
| **Testbench layout** | `designs/examples/*/tb_*.py`, `designs/BypassUnit/tb_bypass_unit.py`, `designs/RegisterFile/tb_regfile.py` |
| **Structured IO** | Designs using `spec` / bundles per `docs/SPEC_STRUCTURES.md` |

Mirror the **directory layout** (design file + `tb_*.py` + optional `README.md`) of the example closest to your block’s complexity.

---

## Step 1 — Read programming style documents and examples

**Goal:** Internalize how pyCircuit expresses hardware: static elaboration, allowed Python control flow, registers, memories, and (for V5) **logical occurrence cycles** vs (for pyc4.0 named wires) **ClockHandle** occurrence indices.

**Actions:**

1. Read **`docs/PyCurcit V5_CYCLE_AWARE_API.md`** end-to-end if the block will use **`CycleAwareCircuit` / `CycleAwareDomain`**.
2. Skim **`docs/PyCircuit V5 Programming Tutorial.md`** for idioms (`signal[hi:lo]`, `pyc_CircuitModule`, `with self.module(...)`, `mux`, `domain.next()`).
3. Read **`docs/FRONTEND_API.md`** and **`docs/TESTBENCH.md`** for `@module`, `Circuit`, and simulation contracts.
4. Open **2–3 concrete examples** under `designs/` that match your intended style (V5 vs `@module`).
5. Note **non-negotiables** from `AGENTS.md`: gate-first IR changes; no backend-only semantic fixes.

**Deliverable:** Short notes (in design `README.md` or `ASSUMPTIONS.md`): which authoring mode (V5 vs `@module` vs mixed), and which example design is the **style reference**.

---

## Design specification conversion (prerequisite before Step 2)

**Why:** Autonomous agents and text-first workflows search, diff, and cite specifications most reliably from **plain Markdown**. Raw **`.docx`**, **`.pdf`**, and **`.xlsx`** files are easy for humans to open but are **poor primary sources** for automated analysis: layout noise, embedded objects, multi-sheet structure, and extraction errors make “read the spec” ambiguous.

**Rule:** **Before** analyzing block-specific design documents in **Step 2**, convert every **normative** artifact in those formats into **`.md`** under the block’s documentation tree (e.g. `designs/<Block>/docs/` or `designs/<Block>/docs/converted/`). Treat the Markdown as the **working copy** for implementation and traceability; keep the originals as the legal/normative file where the project requires it.

**Conversion expectations:**

| Source format | Target | Notes |
|---------------|--------|--------|
| **`.docx`** | One or more `.md` files | Prefer structure-preserving export (e.g. Pandoc `pandoc -f docx -t markdown`), then fix headings/lists/tables by hand if needed. |
| **`.pdf`** | `.md` (text + tables as Markdown) | PDF→text quality varies; add a short **header** in each `.md` stating source path, extraction tool, and known gaps (figures, scanned pages). |
| **`.xlsx`** | `.md` per sheet or one `.md` with anchored sections | Export tables to Markdown (scripted or via CSV intermediate); preserve **sheet names** and **row/column** semantics so Step 3 width tables can cite them. |

**File hygiene:**

- Use **stable, searchable names** (e.g. `protocol_sheet1_summary.md`) and a one-line **provenance** header: original filename, date converted, tool/command.
- If a conversion is **partial**, say so in the `.md` and in the Step 2 source table—do not pretend the Markdown is complete.

**Deliverable (enters Step 2):** Markdown digests for all binary specs the block depends on, or an explicit waiver (with owner approval) recorded in `ASSUMPTIONS.md` / `REQUIREMENT_SOURCES.md`.

---

## From converted Markdown to feature list, step docs, and test plan

**Purpose:** Once normative inputs live as **`.md`** under the block (typically `designs/<Block>/docs/converted/`), this subsection defines how to **propagate** that text into **`FEATURE_LIST`**, optional **per-step markdown** (`step1.md` … `step10.md`), **`TRACEABILITY`**, and **`TEST_PLAN`** so agents and reviewers share one chain of evidence. A completed block under **`designs/`** can serve as a **reference layout** (e.g. `feature_list.md`, `workflow_substeps.md`, `run_<block>_verification.py`).

### 1. End-to-end pipeline (recommended order)

| Order | Artifact | Typical location | Tied to step |
|-------|----------|------------------|--------------|
| 1 | **Regenerate digests** when vendor **.docx / .pdf / .xlsx** change | Script under block `docs/` or repo `scripts/`; output `docs/converted/` + `converted/README.md` | After **Design specification conversion** |
| 2 | **Source inventory** with **digest paths** | `REQUIREMENT_SOURCES.md` (or equivalent): each SRC / file → **binary path** + **Markdown path** | **Step 2** |
| 3 | **Assumptions & conflicts** | `ASSUMPTIONS.md`: inferred port directions, CDC, spreadsheet vs prose conflicts | **Step 2–3** |
| 4 | **Port / bus contract** | `PORT_LIST.md`: widths from XLSX-derived `.md` rows; directions from prose digest + assumptions | **Step 3** |
| 5 | **Feature list** | `FEATURE_LIST.md`: see §2 below | **Step 3** |
| 6 | **Sequential + pipelined pseudocode** | `function_list.md`, `step4.md` / `ALGORITHM_*.md` — map digest **chapters** to functions | **Steps 4–5** |
| 7 | **Cycle-aware pseudocode / RTL notes** | `step6.md`, implementation — **Spec trace** comments point at digest headings (and opcode tables in `.md`) | **Step 6** |
| 8 | **Traceability matrices** | `TRACEABILITY.md`: port → F-xxx; F-xxx → code region → **T-xxx** or **TBD** + gap | **Step 7** |
| 9 | **Test plan** | `TEST_LIST.md` / `TEST_PLAN.md`: T-xxx ↔ F-xxx; SYS scenarios ↔ multi-feature; golden vectors from converted tables | **Step 8** |
| 10 | **Increments & log** | `incremental_plan.md`, `IMPLEMENTATION_LOG.md` — tag **F-xxx** per PR; rerun digest script when specs change | **Step 9** |
| 11 | **System test & sign-off** | `system_test_spec.md`, README — P0 **F-xxx** complete or waived | **Step 10** |
| — | **Optional:** `workflow_substeps.md` | Splits a single Step into **2a, 3b, …** for large blocks | Any step |
| — | **Optional:** `cycle_budget.md` | `domain.next()` count, occurrence stages, golden **`pyc.reg`** / MLIR checks | **Steps 5–6**, **9** |

### 2. Structure of `FEATURE_LIST.md` (normative for agent-friendly blocks)

1. **Legend** — priority (P0/P1/P2), column meanings.  
2. **Numbered features F-001…** — each row: name, priority, **Spec trace** = pointer into **converted** `.md` (heading text or stable section id), trigger, observable effect, dependencies.  
3. **Digest index (coarse)** — table: each major spec chapter (`# …` in the primary digest) → **range of F-ids** (or list).  
4. **Heading checklist (full)** — for the **primary** architecture/spec Markdown export, enumerate **every** `#`, `##`, and `###` heading line; each row assigns **one or more F-ids** or **—** (TOC, cover, non-RTL meta only).  
   - **Maintenance rule:** if Pandoc/export adds or renames headings, **update this table** or add **F-xxx** / **gap** entries in `TRACEABILITY.md`.  
5. **Feature → test summary** — which **T-xxx** / SYS cover which **F-xxx** (use **TBD** only with a dated gap).  

Spreadsheet-derived behavior (opcodes, field maps) should cite the **specific** `converted/SRC-xx_xlsx_*.md` file in **Spec trace**, and keep any RTL allowlists (e.g. legal opcodes) **in sync** with that file.

### 3. Block `step1.md` … `step10.md` (optional but recommended)

For complex blocks, mirror this repository’s **10-step** narrative in **block-local** files so block-specific rules (converted paths, **F-xxx** ranges, **heading checklist**, **cycle_budget**, **workflow_substeps**) do not clutter the generic steps above. Each `stepN.md` should:

- Point to **`docs/converted/`** and the **regenerate** command.  
- State which **F-xxx** band or **checklist** rows that step owns or reviews.  
- Cross-link **`PORT_LIST`**, **`FEATURE_LIST`**, **`TRACEABILITY`**, **`TEST_LIST`** as appropriate.

### 4. Tests and automation

- **Directed tests:** at least one **regression-sensitive** case per **F-xxx** before milestone close; build opcode / flit matrices from **Markdown tables** in `converted/` where possible.  
- **Block runner:** optional `run_<block>_verification.py` that executes **stdlib** checks: digests present, key markdown sections exist, `emit_mlir()` or compile smoke, width/contract assertions.  
- **pytest:** optional `test_<block>_steps.py` with markers `step1` … `step10` mirroring the same checks.

### 5. Relation to the generic Steps 2–10 below

**Steps 2–10** in this document remain the **canonical** workflow. The tables in §1–§4 **specialize** those steps for **Markdown-first** specs; when a bullet in Step 3 / 7 / 8 says “every feature”, use **`FEATURE_LIST`** + **heading checklist** as the definition of “every” **heading-level** requirement unless the project explicitly waives finer bullets under a parent **F-xxx**.

---

## Step 2 — Read all block-specific requirement documents

**Goal:** Load every normative input for **this** block (i.e. everything under the block's `docs/` folder, including PDF/XLSX/DOCX **after** they have been converted to Markdown per the section above).

**Actions:**

0. **Confirm** Markdown digests exist (or are waived in writing) for every **`.docx` / `.pdf` / `.xlsx`** the block treats as authoritative—see **Design specification conversion** above. Use the **`.md`** files as the primary text for extraction and agent review.
1. Enumerate all files in the block’s `docs/` folder (spreadsheets, Word, PDF, markdown—including converted `.md` companions).
2. Extract **clock/reset**, **protocol**, **ordering**, **credit/flow control**, **addressing**, **data widths**, **modes**, **error behavior**.
3. Build a **source table**: requirement → document → section/sheet/cell (as traceable as possible), with **both** the original binary path (if retained) **and** the Markdown digest path.

4. **Parity check:** walk the **heading checklist** in `FEATURE_LIST.md` (see **From converted Markdown to feature list, step docs, and test plan** §2) against the primary spec digest; every heading row must resolve to **F-xxx** or **—**; unresolved items → gap register in `TRACEABILITY.md`.

**Deliverable:** `REQUIREMENT_SOURCES.md` or equivalent table in block `README.md`.

---

## Step 3 — Top-level ports, buses, widths, and itemized feature list

**Goal:** Freeze the **external contract** and decompose the spec into **testable features**.

**Actions:**

1. **Port list:** For every top-level **input** and **output**, record: name, direction, width (or parameterized width), clock domain, synchronous/asynchronous, active level, protocol phase (valid/ready, etc.).
2. **Buses:** Group related pins into **logical buses** (e.g. CHI request channel, response channel). Document packing if the RTL bundles vectors.
3. **Top-level functionality:** One concise paragraph describing the block’s role.
4. **Feature list:** Every **function** or **behavior** described in the spec becomes a **numbered feature** (F-001, F-002, …) with: description, triggering condition, expected observable effect on ports, dependency on other features. For blocks using **converted** specs, follow **From converted Markdown to feature list, step docs, and test plan** §2: include **digest index**, **full heading checklist**, and **Spec trace** paths into `converted/*.md`.

**Deliverable:** `PORT_LIST.md` + `FEATURE_LIST.md` (or sections in `README.md`). These are the **single checklist** for Steps 7–10.

---

## Step 4 — Sequential (imperative) behavior, function-oriented decomposition

**Goal:** Describe behavior as an **imperative program** (C/Python-like), **without** committing to hardware module boundaries yet.

**Actions:**

1. Write a **main routine** (e.g. `main_loop()` or “per-cycle work”) that calls **subroutines** with clear names: `accept_request()`, `route_to_peer()`, `update_credit()`, etc.
2. Each subroutine should have **inputs/outputs** expressed as **conceptual data** (structs, not yet ports), and **no hardware partition**.
3. Prefer **pure functional** steps where possible; use **explicit state** variables for anything that must persist cycle-to-cycle.
4. Decompose until each function fits in one screen and has a **single** coherent responsibility.

**Deliverable:** `ALGORITHM_SEQUENTIAL.md` — plain pseudocode or Python-like pseudocode, **no** `domain.next()` yet.

---

## Step 5 — Align sequential description with cycle-aware hardware (pipeline mapping)

**Goal:** Map the imperative algorithm onto **clock cycles** using **`domain.next()`** (and `push`/`pop` in helpers) so that **pipeline stages** and **signal cycle tags** are intentional.

**Actions:**

1. Choose **where each major step** lands in the occurrence timeline: e.g. “Cycle 0: accept & decode; Cycle 1: lookup; Cycle 2: response mux.”
2. In **each subroutine** that becomes hardware, document:
   - **Entry cycle** relative to the caller (e.g. “called at caller’s cycle N”).
   - Whether the callee does **`domain.push()` / internal `next()` / `pop()`** so it does not corrupt the caller’s cycle counter.
3. For **parent/child cycle relations:**
   - Values produced at **child cycle C_child** consumed by **parent cycle C_parent** must satisfy the V5 balancing rules (or explicit `cas(..., cycle=...)` on ports).
4. Registers: use **`domain.state`** for feedback loops; **`domain.cycle`** for explicit single-stage delays; align with `docs/PyCurcit V5_CYCLE_AWARE_API.md`.

**Deliverable:** `ALGORITHM_PIPELINED.md` — same logical steps as Step 4, annotated with **cycle indices** and **push/pop** discipline for nested helpers.

---

## Step 6 — Full cycle-aware algorithm in detailed pseudocode

**Goal:** One document that an implementer can translate **line-by-line** into `CycleAwareCircuit` / helpers.

**Actions:**

1. Use a consistent notation: `// Cycle k` comments, `domain.next()`, `reg = domain.cycle(...)`, `s = domain.state(...)`, `mux(...)`, `cas(domain, wire, cycle=...)`.
2. Include **reset behavior** and **idle** behavior.
3. Include **back-pressure** and **stall** paths if the spec defines them.
4. Mark **optional** or **parameterized** branches clearly.

**Deliverable:** `ALGORITHM_CYCLE_AWARE_PSEUDOCODE.md` — complete pseudocode for the agreed scope (can be phased by milestone).

---

## Step 7 — Specification and feature traceability check

**Goal:** Prove **coverage**: every port behavior and every feature from Step 3 is realized in Step 6 (and planned implementation).

**Actions:**

1. **Port coverage matrix:** each port (or bus field) → pseudocode region / function → feature ID(s).
2. **Feature coverage matrix:** each F-xxx → pseudocode region → test case ID (placeholder for Step 8).
3. Re-read original specs; log **gaps** or **TBD** items explicitly (do not silently omit). For Markdown-first blocks, ensure **every F-xxx** from the **heading checklist** appears in the feature matrix with a **test ID** or a **dated gap** (see **From converted Markdown …** §1).

**Deliverable:** `TRACEABILITY.md` with two matrices and an explicit **gap list** (empty if complete).

---

## Step 8 — Itemized test plan (every signal and every feature)

**Goal:** A test plan where **no port pin** and **no feature** is untested.

**Actions:**

1. For **each port** (or grouped bus): at least one directed test that exercises **0→1**, **toggle**, **hold**, or **protocol sequence** as appropriate.
2. For **each feature** F-xxx: at least one scenario that **fails** if the feature is removed (regression-sensitive).
3. Classify tests: **reset**, **smoke**, **directed**, **stress**, **corner** (overflow, credit exhaust, simultaneous channels).
4. Map each test to **`@testbench`** steps or cosim checks per `docs/TESTBENCH.md`.

5. **Coverage rule (Markdown-first blocks):** each **F-xxx** in `FEATURE_LIST.md` (including ranges filled after the **heading checklist**) must have a planned **directed** or **system** test before tape-out, unless waived in `TRACEABILITY.md`; stimulus/expected values may cite **`converted/*.md`** tables.

**Deliverable:** `TEST_PLAN.md` with test IDs (T-001, …), stimulus sketch, expected outputs, and links to features/ports.

---

## Step 9 — Incremental implementation plan (feature-by-feature)

**Goal:** Grow the design **safely**: shell → one feature → test → repeat.

**Actions:**

1. **Increment 0:** Top-level **empty** (or pass-through) design with **all ports declared** and tied to safe defaults; compiles and emits MLIR; TB applies reset and idle.
2. For each feature F-xxx in dependency order:
   - Implement **only** that feature (or minimal supporting glue).
   - Add or extend **tests** from `TEST_PLAN.md` for that feature.
   - Run **full regression** for all previous tests (must stay green).
3. Record **increments** in `IMPLEMENTATION_LOG.md`: date, feature ID, files touched, tests added, command line used.

**Deliverable:** Ordered **backlog** of increments + log. Prefer small PR-sized steps.

---

## Step 10 — System test (end-to-end, combinations)

**Goal:** Validate the **whole block** under realistic combined traffic, and re-verify **port** and **feature** coverage.

**Actions:**

1. Define **system scenarios** that stress **multiple features together** (e.g. concurrent requests + credit pressure + error injection).
2. Re-run **full traceability**: confirm `TRACEABILITY.md` and `TEST_PLAN.md` have **no unchecked rows**.
3. Optional: long-run **pseudo-random** stimulus if the TB framework supports it; compare to golden or invariants (no deadlock, no X on outputs, etc.).
4. Document **sign-off criteria** in block `README.md`.

**Deliverable:** `SYSTEM_TEST.md` or README section listing scenarios, commands, and expected results; update `TRACEABILITY.md` status to **closed**.

---

## Relationship to block-specific projects

- For any block, block-specific specs live under `designs/<Block>/docs/`. Start Step 2 there after Step 1, **after** any **DOCX/PDF/XLSX → Markdown** conversion for files you will analyze in depth.
- Existing completed blocks under `designs/` can serve as worked examples of the **From converted Markdown to feature list, step docs, and test plan** pipeline (including **heading checklist**, **`workflow_substeps.md`**, **`cycle_budget.md`**, and **`run_<block>_verification.py`**).
- For new blocks, substitute the appropriate `designs/<Block>/docs/` (or project doc root) and reuse the same artifact names where practical.

## Relationship to repository policy

- If a change requires **new IR semantics** or **stricter legality**, follow **`AGENTS.md`**: extend MLIR verifiers/passes **before** relying on backend behavior.

---

**Copyright (C) 2024–2026 PyCircuit Contributors**
