"""Extract a real combinational fan-in cone from the Yosys gate netlist.

The schematic shows the next-state logic and flip-flops for the low three
bits of active_bank_limit. Other registers are explicit boundary inputs.
No gate, wire, or connection is invented by this script.
"""

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "results" / "netlist" / "scratchpad_gate.json"
destination = ROOT / "results" / "netlist" / "active_limit_gate_cone.json"
netlist = json.loads(source.read_text(encoding="utf-8"))
top_name, top = next(
    (name, module)
    for name, module in netlist["modules"].items()
    if int(module["attributes"].get("top", "0"), 2) == 1
)

drivers = {}
for name, cell in top["cells"].items():
    for port, bits in cell["connections"].items():
        if cell["port_directions"][port] == "output":
            for bit in bits:
                if isinstance(bit, int):
                    if bit in drivers:
                        raise ValueError(f"Multiple drivers for bit {bit}")
                    drivers[bit] = name

limit_bits = top["netnames"]["active_bank_limit"]["bits"][:3]
target_cells = {drivers[bit] for bit in limit_bits}
selected = set(target_cells)
pending = []
for name in target_cells:
    cell = top["cells"][name]
    pending.extend(
        bit
        for port, bits in cell["connections"].items()
        if cell["port_directions"][port] == "input"
        for bit in bits
        if isinstance(bit, int)
    )

while pending:
    bit = pending.pop()
    name = drivers.get(bit)
    if name is None or name in selected:
        continue
    cell = top["cells"][name]
    # Registers outside the target are boundary inputs of this one-clock cone.
    if "DFF" in cell["type"]:
        continue
    selected.add(name)
    pending.extend(
        input_bit
        for port, bits in cell["connections"].items()
        if cell["port_directions"][port] == "input"
        for input_bit in bits
        if isinstance(input_bit, int)
    )

cut_bits = set()
for name in selected:
    cell = top["cells"][name]
    for port, bits in cell["connections"].items():
        if cell["port_directions"][port] != "input":
            continue
        for bit in bits:
            if isinstance(bit, int) and drivers.get(bit) not in selected:
                cut_bits.add(bit)

public_names = {}
for name, net in top["netnames"].items():
    if net["hide_name"]:
        continue
    for index, bit in enumerate(net["bits"]):
        if isinstance(bit, int):
            label = name if len(net["bits"]) == 1 else f"{name}[{index}]"
            if bit not in public_names or len(label) < len(public_names[bit]):
                public_names[bit] = label

ports = {}
for bit in sorted(cut_bits):
    name = public_names.get(bit, f"boundary_{bit}")
    if name in ports:
        name = f"{name}_{bit}"
    ports[name] = {"direction": "input", "bits": [bit]}
ports["active_bank_limit[2:0]"] = {"direction": "output", "bits": limit_bits}

result = {
    "creator": "Yosys gate cone extracted without changing cell connections",
    "modules": {
        "active_bank_limit_cone": {
            "attributes": {"top": "00000000000000000000000000000001"},
            "ports": ports,
            "cells": {name: top["cells"][name] for name in sorted(selected)},
            "netnames": {
                name: net for name, net in top["netnames"].items()
                if any(bit in limit_bits or bit in cut_bits for bit in net["bits"]
                       if isinstance(bit, int))
            },
        }
    },
}
destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
print("Source top:", top_name)
print("Target bits:", limit_bits)
print("Selected cells:", len(selected))
print("Boundary bits:", len(cut_bits))
print("Selected cell types:", dict(Counter(top["cells"][n]["type"] for n in selected)))
print("Output:", destination)
