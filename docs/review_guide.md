# Implementation and professor-review guide

Checked against source and evidence on **23 October 2026**. Use
[context.md](../context.md) for the project map and
[viva_notes.md](viva_notes.md) for quick revision.

## 1. Your opening explanation

> We implemented a parameterized Verilog controller for a tiled dot-product
> engine with one loader, four independent scratchpad banks, and one MAC.
> Loading and computing overlap on different banks. Our proposed controller
> changes the bank allocation limit between two, three, and four using
> observed starvation, and uses completion-aware handoffs to reduce gaps
> between jobs. We verify every tile result, exactly-once issue/completion,
> ownership, service intervals, and cycle accounting in RTL simulation.
> Balanced execution drops from 713 to 522 cycles against our specified
> registered-handoff Fixed 4 baseline. Operands and service delays are
> synthetic; we have not measured a board, fabricated chip, or real DRAM.

The proposed design combines **allocation adaptation and handoff
scheduling**. Restricting eligible banks alone is not the explanation for
the cycle reduction.

## 2. What actually exists

```text
Internal deterministic operand generator
                 |
          one loader / write selection
                 |
     +-----------+-----------+-----------+
     | bank 0    | bank 1    | bank 2    | bank 3
     | sync_ram  | sync_ram  | sync_ram  | sync_ram
     +-----------+-----------+-----------+
                 |
         registered RAM outputs -> bank mux
                 |
       one unsigned multiplier + accumulator
                 |
         result value + tile ID + tile_done

Controller: bank states/tags, allocation/dispatch selection,
            service counters, runtime limit, measurement counters
```

The synthesizable files are [sync_ram.v](../rtl/sync_ram.v),
[mac_engine.v](../rtl/mac_engine.v), and
[scratchpad_controller.v](../rtl/scratchpad_controller.v).
[tb_controller.v](../tb/tb_controller.v) is the simulation environment;
it is not synthesized into the accelerator.

| Main-experiment quantity | Value |
| --- | --- |
| Operand | 8 bits, unsigned |
| RAM word | `{activation, weight}`, 16 bits |
| Tile | 4 operand pairs |
| Result | 32-bit dot product |
| Physical banks | 4 |
| Address width passed by driver | 2 bits |
| Words per bank | 4 |
| Total operand storage | 4 × 4 × 16 = 256 bits = 32 bytes |

The RTL default address width is three, but the driver overrides it to
fit each tile. Each bank holds **one tile**, even if it has extra unused
addresses. Deeper RAM does not automatically implement multiple tile slots.

For tile `t`, word `i`, the DUT generates:

```text
a(t,i) = ((t+i) mod 15) + 1
w(t,i) = ((3t+2i) mod 15) + 1
result(t) = sum over i=0..TILE_SIZE-1 of a(t,i)*w(t,i)
```

These functions are **inside the synthesizable DUT**, not inputs delivered
by Python. The controller's only inputs are `clk` and `rst`; it runs the
finite workload after reset. No AXI, DMA, external memory bus, or CPU is
connected. The service counters model transfer/computation delay.

This is a tiled dot-product model, not full CNN inference or a PE array.
There is no signed arithmetic, floating point, bias, activation function,
or saturation. Arbitrarily large inputs/tiles can overflow the 32-bit sum;
the measured positive operands from 1 to 15 fit safely.

### Verilog concepts the professor may point at

- `parameter` values are chosen when the hardware is elaborated. Changing
  tile size or policy means compiling a different configured instance.
  `active_bank_limit` is a register that changes while that instance runs.
- `wire` represents a driven connection. `reg` is a procedural variable
  type in Verilog; it does not by itself guarantee a physical register.
  Assignment style and clocked/combinational processes determine hardware.
- `always @(posedge clk)` describes edge-triggered updates. `if (rst)`
  inside it is synchronous reset; there is no asynchronous reset edge in
  the sensitivity list.
- `<=` schedules nonblocking state updates after the active edge. Other
  clocked blocks see old values at that edge. `=` is used for local
  calculations and combinational selection in this code.
- `always @*` and continuous `assign` describe combinational logic.
  The handoff selector initializes its temporary/selection values before
  scanning candidates, avoiding unintended retained selection state.
