"""Regenerate figures from measured CSV; never contains performance constants."""
from __future__ import annotations
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pydeps"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROWS = list(csv.DictReader((ROOT / "results/csv/results_summary.csv").open()))
OUT = ROOT / "results/plots"
OUT.mkdir(parents=True, exist_ok=True)
LABEL = {"single":"Single", "pingpong":"Ping-pong", "fixed4_availability":"Fixed availability (4)",
         "static_multibank":"Static cyclic (4)"}
COLOR = {"single":"#687483", "pingpong":"#168aad", "fixed4_availability":"#db6b33",
         "static_multibank":"#764ca3", "runtime_adaptive":"#bf315b"}
plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10,
                     "axes.spines.top":False, "axes.spines.right":False,
                     "figure.dpi":160, "savefig.dpi":200})

def f(row, key):
    return float(row[key])

def save(name, title, xlabel, ylabel):
    plt.title(title, loc="left", fontweight="bold")
    plt.xlabel(xlabel); plt.ylabel(ylabel)
    plt.grid(alpha=.22); plt.tight_layout()
    for ext in ("png", "pdf"):
        plt.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")
    plt.close()

def lines(name, category, xkey, ykey, title, xlabel, ylabel, filter_fn=lambda r:True):
    plt.figure(figsize=(7.2,4.5))
    rows=[r for r in ROWS if r["category"]==category and filter_fn(r)]
    for arch in LABEL:
        subset=sorted((r for r in rows if r["architecture"]==arch),
                      key=lambda r:f(r,xkey))
        if subset:
            plt.plot([f(r,xkey) for r in subset], [f(r,ykey) for r in subset],
                     "o-", label=LABEL[arch], color=COLOR[arch], linewidth=2)
    plt.legend(frameon=False, ncol=2, fontsize=8)
    save(name,title,xlabel,ylabel)

lines("cycles_vs_memory", "fixed", "mem_cycles", "total_cycles",
      "Execution time with 32 tiles and compute setting 8", "Transfer setting (cycles)",
      "Total cycles", lambda r:r["compute_cycles"]=="8")
lines("stall_vs_memory", "fixed", "mem_cycles", "stall_cycles",
      "Compute idle clocks with 32 tiles and compute setting 8", "Transfer setting (cycles)",
      "Stall cycles", lambda r:r["compute_cycles"]=="8")
lines("cycles_vs_tiles", "tile_count", "tiles", "total_cycles",
      "Execution time as workload grows", "Number of tiles", "Total cycles")

plt.figure(figsize=(7.2,4.5))
fixed=[r for r in ROWS if r["category"]=="fixed"]
for arch in LABEL:
    sub=sorted((r for r in fixed if r["architecture"]==arch),
               key=lambda r:f(r,"mem_cycles")/f(r,"compute_cycles"))
    plt.plot([f(r,"mem_cycles")/f(r,"compute_cycles") for r in sub],
             [f(r,"compute_utilization_pct") for r in sub], "o", label=LABEL[arch],
             color=COLOR[arch], alpha=.8)
plt.xscale("log",base=2); plt.legend(frameon=False,ncol=2,fontsize=8)
save("utilization_vs_ratio","Compute utilization across fixed settings",
     "Configured transfer / compute ratio", "MAC active clocks (%)")

plt.figure(figsize=(7.2,4.5))
ordered=sorted({(int(r["mem_cycles"]),int(r["compute_cycles"])) for r in fixed})
names=[f"{m}/{c}" for m,c in ordered]
for arch in ("pingpong","fixed4_availability","static_multibank"):
    vals=[f(next(r for r in fixed if r["architecture"]==arch and
                 int(r["mem_cycles"])==m and int(r["compute_cycles"])==c),
            "speedup_vs_single") for m,c in ordered]
    plt.plot(range(len(names)),vals,"o-",label=LABEL[arch],color=COLOR[arch])
plt.xticks(range(len(names)),names,rotation=45); plt.legend(frameon=False,fontsize=8)
save("speedup_vs_single","Speedup against the same-workload single bank",
     "Transfer / compute setting", "Single cycles / architecture cycles")

plt.figure(figsize=(7.2,4.5))
for category in ("fixed","variable"):
    subset=[r for r in ROWS if r["category"]==category and r["architecture"]=="fixed4_availability"]
    names=[f"{r['mem_cycles']}/{r['compute_cycles']} N={r['tiles']}" for r in subset]
    plt.plot(range(len(subset)),[f(r,"speedup_vs_pingpong") for r in subset],"o-",label=category)
