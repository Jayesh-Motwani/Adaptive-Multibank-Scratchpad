$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$yosys = Join-Path $projectRoot 'tools/yowasp/bin/yowasp-yosys.exe'
$netlistsvg = Join-Path $projectRoot 'tools/netlistsvg/node_modules/netlistsvg/bin/netlistsvg.js'
if (-not (Test-Path -LiteralPath $yosys)) { throw 'Install yowasp-yosys into tools/yowasp first.' }
if (-not (Test-Path -LiteralPath $netlistsvg)) { throw 'Install netlistsvg into tools/netlistsvg first.' }

$oldPythonPath = $env:PYTHONPATH
Push-Location $projectRoot
try {
    $env:PYTHONPATH = (Join-Path $projectRoot 'tools/yowasp')
    New-Item -ItemType Directory -Force -Path 'results/netlist', 'results/plots' | Out-Null
    foreach ($name in @('full', 'ram', 'ram_small', 'hier', 'dot')) {
        & $yosys -Q -T -s "scripts/gate_synthesis_$name.ys" -l "results/netlist/gate_synthesis_$name.log" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Yosys failed for $name." }
    }
    python scripts/extract_active_limit_cone.py
    if ($LASTEXITCODE -ne 0) { throw 'Gate-cone extraction failed.' }

    $diagrams = @{
        'sync_ram_2x1_gate' = 'sync_ram_2x1_gate'
        'sync_ram_4x4_gate' = 'sync_ram_4x4_gate'
        'active_limit_gate_cone' = 'active_limit_gate_cone'
        'scratchpad_hierarchy' = 'scratchpad_synth_hierarchy'
    }
    foreach ($entry in $diagrams.GetEnumerator()) {
        & node $netlistsvg "results/netlist/$($entry.Key).json" -o "results/plots/$($entry.Value).svg"
        if ($LASTEXITCODE -ne 0) { throw "NetlistSVG failed for $($entry.Key)." }
    }
    node scripts/render_gate_png.cjs
    if ($LASTEXITCODE -ne 0) { throw 'PNG rendering failed.' }
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    Pop-Location
}
