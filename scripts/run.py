"""Compile pure Verilog with Icarus, check tiles, and persist simulator metrics."""
from __future__ import annotations
import argparse
import csv
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RTL = sorted((ROOT / "rtl").glob("*.v"))
TB = ROOT / "tb" / "tb_controller.v"
BUILD = ROOT / "results" / "build"
RAW = ROOT / "results" / "raw"
CSV = ROOT / "results" / "csv"
WAVES = ROOT / "results" / "waveforms"
POLICIES = {0: "single", 1: "pingpong", 2: "fixed4_availability",
            3: "static_multibank", 4: "runtime_adaptive"}
FIELDS = ["case", "category", "architecture", "policy", "banks", "tiles",
          "tile_size", "bank_depth_words", "total_storage_words",
          "mem_cycles", "compute_cycles", "variable_latency",
          "latency_profile", "obs_window", "stall_high_threshold",
          "stall_low_threshold", "lookahead_load", "lookahead_compute",
          "total_cycles", "load_active_cycles", "compute_active_cycles",
          "compute_idle_cycles", "stall_cycles", "tiles_completed",
          "total_mac_operations", "compute_utilization_pct", "throughput_tiles_per_cycle",
          "stall_fraction", "speedup_vs_single", "speedup_vs_pingpong",
          "normalized_time_vs_single", "active_bank_limit_final",
          "average_active_banks", "time_in_2_bank_mode",
          "time_in_3_bank_mode", "time_in_4_bank_mode", "mode_transitions",
          "no_ready_stall_cycles", "status"]

def locate(name):
    env = os.environ.get(name.upper())
    if env:
        return env
    local = ROOT / "tools" / "iverilog" / "bin" / (name + ".exe")
    return str(local) if local.exists() else shutil.which(name)

def run_case(case, category, policy, banks, tiles, tile_size, mem, comp, variable=0,
             wave=False, profile=0, obs=32, high=8, low=2,
             addr_width_override=None, lookahead_load=0, lookahead_compute=0,
             trace_handoff=False):
    iverilog, vvp = locate("iverilog"), locate("vvp")
    if not iverilog or not vvp:
        raise RuntimeError("Icarus iverilog/vvp missing; set IVERILOG and VVP or install in tools/iverilog/bin")
    for p in (BUILD, RAW, CSV, WAVES):
        p.mkdir(parents=True, exist_ok=True)
    executable = BUILD / (case + ".vvp")
    addr_width = (max(1, (tile_size - 1).bit_length()) if addr_width_override is None
                  else addr_width_override)
    if (1 << addr_width) < tile_size:
        raise ValueError("bank depth must fit the tile")
    params = dict(POLICY=policy, BANK_COUNT=banks, NUMBER_OF_TILES=tiles,
                  TILE_SIZE=tile_size, ADDR_WIDTH=addr_width,
                  MEMORY_TRANSFER_CYCLES=mem, COMPUTE_CYCLES=comp,
                  VARIABLE_LATENCY=variable, LATENCY_PROFILE=profile,
                  OBS_WINDOW=obs, STALL_HIGH_THRESHOLD=high,
                  STALL_LOW_THRESHOLD=low, LOOKAHEAD_LOAD=lookahead_load,
                  LOOKAHEAD_COMPUTE=lookahead_compute,
                  TRACE_HANDOFF=int(trace_handoff))
    cmd = [iverilog, "-g2005", "-s", "tb_controller", "-o", str(executable)]
    cmd += [f"-Ptb_controller.{key}={val}" for key, val in params.items()]
    cmd += [str(x) for x in RTL] + [str(TB)]
    build = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if build.returncode:
        raise RuntimeError(f"compile {case}:\n{build.stdout}{build.stderr}")
    sim_cmd = [vvp, str(executable)]
    if wave:
        sim_cmd += ["+VCD=" + str(WAVES / (case + ".vcd"))]
    sim = subprocess.run(sim_cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
    log = sim.stdout + sim.stderr
    (RAW / (case + ".log")).write_text(log, encoding="utf-8")
    if sim.returncode or "STATUS=PASS" not in log or "STATUS=FAIL" in log:
        raise RuntimeError(f"simulation {case} failed (log: {RAW / (case + '.log')})\n{log[-2000:]}")
    values = {}
    for line in log.splitlines():
        if "=" in line and line.count("=") == 1:
            key, value = line.split("=", 1)
            values[key] = value
    if int(values["CHECKS"]) != tiles:
        raise RuntimeError(f"{case}: incorrect check count")
    architecture = POLICIES[policy]
    if lookahead_load or lookahead_compute:
        architecture += f"_lookahead_l{lookahead_load}c{lookahead_compute}"
    row = dict(case=case, category=category, architecture=architecture,
               policy=policy, banks=banks, tiles=tiles, tile_size=tile_size,
               bank_depth_words=1 << addr_width,
               total_storage_words=banks * (1 << addr_width),
               mem_cycles=mem, compute_cycles=comp, variable_latency=variable,
               latency_profile=profile, obs_window=obs,
               stall_high_threshold=high, stall_low_threshold=low,
               lookahead_load=lookahead_load, lookahead_compute=lookahead_compute,
               total_cycles=int(values["TOTAL_CYCLES"]),
               load_active_cycles=int(values["LOAD_ACTIVE_CYCLES"]),
               compute_active_cycles=int(values["COMPUTE_ACTIVE_CYCLES"]),
               compute_idle_cycles=int(values["COMPUTE_IDLE_CYCLES"]),
               stall_cycles=int(values["STALL_CYCLES"]),
               tiles_completed=int(values["TILES_COMPLETED"]),
               total_mac_operations=int(values["TOTAL_MAC_OPERATIONS"]),
               active_bank_limit_final=int(values["ACTIVE_BANK_LIMIT"]),
               average_active_banks=(round(int(values["ACTIVE_BANK_SUM"]) /
                                           int(values["TOTAL_CYCLES"]), 6)
                                     if policy == 4 else banks),
               time_in_2_bank_mode=int(values["TIME_IN_2_BANK_MODE"]),
               time_in_3_bank_mode=int(values["TIME_IN_3_BANK_MODE"]),
               time_in_4_bank_mode=int(values["TIME_IN_4_BANK_MODE"]),
               mode_transitions=int(values["MODE_TRANSITIONS"]),
               no_ready_stall_cycles=int(values["NO_READY_STALL_CYCLES"]),
               status="PASS")
    row["compute_utilization_pct"] = round(100 * row["compute_active_cycles"] / row["total_cycles"], 4)
    row["throughput_tiles_per_cycle"] = round(tiles / row["total_cycles"], 8)
    row["stall_fraction"] = round(row["stall_cycles"] / row["total_cycles"], 6)
    return row

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS)
        writer.writeheader()
        writer.writerows(rows)

