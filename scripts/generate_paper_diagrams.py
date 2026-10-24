"""Vector diagrams for the report; no measured data are synthesized here."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pydeps"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT = ROOT / "results" / "plots"
OUT.mkdir(parents=True, exist_ok=True)
NAVY = "#17324b"
BLUE = "#168aad"
ORANGE = "#d86837"
PALE = "#eaf1f5"
LIGHT = "#fdf1e9"
GRAY = "#496173"


def setup(width, height):
    fig, ax = plt.subplots(figsize=(width, height))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def box(ax, x, y, w, h, label, fill=PALE, edge=BLUE, size=8.2, weight="normal"):
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.1, edgecolor=edge, facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=size, color=NAVY, weight=weight, linespacing=1.25)


def arrow(ax, start, end, color=BLUE, style="-|>", rad=0, lw=1.3, dashed=False):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle=style, mutation_scale=10, linewidth=lw,
        color=color, linestyle="--" if dashed else "-",
        connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0,
    ))


def save(fig, stem):
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.05)
    fig.savefig(OUT / f"{stem}.png", dpi=210, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def architecture():
    fig, ax = setup(7.2, 3.55)
    ax.text(0.02, 0.96, "SHARED TILE DATA PATH", fontsize=8.1, weight="bold", color=GRAY)
    box(ax, .02, .62, .10, .20, "Tile\nsource", size=8)
    box(ax, .16, .62, .12, .20, "Single\nloader", size=8)
    box(ax, .33, .57, .29, .32, "", size=8.1)
    ax.text(.475, .83, "Four physical RAM banks", ha="center", va="center",
            fontsize=7.8, color=NAVY, weight="bold")
    for i in range(4):
        box(ax, .35 + i * .065, .61, .047, .12, f"B{i}", fill="white", size=7.1)
    box(ax, .66, .62, .09, .20, "Read\nmux", size=8)
    box(ax, .79, .62, .09, .20, "Single\nMAC", size=8)
    box(ax, .925, .62, .05, .20, "ID +\nsum", size=6.8)
    for a, b in [((.12,.72),(.16,.72)),((.28,.72),(.33,.72)),
                 ((.62,.72),(.66,.72)),((.75,.72),(.79,.72)),
                 ((.88,.72),(.925,.72))]:
        arrow(ax,a,b)
    ax.text(.02,.48,"CONTROL AND OBSERVATION", fontsize=8.1, weight="bold", color=GRAY)
    box(ax, .04, .14, .22, .21, "Bank states + tile IDs\nEMPTY / LOADING\nREADY / COMPUTING", fill=LIGHT, edge=ORANGE, size=7.0)
    box(ax, .38, .14, .22, .21, "Availability arbiter\nselect EMPTY / READY", fill=LIGHT, edge=ORANGE, size=7.2)
    box(ax, .72, .14, .23, .21, "Runtime mode control\n32-cycle stall count\nlimit 2 / 3 / 4", fill=LIGHT, edge=ORANGE, size=7.2)
    arrow(ax,(.26,.245),(.38,.245),ORANGE)
    arrow(ax,(.72,.245),(.60,.245),ORANGE)
    arrow(ax,(.49,.35),(.49,.57),ORANGE,dashed=True)
    arrow(ax,(.41,.57),(.15,.35),ORANGE,rad=.16,dashed=True)
    arrow(ax,(.835,.62),(.835,.35),ORANGE,dashed=True)
    ax.text(.02,.025,"Blue: tile data/result     Orange: allocation decisions and feedback", fontsize=7.1, color=GRAY)
    save(fig,"paper_architecture")


def bank_fsm():
    fig, ax = setup(3.55, 1.75)
    x = [.02,.27,.52,.77]
    for p, name in zip(x,["EMPTY","LOADING","READY","COMPUTING"]):
        box(ax,p,.48,.20,.26,name,size=6.5,weight="bold")
    for i,label in enumerate(["allocate","load done","dispatch"]):
        arrow(ax,(x[i]+.20,.61),(x[i+1],.61))
        ax.text((x[i]+.20+x[i+1])/2,.78,label,ha="center",fontsize=6.4,color=GRAY)
    arrow(ax,(.88,.47),(.13,.47),ORANGE,rad=-.43)
    ax.text(.50,.09,"MAC done / release bank",ha="center",fontsize=7.2,color=ORANGE)
    save(fig,"paper_bank_state_machine")


def mode_fsm():
    fig, ax = setup(3.55, 2.15)
    x=[.06,.415,.77]
    for p,n in zip(x,["LIMIT 2","LIMIT 3","LIMIT 4"]):
        box(ax,p,.40,.17,.26,n,fill=LIGHT,edge=ORANGE,size=7.6,weight="bold")
    for i in (0,1):
        arrow(ax,(x[i]+.17,.60),(x[i+1],.60),ORANGE,rad=.18)
        arrow(ax,(x[i+1],.46),(x[i]+.17,.46),ORANGE,rad=.18)
        ax.text((x[i]+.17+x[i+1])/2,.76,"S ≥ 8",ha="center",fontsize=7.1,color=GRAY)
        ax.text((x[i]+.17+x[i+1])/2,.30,"S ≤ 2",ha="center",fontsize=7.1,color=GRAY)
    ax.text(.50,.96,"Update once per 32-cycle observation window",ha="center",fontsize=8.2,color=NAVY,weight="bold")
    ax.text(.50,.08,"3 ≤ S ≤ 7: hold mode; limits are saturated at 2 and 4",ha="center",fontsize=7.1,color=GRAY)
    save(fig,"paper_mode_state_machine")


if __name__ == "__main__":
    architecture()
    bank_fsm()
    mode_fsm()
    print("Created three vector report diagrams in", OUT)
