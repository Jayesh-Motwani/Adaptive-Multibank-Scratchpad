# Verification plan and observed status

The Verilog testbench resets the DUT, then checks every completed tile ID for
range, uniqueness, and the exact MAC sum computed independently from the
operand formula. It checks the total tile and MAC operation counters, cycle
accounting, one loader/one compute resource occupancy, legal active bank
limit, mode-time accounting, and every EMPTY-to-LOADING transition against
the previous mode limit. A bank already above a lowered limit may drain.

Functional cases cover one tile, 16–96 tiles, slow transfer, slow compute,
balanced settings, variable latency, larger tile size, 2/3/4/8 bank counts,
static cyclic scheduling, and the phase profile. The phase waveform is parsed
to confirm an increase from two to four banks and a later return to two.

**Observed:** 14/14 functional simulations PASS. 129/129 performance runs
completed with `STATUS=PASS`; no failed simulations. `analyze_results.py`
checked all 129 runs for independent expected transfer/compute active cycles,
cycle totals, MAC counts, and lower bounds. The 103 pre-extension cases match
the archived metrics exactly. The checker also validated six VCD mode
transitions and generated `results/csv/mode_trace.csv`.

VCD signals to inspect in GTKWave: `bank_state_debug`, `active_bank_limit`,
`stall_count`, `observation_counter`, `load_busy`, `compute_busy`,
`active_load_bank`, `active_compute_bank`, `tile_done`, `result_tile`, and
`result_value`. The phase trace is
`results/waveforms/adapt_phase_runtime_adaptive.vcd`.
