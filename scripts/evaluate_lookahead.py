"""Verify legacy preservation and measure handoff scheduling on the same RTL.

Writes separate evidence files; results_summary.csv and its original logs
remain the historical bank-depth experiment. Every run checks actual MAC
values, exactly-once issue/completion, ownership, and cycle accounting.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from run import FIELDS, ROOT, run_case

CSV = ROOT / "results/csv"
SNAPSHOT = ROOT / "results/baseline_snapshot/pre_lookahead_sources_and_metrics.zip"
METRICS = ("total_cycles", "load_active_cycles", "compute_active_cycles",
           "compute_idle_cycles", "stall_cycles", "tiles_completed",
           "total_mac_operations", "mode_transitions", "average_active_banks",
           "time_in_2_bank_mode", "time_in_3_bank_mode", "time_in_4_bank_mode",
           "no_ready_stall_cycles")
EVENT = re.compile(r"^(LOAD|MAC)_(ACCEPT|FINISH) CYCLE=(\d+) TILE=(\d+) BANK=(\d+)$")


def service_times(tile, row):
    # Independent statement of the existing deterministic workload contract.
    n, size, mem, comp = (int(row[k]) for k in
                         ("tiles", "tile_size", "mem_cycles", "compute_cycles"))
    profile, variable = int(row["latency_profile"]), int(row["variable_latency"])
    if profile == 2:
        middle = n // 3 <= tile < 2 * n // 3
        lm = [0, 16, 0, 10, 22, 1, 4, 19, 0, 12][tile % 10] if middle else 0
        cm = 0 if middle else 12
    elif variable:
        lm = [0, 8, 0, 7, 18, 0, 4, 13, 2, 10][tile % 10]
        cm = [0, 4, 0, 8, 2][tile % 5]
    else:
        lm = cm = 0
    return max(size, mem + lm), max(size + 2, comp + cm)


def fifo_cycles(row, banks=4):
    """Ideal FIFO two-server schedule with finite whole-tile bank slots.

    Each bank is held from load acceptance to compute completion. Both
    servers may hand off on a finishing edge. First acceptance is cycle 1;
    the existing registered result interface retires the last result one
    cycle after completion. No RTL internal counters are used in this model.
    """
    loads, computes = [], []
    for tile in range(int(row["tiles"])):
        load, comp = service_times(tile, row)
        load_start = max(loads[-1] if loads else 1,
                         computes[tile - banks] if tile >= banks else 1)
        load_finish = load_start + load
        compute_finish = max(load_finish, computes[-1] if computes else 1) + comp
        loads.append(load_finish)
        computes.append(compute_finish)
    return computes[-1] + 1


def check_accounting(row):
    n = int(row["tiles"])
    services = [service_times(t, row) for t in range(n)]
    assert row["load_active_cycles"] == sum(x[0] for x in services), row["case"]
    assert row["compute_active_cycles"] == sum(x[1] for x in services), row["case"]
    assert row["total_cycles"] == row["compute_active_cycles"] + row["compute_idle_cycles"]
    assert row["tiles_completed"] == n
    assert row["total_mac_operations"] == n * int(row["tile_size"])
    if int(row["policy"]) == 4:
        assert sum(row[f"time_in_{b}_bank_mode"] for b in (2, 3, 4)) == row["total_cycles"]
    if row["lookahead_load"] and row["lookahead_compute"] and row["policy"] != 4:
        assert row["total_cycles"] == fifo_cycles(row, int(row["banks"])), row["case"]


def check_trace(row):
    events = []
    for line in (ROOT / "results/raw" / f"{row['case']}.log").read_text().splitlines():
        match = EVENT.match(line)
        if match:
            resource, event, cycle, tile, bank = match.groups()
            events.append(dict(case=row["case"], resource=resource, event=event,
                               cycle=int(cycle), tile=int(tile), bank=int(bank)))
    for resource, service_index in (("LOAD", 0), ("MAC", 1)):
        accepts = {e["tile"]: e for e in events
                   if e["resource"] == resource and e["event"] == "ACCEPT"}
        finishes = {e["tile"]: e for e in events
                    if e["resource"] == resource and e["event"] == "FINISH"}
        assert len(accepts) == len(finishes) == int(row["tiles"]), row["case"]
        intervals = []
        for tile in range(int(row["tiles"])):
            a, f = accepts[tile], finishes[tile]
            assert f["cycle"] - a["cycle"] == service_times(tile, row)[service_index], (row["case"], resource, tile)
            assert a["bank"] == f["bank"], (row["case"], resource, tile)
            intervals.append((a["cycle"], f["cycle"]))
        intervals.sort()
        assert all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])), row["case"]
    return events


def write_rows(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)


def legacy_regression():
    with zipfile.ZipFile(SNAPSHOT) as archive:
        old = list(csv.DictReader(io.TextIOWrapper(
            archive.open("results/csv/results_summary.csv"), encoding="utf-8")))
    for prior in old:
        r = run_case("lookahead_regression_" + prior["case"], "lookahead_regression",
                     int(prior["policy"]), int(prior["banks"]), int(prior["tiles"]),
                     int(prior["tile_size"]), int(prior["mem_cycles"]),
                     int(prior["compute_cycles"]), int(prior["variable_latency"]),
                     profile=int(prior["latency_profile"]), obs=int(prior["obs_window"]),
                     high=int(prior["stall_high_threshold"]), low=int(prior["stall_low_threshold"]),
                     addr_width_override=int(prior["bank_depth_words"]).bit_length() - 1)
        check_accounting(r)
        for metric in METRICS:
            assert abs(float(r[metric]) - float(prior[metric])) < 1e-6, (prior["case"], metric, r[metric], prior[metric])
    print(f"Legacy regression: {len(old)} cases retain all {len(METRICS)} checked metrics", flush=True)
    return len(old)


def robustness():
    rows = []
    # One-bank reuse, non-power-of-two banks, minimum service times, odd tile
    # counts, deep RAMs, variable targets, and changes between workload phases.
    for policy, banks in ((0, 1), (1, 2), (2, 3), (2, 4), (2, 8), (3, 4), (4, 4)):
        for label, n, size, mem, comp, variable, profile in (
            ("one", 1, 1, 1, 1, 0, 0),
            ("tight", 17, 4, 4, 6, 0, 0),
            ("large_variable", 19, 16, 16, 18, 1, 0),
            ("phase", 21, 4, 8, 8, 0, 2),
        ):
            for l, c in ((1, 0), (0, 1), (1, 1)):
                r = run_case(f"lookahead_check_p{policy}b{banks}_{label}_l{l}c{c}",
                             "lookahead_correctness", policy, banks, n, size, mem, comp,
                             variable, profile=profile, lookahead_load=l, lookahead_compute=c,
                             trace_handoff=True)
                check_accounting(r)
                check_trace(r)
                rows.append(r)
    write_rows(CSV / "lookahead_correctness.csv", rows, FIELDS)
    print(f"Look-ahead correctness: {len(rows)} configurations PASS", flush=True)
    return len(rows)


def experiments():
    rows, traces = [], []
    for label, n, size, mem, comp, variable, profile in (
        ("compute", 64, 4, 8, 20, 0, 0),
        ("balanced", 64, 4, 8, 8, 0, 0),
        ("memory", 64, 4, 32, 8, 0, 0),
        ("variable", 64, 4, 8, 8, 1, 0),
        ("phase", 96, 4, 8, 8, 0, 2),
        ("minimum", 64, 4, 4, 6, 0, 0),
        ("large_tile", 16, 16, 16, 20, 1, 0),
        ("one_tile", 1, 4, 8, 8, 0, 0),
    ):
        group = []
        for policy in (2, 4):
            for l, c in ((0, 0), (1, 0), (0, 1), (1, 1)):
                r = run_case(f"lookahead_{label}_p{policy}_l{l}c{c}", label,
                             policy, 4, n, size, mem, comp, variable, profile=profile,
                             lookahead_load=l, lookahead_compute=c, trace_handoff=True,
                             wave=label == "balanced" and policy == 2 and l == c)
                check_accounting(r)
                traces.extend(check_trace(r))
                group.append(r)
        legacy = next(r["total_cycles"] for r in group if r["policy"] == 2 and not r["lookahead_load"] and not r["lookahead_compute"])
        fast = next(r["total_cycles"] for r in group if r["policy"] == 2 and r["lookahead_load"] and r["lookahead_compute"])
        for r in group:
            r["cycles_saved_vs_legacy_fixed4"] = legacy - r["total_cycles"]
            r["speedup_vs_legacy_fixed4"] = round(legacy / r["total_cycles"], 6)
            r["cycle_reduction_pct"] = round(100 * (legacy - r["total_cycles"]) / legacy, 4)
            r["gap_vs_lookahead_fixed4_cycles"] = r["total_cycles"] - fast
            r["ideal_four_bank_fifo_cycles"] = fifo_cycles(r)
        rows.extend(group)
    extra = ("cycles_saved_vs_legacy_fixed4", "speedup_vs_legacy_fixed4",
             "cycle_reduction_pct", "gap_vs_lookahead_fixed4_cycles", "ideal_four_bank_fifo_cycles")
    write_rows(CSV / "lookahead_results.csv", rows, FIELDS + list(extra))
    write_rows(CSV / "lookahead_handoff_trace.csv", traces,
               ("case", "resource", "event", "cycle", "tile", "bank"))
    print(f"Look-ahead measurements: {len(rows)} configurations PASS", flush=True)
    return rows


def main():
    regressions = legacy_regression()
    checks = robustness()
    rows = experiments()
    validation = dict(legacy_regression_cases=regressions,
                      legacy_metrics_per_case=len(METRICS),
                      lookahead_correctness_cases=checks,
                      measurement_cases=len(rows),
                      trace_service_checks="all acceptance/completion intervals match unchanged targets",
                      ideal_fifo_check="all full-lookahead nonadaptive cases match independent finite-bank schedule",
                      snapshot_sha256=hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
                      source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in [ROOT / "rtl/scratchpad_controller.v", ROOT / "rtl/mac_engine.v",
                                               ROOT / "tb/tb_controller.v", Path(__file__), ROOT / "scripts/run.py"]})
    (CSV / "lookahead_validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    lines = ["# Measured look-ahead handoff results", "",
             "All rows use four physical banks, one loader, one MAC, identical operands,",
             "and identical per-tile service times. Cycle counts include startup and final retirement.", "",
             "| Workload | Original fixed 4 | Look-ahead fixed 4 | Look-ahead adaptive | Fixed-4 cycle reduction | Adaptive cycle reduction | Adaptive average limit |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label in dict.fromkeys(r["category"] for r in rows):
        group = [r for r in rows if r["category"] == label]
        old = next(r for r in group if r["policy"] == 2 and not r["lookahead_load"] and not r["lookahead_compute"])
        fast = next(r for r in group if r["policy"] == 2 and r["lookahead_load"] and r["lookahead_compute"])
        adaptive = next(r for r in group if r["policy"] == 4 and r["lookahead_load"] and r["lookahead_compute"])
        lines.append(f"| {label} | {old['total_cycles']} | {fast['total_cycles']} | {adaptive['total_cycles']} | {fast['cycle_reduction_pct']:.2f}% | {adaptive['cycle_reduction_pct']:.2f}% | {adaptive['average_active_banks']:.3f} |")
    lines += ["", f"Verification: {regressions} legacy cases retain {len(METRICS)} metrics each;",
              f"{checks} additional correctness cases and {len(rows)} ablation measurements pass.",
              "Every traced load/MAC interval matches its original service target. The complete",
              "look-ahead fixed-bank cases match an independent finite-buffer FIFO schedule.", "",
              "The cycle improvement is due to removing controller handoff bubbles. The adaptive",
              "bank restriction still does not outperform the same look-ahead scheduler with all",
              "four banks available. Report both comparisons. No clock-frequency, power, or",
              "silicon-area claim follows from cycle reduction alone.", "",
              "Machine-readable rows, event traces, and verification hashes are in",
              "`results/csv/lookahead_results.csv`, `lookahead_handoff_trace.csv`, and",
              "`lookahead_validation.json`. Original results_summary.csv remains unchanged."]
    (ROOT / "docs/lookahead_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
