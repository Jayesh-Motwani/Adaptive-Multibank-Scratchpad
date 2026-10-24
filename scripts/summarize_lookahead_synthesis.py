"""Count generic cells and reject synthesis checks with latches/problems."""
from collections import Counter
import csv
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
rows = []
for variant, stem, script in (
    ("original_fixed4", "lookahead_legacy_fixed4", "lookahead_legacy_synthesis"),
    ("lookahead_fixed4", "lookahead_fixed4", "lookahead_synthesis"),
    ("lookahead_adaptive", "lookahead_adaptive", "lookahead_adaptive_synthesis"),
):
    data = json.loads((ROOT / f"results/netlist/{stem}_gate.json").read_text())
    module = next(m for m in data["modules"].values()
                  if int(m["attributes"].get("top", "0"), 2) == 1)
    types = Counter(c["type"] for c in module["cells"].values())
    log = (ROOT / f"results/netlist/{script}.log").read_text()
    counts = re.findall(r"Found and reported (\d+) problems", log)
    assert counts and all(int(n) == 0 for n in counts), variant
    assert "Warning: Latch inferred" not in log, variant
    assert not any("LATCH" in name for name in types), variant
    rows.append(dict(variant=variant, generic_logic_register_cells=sum(types.values()) - types["$scopeinfo"],
                     scope_metadata_records=types["$scopeinfo"],
                     register_bits=sum(n for name, n in types.items() if "DFF" in name),
                     check_problems=0, inferred_latches=0, banks=4, bank_depth_words=4,
                     tile_size=4, tiles=64, data_width=8, mem_target=8, compute_target=8))
with (ROOT / "results/csv/lookahead_synthesis.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
for row in rows:
    print(row)
