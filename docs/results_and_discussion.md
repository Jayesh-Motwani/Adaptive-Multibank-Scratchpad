# Measured results and discussion

This document preserves the original bank-depth measurements with both
look-ahead handoff flags disabled. The newer scheduling improvement,
including comparisons against original and equally optimized fixed four,
is documented in [lookahead_results.md](lookahead_results.md) and the
updated paper.

All values below come from `results/csv/results_summary.csv`, which was parsed
from individual Icarus/VVP logs. The default data width is eight bits, tile
size four, and a single loader/MAC. `STALL_CYCLES` counts all compute idle
clocks; the narrower no-READY counter drives runtime adaptation.

## Original buffering question

For 32 tiles with fixed transfer/compute settings of 8/8, single buffering
took **640** cycles; ping-pong, fixed four-bank availability, and static
four-bank cyclic each took **361** cycles. Ping-pong gave **1.773×** speedup
against single buffering. Four banks did not help beyond two for this steady
case. The fixed 16/16 case took 1152/625/625 cycles, and the fixed 32/32 case
took 2176/1153/1153 cycles for single/ping-pong/four-bank respectively.

For 32 tiles with the deterministic variable-latency profile and base 8/8,
the same architectures took **922/539/497/497** cycles. Four banks were
**1.0845×** faster than ping-pong. Bank scaling for this workload yielded
539 cycles with two banks and 497 with three, four, six, or eight banks.
Three banks were sufficient; deeper buffering saturated. Fixed four-bank
availability and the static cyclic four-bank proxy had identical cycles in
all tested matched settings. This model therefore does not show an independent
gain from availability arbitration at fixed capacity. It shows a capacity
benefit under variable timing.

## Runtime depth policy

The following direct comparison uses the same RTL datapath, operands,
latency schedule, and simulator in each row. `Avg limit` is the average
eligible bank count over the measured clocks. It is not power.

| Workload | Architecture | Cycles | Compute idle | Utilization | Tiles/cycle | Avg limit |
|---|---|---:|---:|---:|---:|---:|
| Stable compute-bound, 64 tiles, 8/20 | Single | 2048 | 768 | 62.50% | 0.03125 | 1 |
| | Ping-pong | 1481 | 201 | 86.43% | 0.04321 | 2 |
| | Fixed four-bank | 1481 | 201 | 86.43% | 0.04321 | 4 |
| | Runtime 2/3/4 | 1481 | 201 | 86.43% | 0.04321 | 2.022 |
| Stable balanced, 64 tiles, 8/8 | Single | 1280 | 768 | 40.00% | 0.05000 | 1 |
| | Ping-pong | 713 | 201 | 71.81% | 0.08976 | 2 |
| | Fixed four-bank | 713 | 201 | 71.81% | 0.08976 | 4 |
| | Runtime 2/3/4 | 713 | 201 | 71.81% | 0.08976 | 2.045 |
| Variable latency, 64 tiles, base 8/8 | Single | 1847 | 1155 | 37.47% | 0.03465 | 1 |
| | Ping-pong | 1072 | 380 | 64.55% | 0.05970 | 2 |
| | Fixed four-bank | 983 | 291 | 70.40% | 0.06511 | 4 |
| | Runtime 2/3/4 | 1025 | 333 | 67.51% | 0.06244 | 2.500 |
| Phase change, 96 tiles | Single | 2950 | 1414 | 52.07% | 0.03254 | 1 |
| | Ping-pong | 2054 | 518 | 74.78% | 0.04674 | 2 |
| | Fixed four-bank | 1991 | 455 | 77.15% | 0.04822 | 4 |
| | Runtime 2/3/4 | 2033 | 497 | 75.55% | 0.04722 | 2.582 |

Under the stable compute-bound and balanced cases, runtime depth matched
fixed four-bank execution time while averaging about **2.02** and **2.04**
eligible banks. Startup fill briefly raised the mode, then it returned to
two. Under variable latency, fixed four-bank was **4.27% faster** than runtime
(983 versus 1025 cycles), while runtime averaged **2.50** banks. In the
phase-changing workload, runtime was **2.11% slower** than fixed four-bank
(2033 versus 1991 cycles) and averaged **2.58** banks. Runtime still beat
two-bank ping-pong by **1.046×** in the variable case and **1.010×** in the
phase case. These are modest gains; deeper buffering is not always needed.

The measured phase VCD transitions were: cycle 0 two banks; 34 three; 66
two; 770 three; 802 four; 1346 three; 1378 two. The early increase is an
initial-fill transient. The middle increase corresponds to irregular memory
latency, and the final decrease follows return to compute-bound operation.
Mode occupancy over the full 2033-cycle window was 1393 cycles at two banks,
96 at three, and 544 at four. No in-flight high-bank tile was discarded;
all 96 MAC results passed self-checking verification.

## Equal physical word count

Two ping-pong banks with eight words each and four multi-bank banks with four
words each both instantiate 16 RAM words. With tile size four, the variable
case took **1072/983/1025** cycles for ping-pong/fixed four/runtime. The
phase case took **2054/1991/2033**. These match the corresponding main runs
because extra ping-pong words do not hold a second tile in this controller.
The study controls raw word count but leaves a usable-tile-slot difference;
it must not be interpreted as a fully capacity-matched architecture proof.

## Relation to published work

Eyeriss, TPU, and Eyeriss v2 demonstrate that local storage, dataflow, and
flexibility matter in complete accelerators. Their published frame rates,
inferences per second, DRAM accesses/MAC, and full-system speedups do not
share our tile workload, clock, platform, or denominator. The comparison is
**QUALITATIVE**, not DIRECT or NORMALIZED. The controlled RTL rows above are
the evidence for the bank-depth question. The exact published numbers and
sources are in `previous_work_results.md` and
`results/csv/previous_work_comparison.csv`.

## Interpretation

The proposed mechanism answers the new question conditionally: it retains
fixed four-bank performance in stable workloads with an effective depth near
two, but pays a small performance cost under irregular conditions while
using fewer eligible banks on average. Since all four physical banks remain,
the lower effective depth does **not** establish power or area savings.
The single transfer interface also bounds what extra banks can do when memory
service is persistently slower than computation. These negative and neutral
results are part of the finding, not hidden exceptions.
