# Experimental methodology

All architectures share the same Verilog RAM and MAC, deterministic operands,
tile order at input, single transfer interface, and synchronous clock. Each
run recompiles the same RTL with only testbench parameters changed. Icarus
Verilog 14.0 compiled with `-g2005`; `vvp` ran each binary. The testbench
checks every tile's MAC value and tile identity before it prints `STATUS=PASS`.
Python invokes tools and parses logs but does not simulate hardware.

The original matrix has fixed balanced, memory-bound, and compute-bound
settings; variable per-tile latency; tile counts 4–64; tile sizes 8–64;
and adaptive bank counts 2, 3, 4, 6, and 8. Its 103 runs are archived before
the extension. The new matrix adds 20 controlled adaptation runs across
stable compute-bound, balanced, variable-latency, and three-phase workloads.
Six supplementary runs equalize physical RAM word counts between two banks
with eight words each and four banks with four words each.

The equal-word study keeps tile size four and only one tile per bank. Thus,
extra words in a large ping-pong bank are unused, while four smaller banks
can hold four independent tiles. It controls *physical word count*, not usable
tile slots, and cannot isolate all storage effects.

For each scenario, compare single, ping-pong, fixed four-bank availability,
runtime adaptive, and the static cyclic proxy where specified. `run.py`
records simulator stdout in `results/raw`, computes CSV metrics only from
those logs, and emits VCD for representative cases. `analyze_results.py`
checks independent analytical cycle sums and the preserved baseline snapshot.
`generate_plots.py` reads CSV and writes PNG/PDF figures. No manually entered
performance values appear in plot code.

The observed clock interval begins just after reset and includes initial
fill and controller handoff. Transfer latency is an effective tile-load time,
not an electrical DRAM model. Compute latency includes one synchronous RAM
read per operand pair plus optional idle padding; both targets have structural
minimums documented in `architecture.md`.
