# Completion-aware handoffs over the existing scratchpad

The performance extension removes controller idle clocks between loads and
MAC jobs. It keeps the same physical bank count, RAM ports, operand stream,
single loader, and single MAC. Transfer targets, compute targets, useful
MAC operations, and final result registration are unchanged.

`LOOKAHEAD_LOAD=1` lets the loader accept its next descriptor on its current
transfer's finishing edge. It can allocate an EMPTY bank or reclaim the bank
whose computation completes on that edge. `LOOKAHEAD_COMPUTE=1` presents the
next tile descriptor directly to the MAC when idle or finishing. Its bank
may be READY or completing a load on the issue edge. Both parameters default
to zero, preserving the original implementation and its measurements.

The MAC exports `finishing` only when its programmed target has elapsed and
all synchronous RAM responses have been accumulated. `CHAIN_START` permits
the old result to be captured while the next accumulator and descriptor are
initialized. The first read of the new job occurs on the following edge,
so a final RAM write on the issue edge is safe. The controller frees the
old compute bank on `finishing` in look-ahead mode, separately from delayed
result notification. This prevents a later notification from freeing the
new job's bank. Same-edge completion and allocation can collapse logical
bank-state transitions, while each bank still has only one active owner.

Runtime policy 4 retains the original 32-cycle 8/2 threshold rule. The
allocation limit also guards newly reclaimed banks; a limit decrease still
allows existing high-bank tiles to drain. No predictive depth policy or
latency threshold tuning was added to obtain the measured cycle reduction.

## Reproduce

From the project root:

```powershell
python scripts/run.py test
python scripts/evaluate_lookahead.py
python scripts/generate_lookahead_figures.py
python scripts/verify_paper_results.py
python scripts/generate_primary_results.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/synthesize_lookahead.ps1
```

Simulation uses the existing local Icarus installation. Plotting uses the
existing Matplotlib dependencies. Generic synthesis uses the project-local
YoWASP/Yosys installed for the gate diagrams. The paper and the two new
figures are supplied ready for Overleaf; the existing relative figure paths
continue to work.

To run the proposed adaptive variant directly:

```python
from scripts.run import run_case
row = run_case("my_lookahead_case", "manual", 4, 4, 64, 4, 8, 8,
               variable=1, lookahead_load=1, lookahead_compute=1,
               trace_handoff=True, wave=True)
print(row["total_cycles"])
```

Use `policy=2` in the same call for the equally optimized fixed-four control.
The full experiment varies both handoff flags independently for both
policies. `results/csv/lookahead_results.csv` contains all 64 ablation rows,
including the loader-only adaptive case that gets slower.

## Evidence and comparison limits

See [measured results](lookahead_results.md). The old 129-case matrix is
replayed with both flags disabled and compared against 13 archived metrics
per case. Another 84 configurations cover one-bank reuse, non-power-of-two
bank counts, minimum service targets, short workloads, larger tiles, and
changing latency. Every job's issue and completion is traced and checked
against independent service-time formulas. The complete fixed-depth
look-ahead cases also match an independent finite-buffer FIFO schedule.
The pre-extension sources and CSV/raw results are preserved in
`results/baseline_snapshot/pre_lookahead_sources_and_metrics.zip`.

The adaptive look-ahead design beats the **original** fixed-four controller
in cycle count. Giving the same handoff optimization to fixed four remains
faster in irregular workloads. The performance contribution is therefore
handoff scheduling; depth restriction is an independent resource-eligibility
tradeoff. The conference manuscript reports the complete proposed
controller against the registered-handoff fixed-four baseline. Component
controls remain in the project datasets and this engineering documentation.

At four words per bank and fixed 8/8 targets, generic synthesis gives 3477
logic/register cells for original fixed four, 3609 for look-ahead fixed four,
and 4713 for look-ahead adaptive, excluding five scope metadata records in
each netlist. The logs and `results/csv/lookahead_synthesis.csv` document
zero check problems and no inferred latches. Full synthesized Verilog/JSON
outputs are in `results/netlist/lookahead_*_gate.*`. Counts include exposed
instrumentation and flip-flop RAMs; they are not physical area estimates.

The completion-to-issue combinational path may affect clock frequency.
Cycle counts alone do not prove a speedup in nanoseconds, energy reduction,
or improved power. No clock gating, PDK, SRAM macro, or physical timing model
is introduced in this extension. Existing slides and legacy plots retain
the original bank-depth experiment; the updated paper and look-ahead files
describe the new scheduling evidence.
