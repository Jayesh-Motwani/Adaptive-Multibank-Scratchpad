# Project context: adaptive multi-bank scratchpad

Last checked against the source and evidence: **2026-10-23**.

For the implementation tutorial, cycle walkthroughs, and professor questions,
read `docs/review_guide.md`. `docs/viva_notes.md` is the shorter revision sheet.

## 1. What this project implements

A synthesizable Verilog model of a tiled dot-product engine with one loader,
four physical scratchpad banks, one bank-selection mux, and one MAC engine.
The controller manages bank ownership and overlaps loading with computation.

The current proposed controller combines:

1. Runtime allocation eligibility: permit new tiles in banks below an
   `active_bank_limit` of two, three, or four.
2. Completion-aware handoffs: accept the next load/MAC job on a finishing
   edge, reducing gaps between jobs.

The paper compares this complete controller against the specified **Fixed 4**
baseline, which keeps four banks eligible and uses registered handoffs.
The performance claim applies to this pair of implementations. Restricting
bank eligibility alone is not the source of the cycle reduction.

This is a cycle-level RTL architecture study. The top module internally
generates deterministic activation/weight values and synthetic service-time
profiles. It does not connect to a real DRAM, DMA, AXI bus, CPU, or complete
neural-network application.

## 2. Team and manuscript constraints

| Author | Email |
| --- | --- |
| Jayesh Motwani | jayesh.motwani2024@vitstudent.ac.in |
| Kia Wadher | kia.chetanwadher2024@vitstudent.ac.in |
| Vedansh Belwal | vedansh.belwal2024@vitstudent.ac.in |

- Edit the existing `docs/final_report/paper.tex` in place.
- The conference limit is **nine pages including references**; the current
  locally compiled `paper.pdf` has nine pages.
- The manuscript's main comparison is **Fixed 4 versus Proposed**.
- LH-F4/component ablation material was removed from the manuscript at the
  user's request. Additional engineering controls remain in the project data.
- Use research-paper prose. Do not narrate revision history or describe
  results as "new" or "preserved original" results.
- Figure captions describe the circuit or result, not drawing-tool credits.
- Retain the architecture, state diagrams, algorithm, gate schematic, and
  measured results. Do not use image generation for a gate-level schematic.
- Preserve the working RTL, previous baselines, raw evidence, and report
  infrastructure when making further changes.

## 3. Configuration that selects the claimed proposed design

| Parameter | Fixed 4 baseline | Proposed controller |
| --- | ---: | ---: |
| `POLICY` | 2 | 4 |
| `BANK_COUNT` | 4 | 4 |
| `LOOKAHEAD_LOAD` | 0 | 1 |
| `LOOKAHEAD_COMPUTE` | 0 | 1 |
| Initial allocation limit | 4 | 2 |

**`POLICY=4` alone does not select the complete proposed design.** Both
look-ahead parameters must also be one. RTL defaults retain the baseline
timing; several historical commands/results intentionally use those defaults.

Other implemented policies are 0 = single buffering, 1 = ping-pong, and
3 = static cyclic multi-bank mapping. Policies are elaboration parameters;
only `active_bank_limit` changes dynamically during execution.

Main experiments use unsigned eight-bit operands, four operand pairs per
tile, and four words per bank (`ADDR_WIDTH=2`). A word packs an activation
and weight, so it is **16 bits**, not eight. Four banks therefore contain
`4 × 4 × 16 = 256 bits = 32 bytes` of modeled storage. The top-level RTL
default is `ADDR_WIDTH=3`; the Python driver overrides it for these runs.

## 4. Source and artifact map

| File/folder | Role |
| --- | --- |
| `rtl/sync_ram.v` | Enabled synchronous read and write storage primitive. |
| `rtl/mac_engine.v` | Read-response pipeline, unsigned multiply/accumulate, service target, completion and chained start. |
| `rtl/scratchpad_controller.v` | Tile source, service profiles, bank FSMs, arbiters, loader, depth policy, handoffs, counters. |
| `tb/tb_controller.v` | Clock/reset, golden arithmetic, issue/completion scoreboards, ownership assertions, metrics, VCD. |
| `scripts/run.py` | Icarus/VVP invocation and original functional/performance matrix. |
| `scripts/evaluate_lookahead.py` | Reference regression, stress configurations, service-interval checks, extended experiments. |
| `scripts/verify_paper_results.py` | Source-hash check and 20 audited simulation reruns, including supporting control configurations. |
| `scripts/analyze_results.py` | Independent accounting checks for the original matrix and its mode trace. |
| `scripts/generate_primary_results.py` | Current Fixed 4/Proposed plot and proposed phase trace. |
| `scripts/generate_lookahead_figures.py` | Handoff timing figure and separate engineering comparison figure. |
| `scripts/generate_plots.py` / `generate_paper_diagrams.py` | Other measured plots and architecture/state diagrams. |
| `scripts/*synthesis*.ys` | Yosys synthesis configurations. |
| `scripts/synthesize_lookahead.ps1` / `summarize_lookahead_synthesis.py` | Synthesize matched variants and validate/count generic cells. |
| `scripts/generate_gate_diagrams.ps1` | RTL/netlist-to-SVG/PNG schematic pipeline. |
| `results/raw` | Actual simulator logs, including every tile check. |
| `results/csv` | Parsed measurements, validation manifests, and event/mode traces. |
| `results/waveforms` | VCD files; choose the proposed waveform explicitly. |
| `results/netlist` | Synthesized Verilog/JSON, full DOT graph, synthesis logs. |
| `results/plots` | Figure PDFs, PNGs, and SVGs. |
| `results/baseline_snapshot` | Preserved source/metric/raw-log archives. |
| `presentation` | Existing review deck/build source; much of the deck describes the earlier depth-only study. |
| `docs/final_report/paper.tex` / `paper.pdf` | Current conference manuscript and local PDF. |
| `tools` | Project-local Icarus, plotting dependencies, YoWASP/Yosys, and schematic-rendering dependencies. |