def annotate(rows):
    groups = {}
    for row in rows:
        key = (row["category"], row["mem_cycles"], row["compute_cycles"],
               row["tiles"], row["tile_size"], row["variable_latency"],
               row["latency_profile"])
        groups.setdefault(key, {})[row["architecture"]] = row["total_cycles"]
    for row in rows:
        key = (row["category"], row["mem_cycles"], row["compute_cycles"],
               row["tiles"], row["tile_size"], row["variable_latency"],
               row["latency_profile"])
        group = groups[key]
        single = group.get("single")
        pingpong = group.get("pingpong")
        row["speedup_vs_single"] = round(single / row["total_cycles"], 6) if single else ""
        row["speedup_vs_pingpong"] = round(pingpong / row["total_cycles"], 6) if pingpong else ""
        row["normalized_time_vs_single"] = round(row["total_cycles"] / single, 6) if single else ""

def functional():
    cases = [
        ("single_one", 0, 1, 1, 4, 8, 8, 0),
        ("single_many", 0, 1, 32, 4, 16, 8, 0),
        ("pingpong_one", 1, 2, 1, 4, 8, 8, 0),
        ("pingpong_many", 1, 2, 32, 4, 8, 16, 0),
        ("adaptive_2_balanced", 2, 2, 16, 4, 8, 8, 0),
        ("adaptive_4_mem_bound", 2, 4, 32, 4, 32, 8, 0),
        ("adaptive_4_comp_bound", 2, 4, 32, 4, 8, 32, 0),
        ("adaptive_8_variable", 2, 8, 64, 4, 8, 8, 1),
        ("adaptive_3_large_tile", 2, 3, 16, 16, 16, 20, 1),
        ("static_4_variable", 3, 4, 32, 4, 8, 8, 1),
    ]
    for name, policy, banks, tiles, size, mem, comp, var in cases:
        run_case(name, "functional", policy, banks, tiles, size, mem, comp, var,
                 wave=name in {"single_many", "pingpong_many", "adaptive_8_variable", "static_4_variable"})
        print(f"{name}: PASS")
    extra = [
        ("runtime_compute_bound", 64, 8, 20, 0, 0),
        ("runtime_balanced", 64, 8, 8, 0, 0),
        ("runtime_variable", 64, 8, 8, 1, 0),
        ("runtime_phase", 96, 8, 8, 0, 2),
    ]
    for name, tiles, mem, comp, var, profile in extra:
        row=run_case(name,"functional",4,4,tiles,4,mem,comp,var,
                     wave=name=="runtime_phase",profile=profile)
        print(f"{name}: PASS; average active banks={row['average_active_banks']}; "
              f"transitions={row['mode_transitions']}")
    print(f"Functional correctness cases: {len(cases)+len(extra)}/{len(cases)+len(extra)} PASS")

