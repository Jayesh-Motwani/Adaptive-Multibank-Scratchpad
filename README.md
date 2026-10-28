# Look-ahead and runtime-adaptive multi-bank scratchpad

This repository contains a pure-Verilog RTL implementation, self-checking
testbench, controlled simulator sweep, measured figures, review slides, and a
two-column research report. The proposed mechanism is a lightweight
hysteresis-based runtime bank-activation policy: four physical banks exist,
while the allocation limit changes among two, three, and four according to
compute starvation. A lower limit does not discard a tile already in a bank.
The performance extension adds completion-aware loader and MAC handoffs,
which remove controller idle gaps using the same banks and arithmetic
resources. Both handoff controls default to zero to preserve the original
experiments.

## What is implemented

- `rtl/sync_ram.v`: parameterized synchronous behavioral RAM.
- `rtl/mac_engine.v`: synchronous-read tile MAC consumer.
- `rtl/scratchpad_controller.v`: explicit EMPTY/LOADING/READY/COMPUTING bank
  states, counters, and five policies: one bank, two-bank ping-pong, fixed
  four-bank availability, static cyclic multi-bank proxy, and runtime depth.
- `tb/tb_controller.v`: checks every tile ID and MAC result plus occupancy,
  allocation eligibility, counters, and mode accounting.
- `scripts/run.py`: compiles Icarus, runs regression and matrix, saves raw
  logs, VCD, and CSV. Python invokes the Verilog simulator; it never models
  hardware behavior in place of RTL.
- `scripts/analyze_results.py`: independent active-cycle and baseline
  preservation checks; parses the measured phase VCD mode trace.
- `scripts/generate_plots.py`: regenerates 14 PNG/PDF figures from CSV.
- `scripts/generate_paper_diagrams.py`: regenerates three vector diagrams for
  the report, with PNG previews.
- `scripts/evaluate_lookahead.py`: verifies legacy preservation and 148 new
  correctness/ablation cases, checks exact service intervals, and writes
  separate look-ahead results.
- `scripts/generate_lookahead_figures.py`: plots measured cycle comparisons
  and the acceptance/completion timeline.
- `diagrams/*.mmd`: source-controlled architecture, FSM, and timing diagrams.
- `presentation/review_slides.md` and `presentation/review_slides.pptx`:
  24-slide review narrative with editable charts and tables.
- `docs/final_report/paper.tex`, `references.bib`, and `paper.pdf`:
  two-column report with architecture, state and gate diagrams, an algorithm,
  handoff timing, comparison tables, and references. The existing slides
  describe the original depth study; the report includes the new extension.

## Results at a glance

With both look-ahead controls enabled, **adaptive versus original fixed-four**
cycles are **522 vs 713** for 64 balanced tiles (**26.79% fewer**), **925 vs
983** for variable latency (**5.90% fewer**), and **1808 vs 1991** for phase
changes (**9.19% fewer**). Per-tile load and MAC service times are unchanged.
Applying the same optimization to fixed four gives **522, 917, and 1770**
cycles respectively. The cycle gain comes from handoff scheduling; adaptive
depth still has a penalty against equally optimized fixed four. See
[`docs/lookahead_results.md`](docs/lookahead_results.md) and
[`docs/lookahead_design.md`](docs/lookahead_design.md) for the ablations,
reproduction commands, generic synthesis, and clock-frequency limits.
All **129 original cases retain 13 checked metrics** with the flags disabled;
**84 additional correctness cases and 64 measurements pass**.

The original bank-depth experiment follows (both handoff flags disabled).
All **14/14 functional tests** passed. All **129/129 performance runs**
completed. The 103 pre-adaptation runs retained identical core metrics after
the RTL extension. For 32 tiles at fixed 8/8 latency, single/ping-pong/fixed
four-bank needed **640/361/361 cycles**. At variable base 8/8 they needed
**922/539/497 cycles**; scaling reached 497 at three banks and saturated.

For 64 stable compute-bound or balanced tiles, runtime depth exactly matched
fixed-four-bank cycles while averaging **2.022** or **2.045** eligible banks.
For 64 variable-latency tiles, runtime took **1025** versus **983** fixed-four
cycles and averaged **2.500** banks. For 96 phase-changing tiles it took
**2033** versus **1991** cycles and averaged **2.582** banks. The phase VCD
shows a rise to four and return to two. Average active bank limit is an
effective buffering-depth metric; **no power savings were measured**.
Fixed four-bank availability and the static cyclic four-bank proxy matched
in tested cases, so this model does not show a distinct scheduling advantage
at equal bank count. See `docs/results_and_discussion.md` for all limits.

## Prerequisites

- Icarus Verilog (`iverilog`, `vvp`). The driver checks `IVERILOG` and `VVP`
  environment variables, then `tools/iverilog/bin`, then `PATH`.
