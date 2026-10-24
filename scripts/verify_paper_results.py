"""Fresh RTL audit of every configuration in the paper's main comparison."""
import csv
import hashlib
import json

from run import ROOT, FIELDS, run_case, write_csv
from evaluate_lookahead import METRICS, check_accounting, check_trace


def main():
    evidence = ROOT / "results/csv"
    validation = json.loads((evidence / "lookahead_validation.json").read_text())
    for name, expected_hash in validation["source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected_hash, name
    prior = {r["case"]: r for r in csv.DictReader((evidence / "lookahead_results.csv").open())}
    baseline = {r["case"]: r for r in csv.DictReader((evidence / "results_summary.csv").open())}
    rows = []
    metrics = METRICS + ("compute_utilization_pct", "lookahead_load", "lookahead_compute")
    for label in ("compute", "balanced", "variable", "phase"):
        names = [(f"lookahead_{label}_p{p}_l{h}c{h}", prior)
                 for p in (2, 4) for h in (0, 1)]
        names.append((f"adapt_{label}_pingpong", baseline))
        for name, source in names:
            ref = source[name]
            policy = int(ref["policy"])
            handoff = int(ref.get("lookahead_load") or 0)
            row = run_case("paper_audit_" + name, label, policy, int(ref["banks"]),
                           int(ref["tiles"]), int(ref["tile_size"]),
                           int(ref["mem_cycles"]), int(ref["compute_cycles"]),
                           int(ref["variable_latency"]), profile=int(ref["latency_profile"]),
                           lookahead_load=handoff, lookahead_compute=handoff,
                           trace_handoff=True,
                           wave=label == "phase" and policy == 4 and handoff == 1)
            check_accounting(row)
            check_trace(row)
            for metric in metrics:
                target = float(ref.get(metric) or 0)
                assert abs(float(row[metric]) - target) < 1e-6, (name, metric, row[metric], target)
            rows.append(row)
            print(label, f"policy={policy}", f"lookahead={handoff}",
                  f"cycles={row['total_cycles']}", f"idle={row['compute_idle_cycles']}",
                  "PASS", flush=True)
    write_csv(evidence / "paper_result_audit.csv", rows)
    report = {"fresh_simulations": len(rows), "status": "PASS",
              "comparison": "every audited metric matches the existing measured dataset",
              "checks": ["source hashes", "per-tile arithmetic", "exactly-once issue/completion",
                         "bank ownership", "cycle accounting", "service intervals"],
              "source_sha256": validation["source_sha256"]}
    (evidence / "paper_result_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Fresh paper audit: {len(rows)}/{len(rows)} PASS; measured values reproduced.")


if __name__ == "__main__":
    main()