def experiments():
    rows = []
    def quartet(label, category, tiles, size, mem, comp, var=0):
        for policy, banks in ((0,1),(1,2),(2,4),(3,4)):
            rows.append(run_case(f"{label}_{POLICIES[policy]}", category, policy,
                                 banks, tiles, size, mem, comp, var))
    fixed = [(8,8),(16,16),(32,32),(8,4),(16,4),(32,8),(64,8),
             (4,8),(4,16),(8,32),(8,64)]
    for mem, comp in fixed:
        quartet(f"fixed_m{mem}_c{comp}", "fixed", 32, 4, mem, comp)
    for tiles in (4,8,16,32,64):
        quartet(f"tiles_n{tiles}", "tile_count", tiles, 4, 16, 8)
    for size in (8,16,32,64):
        quartet(f"size_{size}", "tile_size", 16, size, max(16,size), max(20,size+2))
    quartet("variable_32", "variable", 32, 4, 8, 8, 1)
    quartet("variable_64", "variable", 64, 4, 8, 8, 1)
    for mem, comp in ((8,8),(8,20),(20,8)):
        for banks in (2,3,4,6,8):
            rows.append(run_case(f"scale_m{mem}_c{comp}_b{banks}", "bank_scaling",
                                 2, banks, 32, 4, mem, comp, 1))
    def adaptation(label, category, tiles, mem, comp, var=0, profile=0):
        for policy,banks in ((0,1),(1,2),(2,4),(3,4),(4,4)):
            rows.append(run_case(f"{label}_{POLICIES[policy]}",category,policy,
                                 banks,tiles,4,mem,comp,var,
                                 wave=category=="phase" and policy==4,
                                 profile=profile))
    adaptation("adapt_compute", "adaptation", 64, 8, 20)
    adaptation("adapt_balanced", "adaptation", 64, 8, 8)
    adaptation("adapt_variable", "adaptation", 64, 8, 8, 1)
    adaptation("adapt_phase", "phase", 96, 8, 8, 0, 2)
    for label,category,tiles,var,profile in (("fair_variable","fair_storage",64,1,0),
                                             ("fair_phase","fair_storage",96,0,2)):
        for policy,banks,width in ((1,2,3),(2,4,2),(4,4,2)):
            rows.append(run_case(f"{label}_{POLICIES[policy]}",category,
                                 policy,banks,tiles,4,8,8,var,profile=profile,
                                 addr_width_override=width))
    annotate(rows)
    write_csv(CSV / "results_summary.csv", rows)
    for category, file in (("fixed", "fixed_latency_results.csv"),
                           ("variable", "variable_latency_results.csv"),
                           ("bank_scaling", "bank_scaling_results.csv"),
                           ("adaptation", "adaptation_results.csv"),
                           ("phase", "phase_results.csv"),
                           ("fair_storage", "equal_storage_results.csv")):
        write_csv(CSV / file, [r for r in rows if r["category"] == category])
    print(f"Performance experiments: {len(rows)}/{len(rows)} completed; failed: 0")
    for category in ("fixed", "variable"):
        sample = [r for r in rows if r["category"] == category and r["tiles"] == 32
                  and r["mem_cycles"] == 8 and r["compute_cycles"] == 8]
        print(category, [(r["architecture"],r["total_cycles"]) for r in sample])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("test", "experiments", "all"))
    args = parser.parse_args()
    if args.command in ("test", "all"):
        functional()
    if args.command in ("experiments", "all"):
        # The requested evidence gate is intentional: run tests before metrics.
        if args.command == "experiments": functional()
        experiments()

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
