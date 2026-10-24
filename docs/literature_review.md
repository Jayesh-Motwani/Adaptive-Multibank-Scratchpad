# Literature review

High arithmetic throughput is useful only when operands arrive on time.
Accelerator designs therefore exploit on-chip storage, tiling, and reuse to
reduce expensive data movement. Sze *et al.* survey the tradeoffs across DNN
hardware platforms and identify data movement and architecture as central
evaluation concerns: [Proceedings of the IEEE, 2017](https://proceedingsoftheieee.ieee.org/efficient-processing-of-deep-neural-networks-a-tutorial-and-survey/).

Eyeriss uses distributed local storage and a row-stationary dataflow to reduce
DRAM accesses; its [JSSC paper](https://doi.org/10.1109/JSSC.2016.2616357)
reports measured CNN frame rate, traffic per MAC, and power. The
[TPU analysis](https://arxiv.org/abs/1704.04760) describes a large
software-controlled on-chip memory feeding a systolic array. These systems
show that local memory organization matters, but neither isolates the simple
tile-buffer scheduling policy evaluated here.

[Eyeriss v2](https://doi.org/10.1109/JETCAS.2019.2910232) adds a flexible
hierarchical on-chip network to handle compact and sparse models with varying
shapes. Its improvement is not attributable solely to bank allocation; it
also changes interconnect, sparsity handling, and the full accelerator.

At the scheduling level, single buffering serializes transfer and compute.
Two-bank ping-pong buffering enables the two stages to overlap. A static
multi-bank mapping can prefetch further, but it may wait for a prescribed
bank even if another bank is empty. Availability-driven allocation chooses
an empty bank and dispatches any ready bank. This project measures when that
extra flexibility changes total cycles under a shared loader and MAC.

The literature motivates the experiment but does not establish a claim that
the proposed policy is new or universally superior. Detailed source values
and comparability are in `previous_work_results.md`.
