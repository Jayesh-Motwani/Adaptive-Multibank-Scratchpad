"""Publication figures from checked simulator metrics and event traces."""
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/pydeps"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = ROOT / "results/plots"
rows = list(csv.DictReader((ROOT / "results/csv/lookahead_results.csv").open()))
events = list(csv.DictReader((ROOT / "results/csv/lookahead_handoff_trace.csv").open()))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    for ext in ("pdf", "svg", "png"):
        kwargs = {"dpi": 220} if ext == "png" else {}
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight", pad_inches=.06, **kwargs)
    plt.close(fig)


def find(category, policy, load, compute):
    return next(r for r in rows if r["category"] == category and int(r["policy"]) == policy
                and int(r["lookahead_load"]) == load and int(r["lookahead_compute"]) == compute)


def comparison():
    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    categories = ("compute", "balanced", "memory", "variable", "phase")
    variants = ((2, 0, 0, "RH-F4", "#8795a3"),
                (4, 0, 0, "RH-AD", "#b5bfca"),
                (2, 1, 1, "LH-F4", "#168aad"),
                (4, 1, 1, "LH-AD", "#d86837"))
    width = .18
    for j, (p, l, c, label, color) in enumerate(variants):
        values = [int(find(cat, p, l, c)["total_cycles"]) /
                  int(find(cat, 2, 0, 0)["total_cycles"]) for cat in categories]
        ax.bar([i + (j - 1.5) * width for i in range(len(categories))], values,
               width=width, label=label, color=color)
    ax.axhline(1, color="#496173", lw=.8, linestyle="--")
    ax.set_xticks(range(len(categories)), ["Compute\nbound", "Balanced", "Memory\nbound", "Variable", "Phase\nchange"])
    ax.set_ylabel("Execution cycles / RH-F4 cycles")
    ax.set_ylim(0, 1.18)
    ax.grid(axis="y", alpha=.18)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=2, fontsize=8, loc="upper center", bbox_to_anchor=(.5, 1.24))
    fig.tight_layout()
    save(fig, "lookahead_cycle_comparison")


def timing():
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    specs = (("lookahead_balanced_p2_l0c0", "LOAD", 3, "Fixed 4: loader", "#168aad"),
             ("lookahead_balanced_p2_l0c0", "MAC", 2, "Fixed 4: MAC", "#17324b"),
             ("lookahead_balanced_p4_l1c1", "LOAD", 1, "Proposed: loader", "#168aad"),
             ("lookahead_balanced_p4_l1c1", "MAC", 0, "Proposed: MAC", "#17324b"))
    for case, resource, y, label, color in specs:
        subset = [e for e in events if e["case"] == case and e["resource"] == resource]
        finishes = {e["tile"]: int(e["cycle"]) for e in subset if e["event"] == "FINISH"}
        for e in subset:
            if e["event"] != "ACCEPT":
                continue
            start = int(e["cycle"])
            if start >= 65 or finishes[e["tile"]] > 65:
                continue
            end = finishes[e["tile"]]
            ax.broken_barh([(start, end - start)], (y - .25, .5), facecolors=color,
                           edgecolor="white", linewidth=.6)
            if end - start >= 4:
                ax.text((start + end) / 2, y, f"T{e['tile']}", color="white",
                        fontsize=7.8, ha="center", va="center")
    ax.set_yticks([3, 2, 1, 0], [s[3] for s in specs])
    ax.set_xticks([1 + 8 * i for i in range(9)])
    ax.set_xlim(0, 65)
    ax.set_ylim(-.5, 3.5)
    ax.set_xlabel("Clock edge after reset")
    ax.grid(axis="x", alpha=.2)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    save(fig, "lookahead_handoff_timing")


comparison()
timing()
print("Generated lookahead_cycle_comparison and lookahead_handoff_timing (PDF/SVG/PNG)")