- Synthesis turns fixed loops, indexing, comparisons, modulo expressions,
  muxes, multipliers, and additions into logic. It does not execute Python
  or simulation system tasks such as `$display` in the resulting circuit.
- Waveform timing is edge-based: old registered values are read, right-hand
  sides are evaluated, and nonblocking outputs then settle. The testbench
  deliberately checks settled results on the opposite clock edge.

## 3. `sync_ram.v`: enabled synchronous storage

Its clocked behavior is:

```verilog
always @(posedge clk) begin
  if (wr_en) mem[wr_addr] <= wr_data;
  if (rd_en) rd_data <= mem[rd_addr];
end
```

`wr_en` writes one packed pair. `rd_en` samples an address and schedules
the output update after the rising edge. This is a synchronous read;
the MAC consumes that response on a later edge. Disabled read holds the
old output. Read/write have separate controls, but the system prevents
concurrent load/read use of the same bank.

RAM contents and output are not reset. Reset clears ownership; a tile
cannot compute until its words have been written. In standalone RTL a
same-edge, same-address read/write would return old contents because of
nonblocking assignments. The system does not depend on that collision
behavior, and we did not characterize a physical macro's collision rules.

This is behavioral synthesizable storage. Our generic synthesis maps it
into registers and selection logic. It is not a transistor SRAM design
or a characterized foundry memory macro.

## 4. `mac_engine.v`: read pipeline and arithmetic

| Signal/register | Purpose |
| --- | --- |
| `start`, `tile_id`, `run_cycles` | New tile descriptor and service target |
| `rd_en`, `rd_addr`, `rd_data` | Request/return interface to selected RAM |
| `busy` | A tile owns the engine |
| `issued`, `consumed` | Count requested and accumulated operand pairs |
| `valid_d` | Previous read enable; marks a returned pair valid |
| `elapsed`, `target` | Track modeled service duration |
| `accumulator`, `active_tile` | Partial sum and current tag |
| `finishing` | Combinational prediction of completion on this edge |
| `done`, `done_tile`, `result` | Registered completion and old tile's result |

The RAM word's upper half is activation and lower half weight. There is
one unsigned multiply/add expression:

```verilog
accumulator <= accumulator + activation * weight;
```

While `busy && issued < TILE_SIZE`, the MAC requests the next address.
On that edge RAM schedules `rd_data`; the MAC still sees the previous
output. `valid_d` therefore delays accumulation by one edge. Without this
valid pipeline, the first word could be stale and the final word missed.

Completion requires all three conditions:

```text
busy AND elapsed+1 >= target AND consumed == TILE_SIZE
```

The controller clamps compute service to at least `TILE_SIZE+2` to allow
the synchronous pipeline to drain. A larger target adds busy padding:
**not every busy clock performs a useful multiplication**.

### Why simultaneous finish/start is safe

With `CHAIN_START=1`, a new `start` is legal when the current tile is
`finishing`. The old accumulator/tag are captured into result registers,
while counters, accumulator, and tag are initialized for the next tile.
Nonblocking right-hand sides use pre-edge values, so clearing the
accumulator does not destroy the old result being captured. The later
`busy <= 1` assignment wins over the earlier `busy <= 0` in that process.

All old read responses have already been accumulated before `finishing`,
so changing banks does not discard a response. `done` is registered after
the finish edge; the controller publishes it one edge later while the
next tile may already be running. Outputs have no downstream `ready`
or backpressure handshake.

## 5. `scratchpad_controller.v`: states, selection, adaptation

### Bank ownership and loader

Each bank has a two-bit state and a 32-bit tile tag:

```text
EMPTY (0) -> LOADING (1) -> READY (2) -> COMPUTING (3) -> EMPTY
```

`active_load_bank` and `active_compute_bank` select the single bank owned
by each resource. One load and one MAC may run concurrently on different
banks; there are never two simultaneous loads or MAC jobs.
`next_load` assigns increasing tile IDs. `rr_load`/`rr_compute` remember
round-robin search positions; `next_compute` also supports ordered static
policies.

On load acceptance the controller tags an eligible bank, marks LOADING,
clears elapsed time, and records `mem_cycles(tile)`. It writes one pair
per subsequent clock while `load_elapsed < TILE_SIZE`; remaining busy
clocks model delay. Target completion makes the tile READY, or COMPUTING
on that same edge if the fast path dispatches it.

