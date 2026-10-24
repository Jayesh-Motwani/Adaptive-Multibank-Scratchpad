# Architecture and implementation plan

The experiment uses one tile source, one transfer interface, one MAC consumer,
and an array of synchronous RAM banks. A tile contains `TILE_SIZE` pairs of
unsigned `DATA_WIDTH` activation and weight values. The loader writes one
pair per clock while active. Its target latency is the configured transfer
cycles, with a floor of `TILE_SIZE` clocks. The MAC reads one pair per clock
from the selected bank. Its target latency has a floor of `TILE_SIZE+2` clocks
to cover the synchronous read pipeline. Extra latency represents waiting, not
additional arithmetic. There is no DRAM protocol or complete CNN datapath.

`scratchpad_controller.v` is the common datapath and state machine. Its policy
parameter selects the only architectural difference:

| Policy | Banks | Load allocation | Compute dispatch |
|---|---:|---|---|
| Single | 1 | tile ID modulo 1 | strict tile ID order |
| Ping-pong | 2 | tile ID modulo 2 | strict tile ID order |
| Adaptive | parameterized, default 4 | round-robin search of EMPTY banks | round-robin search of READY banks |
| Literature-inspired proxy | parameterized, default 4 | static tile ID modulo bank count | strict tile ID order |
| Runtime adaptive | four physical banks, active limit 2/3/4 | round-robin EMPTY search below limit | round-robin READY search over all four banks |

The fourth policy is a **generic static cyclic multi-buffer proxy** for
literature discussion. It does not reproduce a named chip. Its purpose is a
controlled scheduling comparison against availability-driven allocation.

Every bank stores a tile ID and has an explicit state: `EMPTY`, `LOADING`,
`READY`, or `COMPUTING`. The loader and MAC each occupy at most one bank.
When both finish on a clock, state releases take effect after that clock;
the arbiter cannot reuse a just-released bank until the next clock. Results
carry tile IDs, so adaptive dispatch need not preserve arrival order.

## Runtime depth adaptation

The proposed incremental mechanism is a lightweight hysteresis policy for
effective buffering depth. The four physical RAM banks remain instantiated.
`active_bank_limit` begins at two. New load allocations may target only banks
whose index is below that limit. Any READY or COMPUTING tile in a bank above
a newly lowered limit remains valid and is allowed to finish. Compute
dispatch searches all four banks for that reason.

Every `OBS_WINDOW` clocks (default 32), the controller compares the count of
cycles with no READY bank and an available compute engine with integer
thresholds. At eight or more such cycles it raises the limit by one, up to
four. At two or fewer it lowers by one, down to two. Intermediate counts
leave the mode unchanged. No division or machine learning is in the RTL.
The observation counter, stall counter, limit, and per-bank states appear in
VCD. These thresholds are simulation parameters and need retuning for a
different latency scale.

`STALL_CYCLES` remains the original broad compute idle metric, including
initial fill and dispatch overhead. `NO_READY_STALL_CYCLES` is the narrower
starvation event used by the adaptation rule. Average active banks equals
the sum of the limit each measured clock divided by total cycles; it is an
**effective buffering-depth / bank-activity metric**, not measured power.

The phase profile divides the tile stream into thirds. The first and last
thirds use base memory latency and base compute latency plus 12. The middle
third uses base compute latency and adds to memory latency the deterministic
sequence `[0,16,0,10,22,1,4,19,0,12]` by tile ID modulo ten. The profile
creates fast-compute, irregular-memory pressure in the middle. The other
variable profile and its sequences remain as originally implemented.

The RAM is a synthesizable behavioral **RTL scratchpad memory architecture**.
It is not a physical SRAM circuit design. The model does not predict silicon
area, SRAM access energy, or achievable clock frequency.

## Deterministic operands and latency

For tile `t` and element `i`, activation is `((t+i) mod 15)+1` and weight is
`((3t+2i) mod 15)+1`. The expected result is the sum of their products.

Variable transfer latency adds `[0,8,0,7,18,0,4,13,2,10]` for `t mod 10`.
Variable compute latency adds `[0,4,0,8,2]` for `t mod 5`. These sequences
are constants in Verilog, independent of pseudo-random seeds. The configured
base and the minimum structural latency above determine the effective value.

## Metric definitions

The observation window starts on the first clock after reset and ends when
the final result is registered. `TOTAL_CYCLES` counts that window.
`LOAD_ACTIVE_CYCLES` counts clocks with loader busy. `COMPUTE_ACTIVE_CYCLES`
counts clocks with MAC busy. `COMPUTE_IDLE_CYCLES = TOTAL_CYCLES -
COMPUTE_ACTIVE_CYCLES`. `STALL_CYCLES` equals compute idle cycles, including
initial fill and dispatch gaps. `TOTAL_MAC_OPERATIONS = TILES_COMPLETED ×
TILE_SIZE`. Utilization is active/total, throughput is tiles/total, speedup
is baseline cycles divided by candidate cycles, and stall fraction is
stall/total. These definitions deliberately expose controller overhead.

See `diagrams/*.mmd` for architecture, FSM, and illustrative timing sources.
The timing diagrams explain scheduling qualitatively; they are not measured
waveforms. VCD outputs from simulation are the measured waveforms.
