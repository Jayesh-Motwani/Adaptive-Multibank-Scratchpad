$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$yosys = Join-Path $projectRoot 'tools/yowasp/bin/yowasp-yosys.exe'
if (-not (Test-Path -LiteralPath $yosys)) { throw 'Install yowasp-yosys into tools/yowasp first.' }
$oldPythonPath = $env:PYTHONPATH
Push-Location $projectRoot
try {
    $env:PYTHONPATH = Join-Path $projectRoot 'tools/yowasp'
    foreach ($name in @('lookahead_legacy_synthesis', 'lookahead_synthesis', 'lookahead_adaptive_synthesis')) {
        & $yosys -Q -T -s "scripts/$name.ys" -l "results/netlist/$name.log" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Yosys failed for $name." }
    }
    python scripts/summarize_lookahead_synthesis.py
    if ($LASTEXITCODE -ne 0) { throw 'Synthesis validation failed.' }
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    Pop-Location
}