The `generate` loop creates physical RAM instances at elaboration. The
bounded arbitration `for` loops synthesize selection logic; they do not
execute as software loops taking one cycle per iteration. Functions and
`%` expressions also describe hardware. The synthetic source contributes
logic to synthesis totals.

### Policies

| `POLICY` | Normal banks | Rule |
| --- | --- | --- |
| 0 | 1 | Single-buffer cyclic allocation/ordered compute |
| 1 | 2 | Ping-pong cyclic allocation/ordered compute |
| 2 | 4 for Fixed 4 | Round-robin availability search of EMPTY/READY banks |
| 3 | Multiple | Static cyclic mapping and ordered compute |
| 4 | **4 physical banks** | Availability search with runtime allocation limit |

Policies are compile-time parameters. Only the limit changes at runtime.
Policy 4's bounds are hardcoded to two through four; arbitrary bank counts
are not supported merely by changing `BANK_COUNT`. Other policies have
separate scaling tests.

### Runtime allocation limit

Policy 4 starts at two. New allocations require
`bank_index < active_bank_limit`. Each active workload clock counts a
narrow starvation event:

```text
MAC idle AND no MAC issue AND no registered MAC completion
AND no bank currently READY
```

Every 32 clocks, including the current event:

```text
stall count >= 8: increase limit by one, maximum 4
stall count <= 2: decrease limit by one, minimum 2
otherwise:       hold
```

It then clears the window counters. The gap between thresholds provides
a hold region. This uses integer comparisons, not division, ML, or a
latency predictor. There is no adaptive observation window, warmup mask,
instant 2-to-4 jump, READY watermark, or transfer-rate estimator.

Same-edge allocation sees the old limit due to nonblocking semantics;
later edges see the new limit. The testbench compares against
`previous_limit` accordingly.

If the limit falls while a high-index bank holds a tile, it continues
loading/computing or remains dispatchable. Compute selection searches
**all physical banks**. Only future allocation is restricted. There is
no data movement, forced eviction, RAM resizing, clock gating, or power
gating. All four physical banks remain present and clocked.

### Completion-aware handoffs

- `LOOKAHEAD_LOAD=1`: accept the next load on the current load's finish
  edge; potentially reuse a compute bank released on that edge.
- `LOOKAHEAD_COMPUTE=1`: choose a READY bank or a currently finishing load;
  use `mac_finishing` to finish the old MAC and accept the next job on
  one edge. This enables the MAC's `CHAIN_START`.

Starting from a finishing load is safe: accepting the descriptor does
not read RAM immediately; the first read is on the next edge, after the
last write. Releasing the old compute bank uses `mac_finishing` in the
fast path, not delayed `mac_done`, which could otherwise free the newly
selected bank.

Assignment order establishes ownership: load completion's READY is
overridden by same-edge dispatch's COMPUTING; compute release's EMPTY
is overridden by same-edge allocation's LOADING. These are deliberate
nonblocking updates, not simultaneous conflicting owners.

| Parameter | Fixed 4 baseline | Complete proposed design |
| --- | ---: | ---: |
| `POLICY` | 2 | 4 |
| `BANK_COUNT` | 4 | 4 |
| `LOOKAHEAD_LOAD` | 0 | 1 |
| `LOOKAHEAD_COMPUTE` | 0 | 1 |

Both handoff defaults are zero. **Policy 4 alone is the older depth-only
design**, not the complete proposed configuration.

## 6. Clock-by-clock example and the 713-to-522 derivation

Use tile size four, load target eight, compute target eight. Tile zero's
pairs are `(1,1), (2,3), (3,5), (4,7)`, so its sum is **50**.
Execution cycle one is the first active post-reset rising edge, not VCD
timestamp zero.

| Cycle | Proposed action |
| ---: | --- |
| 1 | Accept tile 0 load |
| 2–5 | Write four pairs, one per edge |
| 6–8 | Remaining modeled load delay |
| 9 | Finish tile 0 load; accept MAC tile 0 and next load in another bank |
| 10 | Issue RAM address 0; RAM output updates after edge |
| 11 | Issue address 1, consume pair 0; sum becomes 1 |
| 12 | Issue address 2, consume pair 1; sum becomes 7 |
| 13 | Issue address 3, consume pair 2; sum becomes 22 |
| 14 | Consume pair 3; sum becomes 50 |
| 15–16 | Remaining modeled compute delay |
| 17 | Finish tile 0, capture 50, accept MAC tile 1 |
| 18 | Controller publishes tile 0; tile 1 issues its first read |

