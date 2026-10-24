# Gate-level diagrams from the Verilog

The diagrams below show the original handoff mode (the new look-ahead
parameters default to zero). New matched-parameter synthesized netlists
for original fixed four, look-ahead fixed four, and look-ahead adaptive
are supplied as `results/netlist/lookahead_*_gate.v` and `.json`. Run
`scripts/synthesize_lookahead.ps1` to regenerate those netlists and their
cell/check summary in `results/csv/lookahead_synthesis.csv`.

These are **synthesis-derived netlists and schematics**, generated from the
project RTL by Yosys 0.69 and rendered by NetlistSVG. They are not hand-drawn
architecture sketches. The source files are `rtl/sync_ram.v`,
`rtl/mac_engine.v`, and `rtl/scratchpad_controller.v`.

| Artifact | What it shows |
| --- | --- |
| [`sync_ram_2x1_gate.svg`](../results/plots/sync_ram_2x1_gate.svg) | Readable complete gate schematic of the actual `sync_ram` RTL with `DATA_WIDTH=1`, `ADDR_WIDTH=1` (two words). Its two storage flip-flops, output flip-flop, address logic, and read mux are visible. |
| [`sync_ram_4x4_gate.svg`](../results/plots/sync_ram_4x4_gate.svg) | Complete gate schematic of the same RTL with four 4-bit words. |
| [`active_limit_gate_cone.svg`](../results/plots/active_limit_gate_cone.svg) | Zoomable one-clock logic cone of `active_bank_limit[2:0]` in the full adaptive controller. It retains 186 netlist cells and exposes 105 fan-in bits at the sequential boundary. |
| [`scratchpad_synth_hierarchy.svg`](../results/plots/scratchpad_synth_hierarchy.svg) | Complete parameterized pre-flattening hierarchy. It is large and best viewed with vector zoom. |
| [`scratchpad_gate_full.dot`](../results/netlist/scratchpad_gate_full.dot) | Complete flattened controller gate graph; too dense for a paper page. |
| [`scratchpad_gate.v`](../results/netlist/scratchpad_gate.v) and [`scratchpad_gate.json`](../results/netlist/scratchpad_gate.json) | Machine-readable full flattened generic gate netlist. |

The complete controller synthesis sets `POLICY=4` and `NUMBER_OF_TILES=64`;
the remaining RTL defaults give four physical banks, 8-bit operands, a
four-element tile, and fixed 8-cycle transfer and compute targets. It has
4,758 logic/register cells and five Yosys scope-information records. Yosys
reported zero `check` problems. The tiny RAM view is a separate parameter
instance for readability and **is not the full controller circuit**. The
4-by-4 RAM view provides an intermediate scale.

The control-cone extractor (`scripts/extract_active_limit_cone.py`) copies
existing gate cells and connections from `scratchpad_gate.json`. It stops at
other flip-flops and presents their outputs as boundary inputs; this is not
a complete standalone implementation of the controller. It does not invent
gates or wires.

## Regenerate on Windows

From the project root, with Python, Node.js, and npm available:

```powershell
python -m pip install --target tools/yowasp yowasp-yosys
npm install --prefix tools/netlistsvg netlistsvg@1.0.2 sharp@0.34.4
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/generate_gate_diagrams.ps1
```

The driver runs the checked-in Yosys scripts, extracts the controller cone,
renders vector schematics, and rasterizes the two RAM schematics for pdfLaTeX.
The paper embeds `results/plots/sync_ram_2x1_gate.png`; the SVG is the
zoomable primary output. Synthesis logs are in `results/netlist`.

No standard-cell library, PDK, SRAM macro, placement, or transistor sizing
was supplied. These are **generic gate-level** views, not transistor-level
layouts, area estimates, or timing/power results. A transistor-level drawing
would require a specified cell library or circuit implementation and a
different mapping flow.
