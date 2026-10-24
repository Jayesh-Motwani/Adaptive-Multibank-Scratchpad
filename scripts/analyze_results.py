"""Independent accounting checks and mode transitions parsed from the VCD."""
from __future__ import annotations
import csv
import io
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
CSV=ROOT/"results/csv"
rows=list(csv.DictReader((CSV/"results_summary.csv").open()))

def effective_mem(t,n,size,base,var,profile):
    if profile==2:
        extra=[0,16,0,10,22,1,4,19,0,12][t%10] if n//3<=t<2*n//3 else 0
    elif var:
        extra=[0,8,0,7,18,0,4,13,2,10][t%10]
    else:
        extra=0
    return max(size,base+extra)

def effective_comp(t,n,size,base,var,profile):
    if profile==2:
        extra=12 if t<n//3 or t>=2*n//3 else 0
    elif var:
        extra=[0,4,0,8,2][t%5]
    else:
        extra=0
    return max(size+2,base+extra)

for r in rows:
    n,size,mem,comp,var,profile=(int(r[k]) for k in
        ("tiles","tile_size","mem_cycles","compute_cycles",
         "variable_latency","latency_profile"))
    total=int(r["total_cycles"])
    expected_mem=sum(effective_mem(t,n,size,mem,var,profile) for t in range(n))
    expected_comp=sum(effective_comp(t,n,size,comp,var,profile) for t in range(n))
    assert int(r["load_active_cycles"])==expected_mem, r["case"]
    assert int(r["compute_active_cycles"])==expected_comp, r["case"]
    assert total==int(r["compute_active_cycles"])+int(r["compute_idle_cycles"]),r["case"]
    assert int(r["stall_cycles"])==int(r["compute_idle_cycles"]),r["case"]
    assert int(r["tiles_completed"])==n and int(r["total_mac_operations"])==n*size,r["case"]
    assert total>=max(expected_mem,expected_comp),r["case"]
    if r["architecture"]=="single":
        assert total>=expected_mem+expected_comp,r["case"]
    if r["architecture"]=="runtime_adaptive":
        mode_time=sum(int(r[f"time_in_{b}_bank_mode"]) for b in (2,3,4))
        assert mode_time==total,r["case"]
        mean=sum(b*int(r[f"time_in_{b}_bank_mode"]) for b in (2,3,4))/total
        assert abs(mean-float(r["average_active_banks"]))<1e-5,r["case"]

# Compare every pre-extension run against its archived raw metric summary.
with zipfile.ZipFile(ROOT/"results/baseline_snapshot/pre_adaptation_csv.zip") as archive:
    old=list(csv.DictReader(io.TextIOWrapper(archive.open("results_summary.csv"),encoding="utf-8")))
current={r["case"]:r for r in rows}
metrics=("total_cycles","load_active_cycles","compute_active_cycles",
         "compute_idle_cycles","stall_cycles","tiles_completed","total_mac_operations")
for prior in old:
    key=prior["case"].replace("_adaptive","_fixed4_availability")
    assert key in current,key
    for metric in metrics:
        assert prior[metric]==current[key][metric],(key,metric)

vcd=ROOT/"results/waveforms/adapt_phase_runtime_adaptive.vcd"
assert vcd.exists(),vcd
symbol=None
time_ps=0
trace=[]
for line in vcd.read_text(errors="replace").splitlines():
    if "$var reg 32" in line and "active_bank_limit" in line:
        symbol=line.split()[3]
    elif line.startswith("#"):
        time_ps=int(line[1:])
    elif symbol and line.startswith("b") and line.endswith(" "+symbol):
        bits=line.split()[0][1:]
        if set(bits)<={"0","1"}:
            mode=int(bits,2)
            if not trace or trace[-1][1]!=mode:
                trace.append((time_ps//10000,mode))
assert symbol and trace
sequence=[mode for _,mode in trace]
assert sequence[0]==2 and 3 in sequence and 4 in sequence
assert sequence.index(4)>sequence.index(3)
assert 2 in sequence[sequence.index(4)+1:]
phase=next(r for r in rows if r["case"]=="adapt_phase_runtime_adaptive")
assert len(trace)-1==int(phase["mode_transitions"])
with (CSV/"mode_trace.csv").open("w",newline="") as handle:
    writer=csv.writer(handle)
    writer.writerow(("cycle","active_bank_limit"))
    writer.writerows(trace)
    writer.writerow((int(phase["total_cycles"]),trace[-1][1]))

report=(f"# Analytical checks\n\n"
        f"All {len(rows)} measured runs satisfy independent transfer and MAC "
        f"active-cycle sums, cycle accounting, MAC counts, and throughput lower bounds.\n\n"
        f"All {len(old)} pre-adaptation runs retain the same seven core metrics "
        f"as the archived baseline.\n\n"
        f"The phase VCD has {len(trace)-1} transitions: "
        + ", ".join(f"cycle {cycle}: {mode} banks" for cycle,mode in trace)
        + ". The trace reaches four banks and returns to two.\n")
(ROOT/"docs/analytical_checks.md").write_text(report,encoding="utf-8")
print(report)