With minimum compute target six, tile zero could finish at cycle 15;
target eight deliberately holds it until 17.

Fixed 4's load also finishes at nine. At ten the controller sees READY
and registers `mac_start`; the MAC accepts at eleven and finishes at
nineteen. The controller publishes the result and frees the bank at twenty, requests
the next start at twenty-one, and the MAC accepts at twenty-two. Thus
successive MAC starts are separated by eight busy plus three handoff
clocks in this case.

```text
Fixed 4: first MAC finish 19 + 63*11 + final retirement 1 = 713
Proposed: first MAC finish 17 + 63*8 + final retirement 1 = 522
Saving: 2 startup clocks + 63*3 handoff clocks = 191
```

Both execute 512 MAC-busy clocks and 256 useful MAC operations. Per-tile
work and service targets are unchanged. Scheduling removes idle gaps.

For memory-bound 32/8, 2048 loader-service clocks remain unchanged.
The reduction 2123→2058 saves 63 between-load gaps plus two initial
dispatch clocks. More banks cannot create single-loader bandwidth.

## 7. What workloads were simulated

Service delays are deterministic functions of tile ID, not recorded DRAM
traces or random traffic:

| Profile | Load extra | Compute extra |
| --- | --- | --- |
| Fixed | 0 | 0 |
| Variable | By `t%10`: `[0,8,0,7,18,0,4,13,2,10]` | By `t%5`: `[0,4,0,8,2]` |
| Phase middle third | By `t%10`: `[0,16,0,10,22,1,4,19,0,12]` | 0 |
| Phase outer thirds | 0 | 12 |

`LATENCY_PROFILE=2` overrides the variable profile. The middle third is
`N/3 <= t < 2*N/3` with integer division. For 96 tiles there are three
32-tile phases. Base 8/8 gives outer phases L8/C20 and a middle phase
with irregular loads/C8.

```text
L(t) = max(TILE_SIZE, base load + extra)
C(t) = max(TILE_SIZE+2, base compute + extra)
```

The suite varies tile count/size, bank count, policy, service balance,
profile, and handoff flags. It does not run a trained model or image dataset.

## 8. Counters: what the percentages actually mean

| Counter | Meaning |
| --- | --- |
| `total_cycles` | Active workload through final result retirement; includes fill/drain |
| `load_active_cycles` | Loader busy clocks, including delay padding |
| `compute_active_cycles` | MAC busy clocks, including pipeline and padding |
| `compute_idle_cycles` | Other workload clocks, including startup/handoffs |
| `stall_cycles` | Alias of compute idle |
| `no_ready_stall_cycles` | Narrow adaptation event; not every idle clock |
| `tiles_completed` | Published results |
| `total_mac_operations` | Derived as completed tiles × tile size, not measured multiply pulses |
| `active_bank_sum` | Time sum of allocation limit |
| `time_in_2/3/4_bank_mode` | Workload clocks at each limit |
| `mode_transitions` | Actual limit changes |

```text
total = compute active + compute idle
busy utilization (%) = 100 * compute active / total
tile throughput = completed tiles / total
cycle reduction (%) = 100 * (baseline-proposed) / baseline
speedup = baseline / proposed
average limit = active_bank_sum / total
              = (2*time2 + 3*time3 + 4*time4) / total
```

Balanced proposed busy utilization is `512/522 = 98.08%`; useful work
is `256/522 = 0.4904 MACs/clock`. Do not call 98.08% useful multiplier
efficiency. A 26.79% cycle reduction is about 1.366× throughput, or 36.6%
higher throughput, not 26.79% higher.

The testbench clock period is 10 ns. That determines simulation timestamps;
it does not establish 100 MHz timing closure or measured operations/second.

## 9. Results to remember and difficult attribution questions

