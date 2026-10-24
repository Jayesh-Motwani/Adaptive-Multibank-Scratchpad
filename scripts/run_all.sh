#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python3 scripts/run.py test
python3 scripts/run.py experiments
python3 scripts/analyze_results.py
python3 scripts/generate_plots.py
python3 scripts/generate_paper_diagrams.py