plt.axhline(1,color="black",linewidth=.8); plt.legend(frameon=False)
plt.xticks(range(max(len([r for r in ROWS if r["category"]=="fixed" and r["architecture"]=="fixed4_availability"]),
                     len([r for r in ROWS if r["category"]=="variable" and r["architecture"]=="fixed4_availability"]))),
           [str(i+1) for i in range(11)])
save("adaptive_vs_pingpong","Adaptive speedup relative to two banks",
     "Fixed case index (variable cases at indices 1–2)", "Ping-pong cycles / adaptive cycles")

for metric,name,ylabel in (("total_cycles","bank_scaling_cycles","Total cycles"),
                           ("throughput_tiles_per_cycle","bank_scaling_throughput","Tiles per cycle")):
    plt.figure(figsize=(7.2,4.5))
    for m,c in ((8,8),(8,20),(20,8)):
        sub=sorted((r for r in ROWS if r["category"]=="bank_scaling" and
                    r["mem_cycles"]==str(m) and r["compute_cycles"]==str(c)),
                   key=lambda r:int(r["banks"]))
        plt.plot([f(r,"banks") for r in sub],[f(r,metric) for r in sub],"o-",
                 label=f"base {m}/{c}")
    plt.legend(frameon=False)
    save(name,"Variable latency: capacity scaling", "Bank count",ylabel)

plt.figure(figsize=(7.2,4.5))
for arch in LABEL:
    vals=[]
    for category in ("fixed","variable"):
        vals.append(f(next(r for r in ROWS if r["category"]==category and
                           r["architecture"]==arch and r["mem_cycles"]=="8" and
                           r["compute_cycles"]=="8" and r["tiles"]=="32"),
                      "total_cycles"))
    x=list(LABEL).index(arch)
    plt.bar([x-.17,x+.17],vals,width=.32,color=["#a8b5c4",COLOR[arch]])
plt.xticks(range(4),list(LABEL.values()),rotation=12)
plt.legend(["Fixed","Variable"],frameon=False)
save("fixed_vs_variable","Matched 32-tile base 8/8 cases",
     "Architecture", "Total cycles")

adapt=[r for r in ROWS if r["category"] in ("adaptation","phase") and
       r["architecture"] in ("pingpong","fixed4_availability","runtime_adaptive")]
scenarios=[("Stable compute", "adaptation",8,20,0),
           ("Stable balanced", "adaptation",8,8,0),
           ("Variable", "adaptation",8,8,0),
           ("Phase change", "phase",8,8,2)]
for metric,name,ylabel in (("total_cycles","adaptation_cycles","Total cycles"),
                           ("compute_utilization_pct","adaptation_utilization","MAC active clocks (%)"),
                           ("stall_cycles","adaptation_stalls","Compute idle clocks"),
                           ("average_active_banks","adaptation_active_banks","Average active bank limit")):
    plt.figure(figsize=(7.2,4.5))
    for idx,arch in enumerate(("pingpong","fixed4_availability","runtime_adaptive")):
        vals=[]
        for label,cat,mem,comp,profile in scenarios:
            row=next(r for r in adapt if r["category"]==cat and
                     r["architecture"]==arch and r["mem_cycles"]==str(mem) and
                     r["compute_cycles"]==str(comp) and
                     r["latency_profile"]==str(profile) and
                     r["variable_latency"]==str(1 if label=="Variable" else 0))
            vals.append(f(row,metric))
        plt.bar([x+(idx-1)*.25 for x in range(4)],vals,width=.23,
                label={"pingpong":"Ping-pong (2)","fixed4_availability":"Fixed (4)",
                       "runtime_adaptive":"Runtime (2/3/4)"}[arch],color=COLOR[arch])
    plt.xticks(range(4),[s[0] for s in scenarios],rotation=12)
    plt.legend(frameon=False,fontsize=8)
    save(name,"Runtime depth policy across workloads","Workload",ylabel)

trace_path=ROOT / "results/csv/mode_trace.csv"
if trace_path.exists():
    trace=list(csv.DictReader(trace_path.open()))
    plt.figure(figsize=(7.2,3.7))
    plt.step([int(x["cycle"]) for x in trace],
             [int(x["active_bank_limit"]) for x in trace],where="post",
             color=COLOR["runtime_adaptive"],linewidth=2)
    plt.yticks([2,3,4]); plt.ylim(1.7,4.3)
    save("phase_mode_trace","Measured VCD mode transitions (phase workload)",
         "Simulation cycle", "Active bank limit")
print(f"Generated {len(list(OUT.glob('*.png')))} PNG and {len(list(OUT.glob('*.pdf')))} PDF figures")
