# Pre-adaptation passing state (2026-10-09)

The existing implementation was compiled and simulated with Icarus Verilog
14.0 (devel) before the runtime-depth extension. All **10/10 functional
cases** passed, including single, ping-pong, adaptive 2/4/8-bank, and static
cyclic four-bank tests. All **103/103 performance simulations** passed.

The original CSV and raw simulator logs were copied, without changing them,
to `results/baseline_snapshot/pre_adaptation_csv.zip` and
`results/baseline_snapshot/pre_adaptation_raw.zip` before RTL modification.

Representative measured cycles for 32 tiles, tile size 4:

| Condition | Single | Ping-pong | Fixed 4-bank availability | Static 4-bank |
|---|---:|---:|---:|---:|
| Fixed transfer 8, compute 8 | 640 | 361 | 361 | 361 |
| Variable latency, base transfer 8, compute 8 | 922 | 539 | 497 | 497 |

Under the existing serial load and compute model, fixed four-bank availability
and static cyclic four-bank gave the same measured time in these conditions.
This suggests the gain over two banks here comes from additional buffering
capacity, not the availability arbitration policy alone. The later runtime
depth experiments will compare against this preserved fixed four-bank baseline.