| Workload | Tiles | Fixed 4 | Proposed | Fewer cycles | Average limit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Compute, base 8/20 | 64 | 1481 | 1290 | 12.90% | 2.025 |
| Balanced, base 8/8 | 64 | 713 | 522 | 26.79% | 2.061 |
| Memory, base 32/8 | 64 | 2123 | 2058 | 3.06% | 3.953 |
| Variable, base 8/8 | 64 | 983 | 925 | 5.90% | 3.069 |
| Phase, base 8/8 | 96 | 1991 | 1808 | 9.19% | 2.619 |
| Minimum targets, 4/6 | 64 | 581 | 390 | 32.87% | 2.000 |
| Tile size 16, variable 16/20 | 16 | 429 | 403 | 6.06% | 2.079 |
| One tile, 8/8 | 1 | 20 | 18 | 10.00% | 2.000 |

Proposed phase transitions in execution cycles:

```text
cycle: 0  32  64  672  704  1216  1248
limit: 2   3   2    3    4     3     2
```

Mode occupancy is 1200/96/512 clocks at 2/3/4, summing to 1808; weighted
sum 4736 gives average `4736/1808 = 2.619469`. The early excursion is
startup response; warmup is not suppressed. Phase boundaries follow tile
IDs, not an arbitrary timestamp boundary.

Variable proposed has 692 busy + 233 idle = 925 clocks, mode times
224/413/288. Phase has 1536 busy + 272 idle = 1808; its narrow starvation
count is 229, which differs from broad idle time.

**Stale figures:** variable 1025 and phase 2033 belong to the older
policy-4 registered-handoff version. Some slides describe that earlier
study. Use current evidence for the complete proposed design.

**If asked whether adaptation alone caused the gain:**

> No. The measured improvement is for the combined controller against the
> specified Fixed 4 implementation. Faster handoffs remove gaps; adaptation
> changes buffering eligibility and can introduce waiting. We do not
> demonstrate an adaptation-only cycle advantage over Fixed 4.

**If asked whether Fixed 4 can use the same handoffs:**

> Yes. Our engineering controls include it. It matches some schedules and
> is faster on some changing-latency cases: 917 versus 925 for variable
> latency and 1770 versus 1808 for the phase case. Our claim is against
> the specified baseline, not every possible four-bank scheduler.

Controls remain in the datasets. The requested manuscript scope is Fixed
4 versus Proposed within nine pages; this guide does not add an ablation
section to it. Do not deny an existing control result if directly asked.

## 10. Testbench: how correctness was checked

Read [tb_controller.v](../tb/tb_controller.v) in four parts:

1. **Clock/reset:** `timescale 1ns/1ps`, clock toggles every five ns; reset
   stays high through three falling edges. It deasserts around 30 ns;
   first active rising edge is 35 ns. RTL reset is synchronous active high.
2. **Rising-edge issue checks:** observe actual accepted descriptors;
   reject unavailable MAC issues, invalid IDs, duplicate starts, invalid
   compute-bank ownership, and same-bank concurrent load/read. Chained
   start is legal only on a finishing edge with the feature enabled.
3. **Falling-edge settled checks:** after nonblocking updates, require at
   most one LOADING and one COMPUTING bank; validate loader ownership,
   prior-limit allocation eligibility, runtime bounds, result IDs,
   duplicate completions, and every expected dot product.
4. **Final checks/timeout:** require N starts and results, completed and
   operation counts, total/active/idle accounting, and mode-time sums.
   A bounded timeout detects a workload that fails to finish.

`started` and `seen` bit vectors act as issue/completion scoreboards.
The golden loop recomputes the specified operand formulas and full sum,
not the DUT accumulator. `!==` catches unknown result bits too. This
is independent arithmetic implementation, not independent validation
that the chosen synthetic workload represents a real application.

The fail task prints `STATUS=FAIL` and calls `$finish`, which can still
return process exit code zero. Python therefore requires `STATUS=PASS`,
absence of `STATUS=FAIL`, and the expected check count, not just exit zero.
Each correct tile produces `TILE_PASS`. With `TRACE_HANDOFF=1`, logs
include LOAD/MAC ACCEPT/FINISH cycle, bank, and tile. `+VCD=...` writes
signal-level waveforms.

