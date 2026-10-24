# Verified published results and comparability

These values were checked against the original publisher page or an author-hosted
manuscript. They are **not** measurements from this repository. The papers use
different workloads, datapaths, processes, and baselines. No published value
below can be compared directly with this project's simulated tile cycles.

| Work | Exact source and location | Reported condition and value | Comparison |
|---|---|---|---|
| Chen et al., *Eyeriss: An Energy-Efficient Reconfigurable Accelerator for Deep Convolutional Neural Networks*, IEEE JSSC, 2017, DOI [10.1109/JSSC.2016.2616357](https://doi.org/10.1109/JSSC.2016.2616357) | IEEE abstract | AlexNet convolutional layers, batch 4: **35 frames/s**, **0.0029 DRAM accesses/MAC**, **278 mW**; VGG-16, batch 3: **0.7 frames/s**, **0.0035 DRAM accesses/MAC**, **236 mW**. | QUALITATIVE. This project models neither frames, DRAM traffic, nor power. |
| Jouppi et al., *In-Datacenter Performance Analysis of a Tensor Processing Unit*, ISCA 2017, DOI [10.1145/3079856.3080246](https://doi.org/10.1145/3079856.3080246) | [Original manuscript abstract](https://arxiv.org/abs/1704.04760), also [author paper PDF](https://www.mit.edu/~kepner/Academic-ML-Papers/VeryNew/Jouppi2017.pdf) | Production MLP/CNN/LSTM inference: TPU about **15–30× faster** than contemporary GPU or CPU and **30–80× TOPS/W**. The comparison baselines are the paper's server CPU and GPU, not this project's controller. | QUALITATIVE. The relative numbers have a different denominator and include a full accelerator. |
| Chen et al., *Eyeriss v2: A Flexible Accelerator for Emerging Deep Neural Networks on Mobile Devices*, IEEE JETCAS 9(2), 2019, DOI [10.1109/JETCAS.2019.2910232](https://doi.org/10.1109/JETCAS.2019.2910232) | [Author manuscript abstract](https://eems.mit.edu/wp-content/uploads/2019/04/2019_jetcas_eyerissv2.pdf) | Sparse MobileNet, batch 1, 65 nm process: **1470.6 inferences/s**, **2560.3 inferences/J**, **12.6× faster** and **2.5× more energy efficient** than original Eyeriss running MobileNet. | QUALITATIVE. The full model, sparsity and silicon data cannot be mapped to tile-level cycles. |

## Literature comparison

| Reference | Memory organization and strategy | Workload | Strength relevant here | Key limit for this project |
|---|---|---|---|---|
| Eyeriss | Distributed local storage and row-stationary reuse | CNN convolutions | Shows the importance of local data reuse and DRAM traffic | No matching tile-controller timing experiment |
| TPU | Large software-controlled on-chip memory feeding systolic matrix unit | Datacenter inference | Shows a real accelerator with significant local memory | Full-system speedup cannot isolate buffering policy |
| Eyeriss v2 | Flexible hierarchical on-chip network and compressed sparse execution | Sparse MobileNet | Shows value of flexibility under variable layer shapes | Network and sparsity changes confound any bank-controller comparison |

The controlled internal comparison in this repository, once simulated, is the
only direct test of the scheduling question. The generic static cyclic
multi-bank policy is a **literature-inspired RTL baseline** in the sense of
representing static assignment and in-order consumption. It is explicitly a
simplified proxy, not an Eyeriss, TPU, or Eyeriss v2 reproduction.
