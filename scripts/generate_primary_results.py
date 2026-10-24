"""Main-paper comparisons and proposed-policy trace from audited RTL runs."""
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/pydeps"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV = ROOT / "results/csv"
OUT = ROOT / "results/plots"
ROWS = list(csv.DictReader((CSV / "paper_result_audit.csv").open()))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False})


def find(category, policy, handoff):
    return next(r for r in ROWS if r["category"] == category
                and int(r["policy"]) == policy and int(r["lookahead_load"]) == handoff
                and int(r["lookahead_compute"]) == handoff)


def save(fig, name):
    for ext in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight", pad_inches=.06, dpi=220)
    plt.close(fig)


def comparison():
    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    categories = ("compute", "balanced", "variable", "phase")
    variants = ((2, 0, "Fixed 4", "#697889"),
                (4, 1, "Proposed", "#d86837"))
    width = .28
    for j, (policy, handoff, label, color) in enumerate(variants):
        positions = [i + (j - .5) * width for i in range(len(categories))]
        values = [int(find(cat, policy, handoff)["total_cycles"]) for cat in categories]
        bars = ax.bar(positions, values, width=width, color=color, label=label)
        ax.bar_label(bars, padding=3, fontsize=8)
    ax.set_xticks(range(4), ["Compute-bound\n64 tiles", "Balanced\n64 tiles",
                             "Variable latency\n64 tiles", "Phase changes\n96 tiles"])
    ax.set_ylabel("Execution cycles")
    ax.set_ylim(0, 2300)
    ax.grid(axis="y", alpha=.2)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=2, fontsize=9, loc="upper center", bbox_to_anchor=(.5, 1.16))
    fig.tight_layout()
    save(fig, "paper_primary_cycles")


def mode_trace():
    row = find("phase", 4, 1)
    wave = ROOT / "results/waveforms" / f"{row['case']}.vcd"
    symbols, values, trace = {}, {}, []

    def record():
        if "active_bank_limit" in values and "total_cycles" in values:
            point = values["total_cycles"], values["active_bank_limit"]
            if not trace or trace[-1][1] != point[1]:
                trace.append(point)

    for line in wave.read_text().splitlines():
        fields = line.split()
        if line.startswith("$var reg 32") and fields[4] in ("active_bank_limit", "total_cycles"):
            symbols[fields[3]] = fields[4]
        elif line.startswith("#"):
            record()
        elif line.startswith("b") and len(fields) == 2 and fields[1] in symbols:
            bits = fields[0][1:]
            if set(bits) <= {"0", "1"}:
                values[symbols[fields[1]]] = int(bits, 2)
    record()
    end = int(row["total_cycles"])
    assert len(trace) - 1 == int(row["mode_transitions"]), trace
    assert all(0 <= cycle <= end for cycle, _ in trace)
    occupancy = {b: 0 for b in (2, 3, 4)}
    for (a, mode), (b, _) in zip(trace, trace[1:] + [(end, trace[-1][1])]):
        occupancy[mode] += b - a
    for mode, cycles in occupancy.items():
        assert cycles == int(row[f"time_in_{mode}_bank_mode"]), (mode, cycles, row)
    with (CSV / "proposed_phase_mode_trace.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("cycle", "active_bank_limit"))
        writer.writerows(trace + [(end, trace[-1][1])])
    fig, ax = plt.subplots(figsize=(3.55, 2.1))
    points = trace + [(end, trace[-1][1])]
    ax.step([x for x, _ in points], [y for _, y in points], where="post",
            color="#d86837", linewidth=1.4)
    ax.set_xlabel("Execution cycle")
    ax.set_ylabel("Allocation limit")
    ax.set_yticks((2, 3, 4))
    ax.set_ylim(1.8, 4.2)
    ax.set_xlim(0, end)
    ax.grid(alpha=.2)
    fig.tight_layout()
    save(fig, "paper_proposed_phase_trace")
    print("LH-AD phase transitions:", trace)
    print("LH-AD phase occupancy:", occupancy, "total:", end)


comparison()
mode_trace()