| Evidence set | Count | Purpose |
| --- | ---: | --- |
| Functional cases | 14 | Arithmetic/protocol checks across baseline policies/runtime depth |
| Historical replays | 129 | Handoff flags off; preserve 13 reference metrics |
| Additional stress configurations | 84 | Corner sizes/counts/banks/policies and enabled handoff combinations |
| Extended measurements | 64 | Eight workloads × two policies × four handoff settings |
| Audit reruns | 20 | Four families × five configurations; reproduce stored audited metrics |

The 14 functional cases comprise ten initial and four runtime cases,
with registered handoffs. **That suite alone does not verify the full
proposed design**; the extension and audit exercise fast paths.

Stress is seven policy/bank combinations × four workloads × three nonzero
handoff settings. It includes one tile, tile size one, minimum service
floors, larger variable tiles, phase changes, and bank counts 1/2/3/4/8
under suitable policies. These are directed cases, not random seeds.

The original 129 matrix comprises 44 fixed-latency, 20 tile-count,
16 tile-size, 8 variable, 15 bank-scaling, 15 adaptation, 5 phase, and
6 equal-storage configurations. An older 103-case archive predates the
runtime extension. Coverage overlaps; do not add all counts and call
the sum independent applications.

On **23 October 2026**, source hashes matched the validation manifest;
**14/14 functional and 20/20 audit cases were freshly rerun and passed**.
The larger matrices are preserved validation evidence and were not all
rerun for this documentation update.

## 11. Scripts: what we wrote beyond RTL

### Simulation and analysis

| Script | Responsibility |
| --- | --- |
| `scripts/run.py` | Find tools, select parameters, compile/run, check logs, parse counters, write CSVs, enumerate original cases |
| `scripts/evaluate_lookahead.py` | Replay references; stress/measurement matrix; independent service sums and intervals; event traces and source hashes |
| `scripts/verify_paper_results.py` | Check recorded source hashes, rerun 20 selected cases, compare metrics to stored evidence, write audit CSV/JSON |
| `scripts/analyze_results.py` | Original matrix accounting/bounds, historical preservation, original phase waveform analysis |

`run.py` invokes commands equivalent to:

```text
iverilog -g2005 -s tb_controller -o results/build/CASE.vvp
         -Ptb_controller.PARAMETER=VALUE ... rtl/*.v tb/tb_controller.v
vvp results/build/CASE.vvp [+VCD=waveform_path]
```

It checks `IVERILOG`/`VVP` environment variables, then local
`tools/iverilog/bin`, then PATH. It calculates an address width that fits
the tile and rejects too-small explicit depth. It does not override
operand width, so ordinary runs use the testbench's eight-bit default.
Python orchestrates and analyzes; the MAC computation runs in Verilog.

Independent checks sum all `L(t)`/`C(t)` targets and compare active counts.
For every tile, traced finish-minus-accept must equal its target and use
the same bank; resource intervals must not overlap. Full-look-ahead
fixed-depth controls also match a separate finite-buffer two-server FIFO
schedule model. That model is not an oracle for adaptive scheduling.

Validation JSON records SHA-256 for the controller, MAC, testbench,
driver, and extension evaluator. The audit checks those hashes before
replay. This binds evidence to those source versions, not every file
in the project, and is not a formal correctness proof.

### Plots, diagrams, presentation

| Script | Responsibility |
| --- | --- |
| `scripts/generate_primary_results.py` | Current Fixed 4/Proposed cycle figure; proposed phase VCD parsing; occupancy cross-check |
| `scripts/generate_lookahead_figures.py` | Actual handoff event timing; separate unused engineering-control plot |
| `scripts/generate_plots.py` | Original matrix plots |
| `scripts/generate_paper_diagrams.py` | Vector architecture/state diagrams using Matplotlib |
| `presentation/build/build_deck.mjs` | Existing review slides, some containing older depth-only results |

Correct proposed phase waveform:
`results/waveforms/paper_audit_lookahead_phase_p4_l1c1.vcd`.
`adapt_phase_runtime_adaptive.vcd` is the old 2033-cycle schedule.
The current parser uses the DUT execution-cycle signal; simply dividing
VCD timestamps by period would leave reset offset in the plot.

### Synthesis and gate diagrams

