$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    python scripts/run.py test
    if ($LASTEXITCODE -ne 0) { throw 'Functional regression failed' }
    python scripts/run.py experiments
    if ($LASTEXITCODE -ne 0) { throw 'Experiment sweep failed' }
    python scripts/analyze_results.py
    if ($LASTEXITCODE -ne 0) { throw 'Analytical checks failed' }
    python scripts/generate_plots.py
    if ($LASTEXITCODE -ne 0) { throw 'Plot generation failed' }
    python scripts/generate_paper_diagrams.py
    if ($LASTEXITCODE -ne 0) { throw 'Paper diagram generation failed' }
    Write-Host 'RTL, experiments, analytical checks, plots, and paper diagrams completed.'
    Write-Host 'Build slides with the bundled Node runtime and compile paper.tex with LaTeX or Overleaf.'
} finally {
    Pop-Location
}
