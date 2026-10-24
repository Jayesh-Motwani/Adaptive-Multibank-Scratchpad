# Limitations and future work

- Behavioral synchronous RAM is an RTL scratchpad model, not a physical SRAM
  circuit or macro. No place-and-route, post-layout timing, area, or power
  measurement was performed.
- The loader abstracts effective tile transfer latency. It does not implement
  a DRAM protocol, cache, coherence, burst arbitration, or a full CNN pipeline.
- One loader and one MAC limit throughput. In memory-bound cases, more banks
  cannot increase the single transfer interface's service rate.
- The 8-bit operand MAC and tile sizes are a simplified consumer. Larger
  application dataflows may change queue behavior.
- Runtime mode changes alter *eligibility for new allocations* only. All four
  RAM banks physically exist throughout. Average active bank limit is a
  buffering-depth metric, not measured dynamic or leakage power savings.
- Fixed 32-clock observation windows with 8/2 stall thresholds were chosen
  for the evaluated latency scale. Startup fill briefly raises the mode even
  in stable compute-bound conditions; bursty cases can change mode at many
  successive windows. Alternative thresholds and phase detection merit study.
- Extra physical words in the equal-storage ping-pong test are unused because
  the architecture holds one tile per bank; the experiment cannot equate
  effective tile slots.
- Cross-paper published metrics involve full accelerators, distinct workloads,
  and different silicon. They are qualitative context, not directly comparable
  to simulated tile cycles.

Future work could add multiple transfer channels, queued tiles per bank,
measured memory traffic, synthesis with a target technology, post-layout
power/timing, and traces from a real neural network workload. An adaptation
policy could also distinguish initial fill from sustained starvation.