| Script | Responsibility |
| --- | --- |
| `scripts/lookahead_legacy_synthesis.ys` | Baseline: four banks, address width two, 64 tiles, flags off |
| `scripts/lookahead_adaptive_synthesis.ys` | Matched geometry, policy four, flags on |
| `scripts/synthesize_lookahead.ps1` | Project-local YoWASP/Yosys runs and summary validation |
| `scripts/summarize_lookahead_synthesis.py` | Validate logs/netlists, reject latch problems, count generic cells/register bits |
| `scripts/generate_gate_diagrams.ps1` | Synthesis-to-netlist-to-NetlistSVG schematic, with image conversion |
| `scripts/extract_active_limit_cone.py` | Extract actual cells/wires around allocation-limit registers; other registers form boundaries |

The Yosys scripts read all three modules, apply parameters, run
`synth -top scratchpad_controller -flatten`, and write JSON and Verilog.
This maps to generic gates/registers, with no foundry Liberty library
or FPGA device target.

Matched baseline/proposed counts are **3477/4713 generic cells and
595/864 register bits**. Five scope metadata cells per JSON are excluded.
The generic cell count rises **35.55%**. Totals include instrumentation,
synthetic source logic, and flop-mapped memory; do not claim unchanged
area or convert directly to watts or square micrometres. Older synthesis
configurations have different RAM depths and are not matched comparisons.

The small RAM schematic is a reduced instance for readability, not all
four banks. A two-word/one-bit instance maps to six cells: three enabled
registers, one mux, and two decode gates. A four-word/four-bit instance
maps to 38 cells. The limit schematic is a real extracted netlist cone.
These diagrams derive from actual synthesized connectivity, not generated
artwork. They do not show transistor sizes, physical routing, or SRAM layout.

## 12. Reproduce results during the review

From project-root PowerShell:

```powershell
python scripts/run.py test
python scripts/verify_paper_results.py
```

For an explicit comparison with waveforms and event logs:

```powershell
@'
from scripts.run import run_case
for name, policy, handoff in (("review_fixed4", 2, 0),
                              ("review_proposed", 4, 1)):
    r = run_case(name, "review", policy, 4, 64, 4, 8, 8,
                 wave=True, trace_handoff=True,
                 lookahead_load=handoff, lookahead_compute=handoff)
    print(name, r["total_cycles"], r["compute_active_cycles"],
          r["compute_idle_cycles"], r["status"])
'@ | python -
```

Expected metrics:

```text
review_fixed4    713 512 201 PASS
review_proposed  522 512  10 PASS
```

Show `results/raw/review_proposed.log` for tile results/events; its first
result is 50. The waveform is `results/waveforms/review_proposed.vcd`.
Inspect clock/reset, bank states, busy signals, active bank indices,
`mac_issue`, `mac_finishing`, `mac_done`, RAM read/addr, `valid_d`,
accumulator, result, and allocation limit.

Add `variable=1` for 983/925; use 96 tiles and `profile=2` for 1991/1808.
Both proposed handoff flags must remain one.

Full regeneration commands are in `context.md`. Older `run_all.ps1`/`.sh`
do not run the scheduling extension; `make lookahead` does. Synthesis is
separate. Restricted sandboxes can prevent overwriting existing `.vvp`
files; the current host PowerShell rerun succeeded.

## 13. Professor questions: direct answers

**Scratchpad versus cache?** Explicit placement and lifetime controlled
by tile tags/states; no cache tag lookup, miss handling, replacement,
or coherence protocol.

**Why banks?** They separate loader and MAC ownership and queue complete
tiles. This is buffering, not parallel multiword reads into a PE array.

**What does round-robin do?** Search from a remembered pointer, select
the first eligible bank, then advance past it. This is combinational
selection, not a CPU scheduling software threads.

**What does the state diagram mean physically?** Two state bits per
bank, sequential updates, and selection logic. There is no processor
executing state labels.

**Why not reset memory?** Ownership prevents reading a tile before
writing it. Resetting control is sufficient for the intended startup.
Mid-workload reset recovery was not separately tested.

**Why `valid_d`?** RAM output changes after the read edge. Accumulating
on the following edge consumes the correct synchronous response.

**Why separate `finishing` and `done`?** One predicts the edge for fast
handoff; the other records completion and carries the result afterward.

