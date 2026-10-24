PYTHON ?= python
NODE ?= node
TEX ?= pdflatex

.PHONY: test experiments analyze plots lookahead lookahead-plots slides report all
test:
	$(PYTHON) scripts/run.py test

experiments:
	$(PYTHON) scripts/run.py experiments

analyze:
	$(PYTHON) scripts/analyze_results.py

plots:
	$(PYTHON) scripts/generate_plots.py
	$(PYTHON) scripts/generate_paper_diagrams.py

lookahead:
	$(PYTHON) scripts/evaluate_lookahead.py
	$(PYTHON) scripts/generate_lookahead_figures.py
	$(PYTHON) scripts/verify_paper_results.py
	$(PYTHON) scripts/generate_primary_results.py

lookahead-plots:
	$(PYTHON) scripts/generate_lookahead_figures.py
	$(PYTHON) scripts/generate_primary_results.py

slides:
	$(NODE) presentation/build/build_deck.mjs

report: plots lookahead-plots
	cd docs/final_report && $(TEX) -interaction=nonstopmode -halt-on-error paper.tex
	cd docs/final_report && $(TEX) -interaction=nonstopmode -halt-on-error paper.tex

all: test experiments analyze plots slides report
