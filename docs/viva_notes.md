# Viva revision sheet: current proposed controller

Checked 23 October 2026. Read [review_guide.md](review_guide.md) for the
full implementation, clock walkthrough, scripts, testing, and questions.

## One-minute answer

We implemented a tiled dot-product engine in Verilog with one loader,
four independent scratchpad banks, and one unsigned MAC. The controller
overlaps loading and computing on different banks. The proposed design
combines a runtime 2/3/4 bank allocation limit with completion-aware
handoffs that remove gaps between jobs. We verified every tile sum,
exactly-once issue/completion, ownership, service intervals, and cycle
accounting in Icarus simulation. Balanced execution drops from 713 to
522 cycles against the specified Fixed 4 baseline. Operands and transfer
delays are synthetic; we have not measured a board or fabricated chip.

## Know the implementation

| File | What to explain |
| --- | --- |
| `rtl/sync_ram.v` | Synchronous enabled read/write array; no RAM reset; registered read output |
| `rtl/mac_engine.v` | Unpack two unsigned operands; read/valid pipeline; multiply/accumulate; finishing and chained start |
| `rtl/scratchpad_controller.v` | Operand generator; loader; bank FSMs/tags; round-robin arbitration; runtime limit; handoffs; counters |
| `tb/tb_controller.v` | Clock/reset; independent expected sums; issue/completion scoreboards; protocol assertions; PASS/FAIL and VCD |

- Main tile: four activation/weight pairs. Eight bits per operand, 16 bits
  per stored word, 32-bit sum. Four banks × four words = 32 bytes.
- Bank states: `EMPTY → LOADING → READY → COMPUTING → EMPTY`.
- One loader and one MAC; they can overlap only on different banks.
- Input values are generated **inside the DUT**. No actual DRAM/AXI/DMA.
- `valid_d` aligns accumulation with synchronous RAM responses.
- `finishing` predicts completion before an edge; `done` is registered
  after it. Old result capture and next-job reset share an edge safely
  using nonblocking assignments.
- First tile: activations 1/2/3/4, weights 1/3/5/7, result **50**.

## Exact settings and adaptation

| Setting | Fixed 4 | Proposed |
| --- | ---: | ---: |
| `POLICY` | 2 | 4 |
| `BANK_COUNT` | 4 | 4 |
| `LOOKAHEAD_LOAD` | 0 | 1 |
| `LOOKAHEAD_COMPUTE` | 0 | 1 |

Policy 4 alone is the older depth-only configuration. Both handoff flags
are needed for the current proposed results.

Every 32 active clocks: at least eight narrow starvation events raises
the limit by one; at most two lowers it by one; otherwise hold. Limits
are two through four. Starvation means MAC idle, no issue or completion,
and no READY bank. The limit restricts **new allocations only**; tiles in
higher banks drain normally. All four banks stay instantiated and clocked.

## Numbers to remember

| Workload | Fixed 4 | Proposed | Fewer cycles |
| --- | ---: | ---: | ---: |
| Compute-bound, 64 tiles | 1481 | 1290 | 12.90% |
| Balanced, 64 tiles | 713 | 522 | 26.79% |
| Memory-bound, 64 tiles | 2123 | 2058 | 3.06% |
| Variable, 64 tiles | 983 | 925 | 5.90% |
| Phase, 96 tiles | 1991 | 1808 | 9.19% |

Balanced explanation: **2 startup clocks + 63 × 3 MAC handoff clocks =
191 saved**. Both variants still have 512 MAC-busy clocks and perform
256 useful MACs. Proposed busy utilization is 98.08%; useful work rate is
0.4904 MACs/clock. Busy utilization includes modeled delay padding.

Proposed phase occupancy: 1200/96/512 clocks at limits 2/3/4, averaging
2.619. This is eligibility, not physical occupancy or measured power.
Old 1025/2033 values belong to the depth-only version; some slides are stale.

## Testing and scripts

- Icarus compiles Verilog; VVP simulates it on the Windows host.
- Python orchestrates runs, checks logs, derives metrics, writes CSVs,
  independently checks service sums/intervals, and generates figures.
- Testbench checks every result, valid IDs, no duplicate starts/results,
  resource ownership, no load/read bank collision, limit bounds, counters,
  and timeout. Rising-edge issue checks and falling-edge settled-result
  checks handle nonblocking timing correctly.
- Evidence: 14 functional cases, 129 reference replays, 84 stress cases,
  64 extended measurements, 20 audited reruns. Coverage overlaps.
- **Freshly rerun on 23 October: 14/14 functional and 20/20 audit PASS.**
- `run.py`: compile/run/parse. `evaluate_lookahead.py`: regression, stress,
  independent schedule/accounting checks. `verify_paper_results.py`:
  source hashes and measurement replay. `generate_primary_results.py`:
  current main figures and proposed VCD trace.

```powershell
python scripts/run.py test
python scripts/verify_paper_results.py
```

## Difficult questions: accurate short answers

**Is adaptation alone responsible for the speedup?** No. The complete
controller combines adaptation with faster handoffs. Scheduling removes
idle gaps; adaptation changes available buffering.

**Can a fixed-depth controller also use those handoffs?** Yes. Engineering
controls show it can match or beat the adaptive schedule. The supported
claim is against the specified registered-handoff Fixed 4 baseline.

**Did fewer banks save power?** We did not establish that. Four banks
remain present; no clock/power gating or technology power analysis exists.

**What was synthesized?** The actual three RTL modules, with matched
parameters, into generic Yosys cells. Baseline/proposed: 3477/4713 cells,
595/864 register bits. That includes counters, source logic, and flop RAM.
No PDK, physical area, or timing closure was used.

**Is the gate figure genuine?** It comes from synthesized netlist
connectivity. The small RAM instance and allocation-limit cone are selected
views, not the entire accelerator or a transistor SRAM layout.

**What is not verified?** Real memory traffic, trained applications,
signed/full-range arithmetic, mid-run reset, downstream backpressure,
physical timing/power, and exhaustive/formal parameter correctness.

**Why not compare cycles directly with TPU/Eyeriss?** Different complete
systems and workloads. Literature motivates the design; only our internal
controlled RTL comparisons have the same work and timing model.

**Next step?** Replace the synthetic source with a real handshake interface,
test realistic traces, define arithmetic overflow behavior, and perform
technology-specific timing/power analysis.