- Python 3.11+ for orchestration, CSV, analysis, and plots.
- Matplotlib 3.10.7 for figures (`requirements.txt`). Install into
  `tools/pydeps` with `python -m pip install --target tools/pydeps -r
  requirements.txt`, or make it available in Python's environment.
- Node.js and `@oai/artifact-tool` only to rebuild the editable PPTX.
- LaTeX with `article`, `graphicx`, `amsmath`, `booktabs`, `geometry`,
  `array`, `url`, and `lmodern` for the report; IEEEtran is optional on Overleaf.
- Optional GTKWave to inspect VCD. Mermaid-compatible renderer for diagrams.

On Windows, the workspace-local Icarus 14 package was retrieved from
`https://bleyer.org/icarus/iverilog-v14-20260804-x64_setup.exe`, verified
against SHA-256
`5d65c90c269af75c12ba6e9af6ceb0d64511ea8913d0b2a28eb82e697521cf17`
(the published Scoop manifest), and extracted into `tools/iverilog` with an
already installed 7-Zip utility. The installer itself was not used. On Linux,
install Icarus through the distribution package manager and use `PATH`.

## Reproduce the evidence

From the repository root:

```text
python scripts/run.py test
python scripts/run.py experiments
python scripts/analyze_results.py
python scripts/generate_plots.py
python scripts/generate_paper_diagrams.py
```

To reproduce the additional scheduling improvement and its figures:

```text
python scripts/evaluate_lookahead.py
python scripts/generate_lookahead_figures.py
python scripts/verify_paper_results.py
python scripts/generate_primary_results.py
```

These commands write `lookahead_*.csv` and leave the original
`results_summary.csv` intact. Set both `lookahead_load=1` and
`lookahead_compute=1` in `run_case` to use the new scheduler.
The paper's main comparison uses `paper_result_audit.csv`, produced by
20 fresh RTL runs checked against the measured matrix. Individual
`paper_audit_*.log` files in `results/raw` show the parameter flags, tile
checks, and reported cycle counts. The proposed phase trace uses the
LH-AD VCD and is checked against its measured mode-occupancy counters.

The same five steps are in `scripts/run_all.ps1` and `scripts/run_all.sh`.
Where GNU Make is installed, `make test`, `make experiments`, `make analyze`,
`make plots`, and `make all` provide corresponding targets. Windows on this
host did not have `make`; direct Python commands above were actually used.
`make all` additionally builds the presentation and report, so it requires
the optional Node/LaTeX tools. The simulation workflow needs no FPGA toolchain
or proprietary IP.

To run one specific configuration, use the reusable Python API in a console:

```python
from scripts.run import run_case
print(run_case("one_case", "manual", 4, 4, 64, 4, 8, 8,
               variable=1, wave=True))
```

The policy number 4 selects runtime depth; policy 2 is fixed availability.
Logs are in `results/raw`, CSVs in `results/csv`, figures in
`results/plots`, and waveform files in `results/waveforms`. Open
`adapt_phase_runtime_adaptive.vcd` in GTKWave and inspect
`active_bank_limit`, `stall_count`, `observation_counter`, `bank_state_debug`,
`load_busy`, `compute_busy`, `tile_done`, and tile result signals. The plotted
mode sequence is also in `results/csv/mode_trace.csv`.

## Synthesis-derived gate diagrams

The actual Yosys gate schematics are in `results/plots`: the compact
[`sync_ram_2x1_gate.svg`](results/plots/sync_ram_2x1_gate.svg), the larger
[`sync_ram_4x4_gate.svg`](results/plots/sync_ram_4x4_gate.svg), and the
[`active_limit_gate_cone.svg`](results/plots/active_limit_gate_cone.svg)
from the adaptive controller. The full flattened gate netlist is in
`results/netlist/scratchpad_gate.v` and `.json`; its full graph is also
provided as a DOT file. See
[`docs/gate_level_diagrams.md`](docs/gate_level_diagrams.md) for the exact
parameter choices, synthesis limits, and a one-command reproduction path.

## Report and slides

The paper source is [paper.tex](docs/final_report/paper.tex). It searches both
`../../results/plots/` for local compilation from the report directory and
`results/plots/` for Overleaf's project-root compilation. **For Overleaf,
upload the `docs/final_report` and `results/plots` folders with their relative
structure intact, then set `docs/final_report/paper.tex` as the main file.** The
source uses a standard two-column `article` layout because IEEEtran was not
installed in the local MiKTeX setup. The source and existing PDF compiled
locally with MiKTeX; the Codex built-in editor compiler reported a Windows
platform-directory error. Overleaf can compile the source with the listed
packages and relative figure paths.

To rebuild the local PDF from the report directory:

```text
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
```

The PowerPoint build source is `presentation/build/build_deck.mjs`; it uses
the Codex bundled Node and `@oai/artifact-tool` runtime, and was validated
as a 24-slide deck. The final PPTX is already in `presentation`. The deck
contains 5 native editable charts, 3 editable tables, and the measured VCD
mode waveform as an image.
