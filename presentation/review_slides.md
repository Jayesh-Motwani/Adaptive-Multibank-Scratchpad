# Review presentation: adaptive scratchpad buffering depth

The PowerPoint deck follows this concise 24-slide outline. Quantitative
values come from `results/csv/results_summary.csv`; published numbers are
traced in `docs/previous_work_results.md`.

1. **Title** — RTL implementation and controlled evaluation.
2. **Research questions** — when four banks beat ping-pong; whether runtime
   depth keeps performance with fewer eligible banks.
3. **Memory bottleneck** — transfer and MAC compete for tile availability.
4. **Scratchpad and tiling** — a tile is four activation/weight pairs in the
   principal experiment; RAM is behavioral RTL, not physical SRAM.
5. **Prior accelerators** — Eyeriss, TPU, Eyeriss v2 and their memory roles.
6. **Published measurements** — exact reported conditions and values.
7. **Comparability** — published hardware metrics are qualitative context.
8. **Single buffer** — load and compute serialize.
9. **Ping-pong** — two banks overlap loading and MAC work.
10. **Fixed four-bank baseline** — round-robin EMPTY/READY arbitration.
11. **Static cyclic proxy** — fixed modulo assignment under the same hardware.
12. **Fixed-depth limitation** — stable workloads need only two eligible banks.
13. **Runtime architecture** — observation, hysteresis, bank limit, scheduler.
14. **Bank FSM** — EMPTY → LOADING → READY → COMPUTING → EMPTY.
15. **Adaptation FSM** — 32-clock window, high 8, low 2.
16. **Verification** — 14/14 functional, 129/129 performance, 103 unchanged.
17. **Fixed timing results** — 640/361/361 cycles at 8/8 and 32 tiles.
18. **Variable timing results** — 922/539/497 cycles at 8/8 and 32 tiles.
19. **Bank scaling** — variable case saturates at three banks.
20. **Stable runtime results** — fixed-four timing at average depth ~2.
21. **Variable runtime result** — 1025 versus 983 cycles, average depth 2.50.
22. **Phase result and waveform** — 2033 versus 1991 cycles, 2→3→4→2.
23. **Equal-word fairness** — both designs have 16 physical RAM words;
   usable tile slots differ.
24. **Conclusions and limitations** — buffering helps under variable latency;
   runtime depth trades 2–4% cycles for lower eligibility, not measured power.

Source plots are in `results/plots` and VCDs in `results/waveforms`. The
PowerPoint uses native editable charts and tables for quantitative evidence.