## 5. Measurements to know

All pairs below use the same tile values, per-tile service targets, bank
count, single loader, and single MAC. Total cycles include fill and final
result retirement.

| Workload | Fixed 4 cycles | Proposed cycles | Cycle reduction | Proposed average limit |
| --- | ---: | ---: | ---: | ---: |
| Compute-bound, 64 tiles, base 8/20 | 1481 | 1290 | 12.90% | 2.025 |
| Balanced, 64 tiles, base 8/8 | 713 | 522 | 26.79% | 2.061 |
| Memory-bound, 64 tiles, base 32/8 | 2123 | 2058 | 3.06% | 3.953 |
| Variable latency, 64 tiles, base 8/8 | 983 | 925 | 5.90% | 3.069 |
| Phase changes, 96 tiles | 1991 | 1808 | 9.19% | 2.619 |

Authoritative inputs: `lookahead_results.csv` and `paper_result_audit.csv`
under `results/csv`. `results_summary.csv` is the historical registered-
handoff matrix; it does not contain the proposed look-ahead results.

The phase plot for the proposed design uses
`paper_audit_lookahead_phase_p4_l1c1.vcd`, not
`adapt_phase_runtime_adaptive.vcd` (the latter has the older 2033-cycle run).
Its execution-cycle transitions are:
`(0,2), (32,3), (64,2), (672,3), (704,4), (1216,3), (1248,2)`.
Occupancy is 1200/96/512 clocks at limits 2/3/4, totaling 1808 clocks.

Matched generic synthesis (`ADDR_WIDTH=2`, fixed 8/8, 64 tiles) reports:

| Configuration | Logic/register cells | Register bits |
| --- | ---: | ---: |
| Fixed 4 | 3477 | 595 |
| Proposed | 4713 | 864 |

The proposed generic cell count is 35.55% larger. Counts include
instrumentation and flip-flop RAM mapping and exclude five scope metadata
records per netlist. They are not technology-specific SRAM area or timing.

## 6. Verification status and what it means

- 14 original functional parameterizations pass.
- 129 historical configurations retain 13 checked reference metrics with
  the handoff controls disabled.
- 84 additional correctness stress configurations pass.
- 64 extended performance/control configurations pass.
- The 20-case audit reproduces its stored measurements and checks source
  hashes, arithmetic, exactly-once issue/completion, ownership, accounting,
  and service intervals.
- These counts overlap in scenario coverage; do not add them and call the
  sum independent workloads or random tests.
- On **2026-10-23**, the source hashes matched the validated manifests,
  and the 14-case functional suite plus 20-case audit were rerun successfully.

Primary evidence manifests: `results/csv/lookahead_validation.json` and
`results/csv/paper_result_audit.json`. Their source hashes bind results to
the RTL/testbench/driver versions. They do not constitute a formal proof.

## 7. Commands

Run from the project root in normal PowerShell:

```powershell
python scripts/run.py test
python scripts/verify_paper_results.py
```

Explicit proposed variable-latency case:

```powershell
@'
from scripts.run import run_case
r = run_case("review_proposed_variable", "review", 4, 4, 64, 4, 8, 8,
             variable=1, lookahead_load=1, lookahead_compute=1,
             trace_handoff=True, wave=True)
print(r)
'@ | python -
```

The expected proposed cycle count is 925. For Fixed 4 use `policy=2` and
both look-ahead flags zero; the matched count is 983.

Full evidence regeneration, when needed:

```powershell
python scripts/run.py experiments
python scripts/analyze_results.py
python scripts/evaluate_lookahead.py
python scripts/verify_paper_results.py
python scripts/generate_primary_results.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/synthesize_lookahead.ps1
```

`run_all.ps1` and `run_all.sh` cover the earlier simulation/analysis/plot
workflow; they do not by themselves run the look-ahead extension.
`make lookahead` covers the extended evaluation/audit/figure workflow.
The Python driver honors `IVERILOG`/`VVP`, then checks `tools/iverilog/bin`,
then `PATH`. Restricted sandboxes may prevent overwriting existing build
artifacts; the normal host PowerShell run succeeded during the review check.

## 8. Interpretation boundaries

- All four physical banks remain instantiated and clocked. Eligibility is
  not clock gating, power gating, or physical RAM resizing.
- Busy-cycle utilization includes service padding and pipeline overhead;
  it is not the fraction of clocks performing a useful multiply.
- The model has no real DRAM protocol or measured external-memory traces.
- The operands are positive deterministic values, not trained model data.
- No FPGA board, ASIC silicon, physical timing closure, or power analysis
  was used to obtain the cycle results.
- The proposed design improves over the specified Fixed 4 implementation.
  Do not claim that adaptive restriction inherently beats every controller
  with four banks or that the result is an adaptation-only speedup.
- The tiny RAM gate figure is a reduced parameter instance of the same RAM
  source, not the entire four-bank accelerator.
- Existing slides and older notes may describe depth-only behavior. Use
  the current paper, this file, and `docs/review_guide.md` for the review.

## 9. Report compilation

The report uses standard two-column `article` LaTeX with Latin Modern fonts.
Local MiKTeX builds `paper.pdf`; two passes resolve references. Overleaf
requires the existing `docs/final_report` and `results/plots` folder structure,
with `docs/final_report/paper.tex` selected as the main file.
The built-in editor compiler has been unable to resolve the external figure
paths; successful local compilation is separately verified.