**Can a new start overwrite the old result?** Old accumulator/tag are
captured using pre-edge values before new-job state takes effect;
the registered result is distinct from the new accumulator.

**Why not release with `mac_done` in fast mode?** It is delayed; the
active bank could already belong to the next tile. Release uses the
old job's finishing edge instead.

**Can the MAC start on a final write?** Yes: descriptor acceptance is
followed by the first read one edge later. The write has completed.

**Does shrinking lose a high-bank tile?** No. Existing owners drain,
and dispatch sees all banks. Only future allocations are restricted.

**Does average 2.061 mean fractional hardware or occupancy?** Neither.
It averages the eligible-bank limit. All four banks remain instantiated.

**Why early mode changes?** Startup starvation is counted; no warmup
mask exists.

**Do thresholds guarantee no oscillation?** No. Windowing and a hold
region reduce reaction frequency; adversarial delays can still cause
repeated changes.

**Are 32/8/2 optimal?** They are explicit heuristic settings. There is
no proof of global optimality or real-application tuning campaign.

**Why small memory-bound gain?** The single loader still supplies all
operands. Buffering and gap removal cannot invent transfer bandwidth.

**Was the multiplier made faster?** No. Same one multiplier/accumulator,
operand width, and service targets. Handoff scheduling removes idle gaps.

**What did we test on?** Windows-host software simulation with Icarus
Verilog and VVP; generic synthesis with Yosys/YoWASP. No FPGA, chip,
real DRAM, PDK, or hardware power meter supplied the reported numbers.

**How do we know plots are measurements?** Tile checks, counters, and
event logs come from simulation. Scripts independently validate service
sums/intervals, preserve raw logs, and audit replay against hashed sources.

**Does passing simulation prove all behavior?** No. Directed tests,
scoreboards, accounting, and synthesis checks are evidence, not formal
exhaustive verification. The golden sum also shares the specified input
formula, so it cannot independently validate the workload specification.

**Does synthesis establish clock frequency?** No. Technology mapping,
constraints, placement/routing, and static timing analysis are needed.
Fast handoff selection adds combinational logic that needs timing review.

**What is the hardware cost?** The matched generic cell count rises
3477→4713; register bits 595→864. Instrumentation and source logic are
included. These are not physical area/power measurements.

**Is the diagram the whole chip?** The small RAM and limit-cone figures
are selected real netlist views. Full JSON/Verilog is in `results/netlist`.
They are not a transistor SRAM or chip layout.

**Do fewer eligible banks save power?** Not demonstrated. No bank clock
or power gating is implemented, and no technology power flow was run.

**Can literature numbers be ranked against ours?** No. Eyeriss/TPU are
different complete systems/workloads. Our static cyclic policy is a
buffering proxy, not a faithful reproduction of either architecture.

**Who wrote each part?** Use actual contribution history. The repository
establishes artifacts, not per-file individual authorship. Do not invent
teammate roles for the review.

## 14. Boundaries and next steps

- No external-memory protocol, real traces, trained-network application,
  physical timing closure, board measurements, or power measurements.
- No full-range/signed arithmetic sweep, overflow handling, mid-run reset
  campaign, downstream backpressure tests, standalone exhaustive RAM
  collision verification, formal proof, or UVM environment.
- No exhaustive parameter validation. Policy 4 assumes four banks;
  service/read counters are 16 bits and IDs/metrics are 32 bits, so huge
  configurations are not covered.
- Equal storage words do not necessarily mean equal usable tile slots.
- Generic synthesizability does not establish an achievable chip clock.

Next steps: a real transfer handshake interface, realistic traces,
defined signed/overflow behavior, stronger protocol verification, and
technology-specific timing/power analysis. These are future work.

## 15. Preparation route

1. Memorize the opening, parameter table, five main cycle pairs, and
   busy-utilization caveat.
2. Read RAM then MAC. Draw tile zero's read/valid/accumulate sequence
   and explain result 50.
3. Read the controller in order: states, functions, selector, RAM
   instances, reset, adaptation, completion, allocation, dispatch.
4. Explain 713→522 without referring to a plot.
5. Show a raw log and audit JSON. Say which check catches a wrong sum,
   duplicate/missing tile, collision, or changed service interval.
6. Rehearse the attribution and physical-measurement questions honestly.
