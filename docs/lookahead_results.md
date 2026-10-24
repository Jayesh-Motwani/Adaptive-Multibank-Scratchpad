# Measured look-ahead handoff results

All rows use four physical banks, one loader, one MAC, identical operands,
and identical per-tile service times. Cycle counts include startup and final retirement.

| Workload | Original fixed 4 | Look-ahead fixed 4 | Look-ahead adaptive | Fixed-4 cycle reduction | Adaptive cycle reduction | Adaptive average limit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| compute | 1481 | 1290 | 1290 | 12.90% | 12.90% | 2.025 |
| balanced | 713 | 522 | 522 | 26.79% | 26.79% | 2.061 |
| memory | 2123 | 2058 | 2058 | 3.06% | 3.06% | 3.953 |
| variable | 983 | 917 | 925 | 6.71% | 5.90% | 3.069 |
| phase | 1991 | 1770 | 1808 | 11.10% | 9.19% | 2.619 |
| minimum | 581 | 390 | 390 | 32.87% | 32.87% | 2.000 |
| large_tile | 429 | 385 | 403 | 10.26% | 6.06% | 2.079 |
| one_tile | 20 | 18 | 18 | 10.00% | 10.00% | 2.000 |

Verification: 129 legacy cases retain 13 metrics each;
84 additional correctness cases and 64 ablation measurements pass.
Every traced load/MAC interval matches its original service target. The complete
look-ahead fixed-bank cases match an independent finite-buffer FIFO schedule.

The cycle improvement is due to removing controller handoff bubbles. The adaptive
bank restriction still does not outperform the same look-ahead scheduler with all
four banks available. Report both comparisons. No clock-frequency, power, or
silicon-area claim follows from cycle reduction alone.

Machine-readable rows, event traces, and verification hashes are in
`results/csv/lookahead_results.csv`, `lookahead_handoff_trace.csv`, and
`lookahead_validation.json`. Original results_summary.csv remains unchanged.
