# VAJRA — judge-facing commands.
#
# `make all`         reproduce every published number, seeded, in order (see below).
# `make demo`        bring up the UI against the committed offline replay bundle (no training).
# Each target is a thin wrapper over a Python module CLI, so a judge can also run any stage directly.
#
# THE PRESET controls scale. `smoke` is wiring only and is stamped NOT REPORTABLE. `small` is the
# committed replay-bundle population. `full` is what the deck quotes. Set with `make all PRESET=full`.
#
# Everything runs single-threaded and seeded on the CI path for byte-reproducibility; the demo path may
# use all cores and says so. `make sensitivity` is deliberately EXCLUDED from `make all` and the
# runtime budget: it re-runs the archive three times.

PY ?= ./.venv/bin/python
PYTHONPATH := .
export PYTHONPATH
PRESET ?= small
VIEW ?= issuer

# Views the visibility ablation trains (never cut). Override with `make train-views VIEWS="issuer acquirer"`.
VIEWS ?= issuer acquirer payee_psp network

.PHONY: help venv grammar sim fidelity train train-views eval loop archive-report duallog verify \
        bench money report bundle all demo api ui test clean sensitivity no-attacks-null generator-b quick-eval

help:
	@echo "VAJRA make targets:"
	@echo "  make venv           create .venv and install requirements"
	@echo "  make grammar        enumerate + type-check + audit the attack grammar (fast)"
	@echo "  make sim            generate the world + run the F1 invariant gate (PRESET=$(PRESET))"
	@echo "  make generator-b    independent cross-generator eval stream (card-CNP + UPI-PAY)"
	@echo "  make fidelity       F1-F6, provenance-badged, -> reports/fidelity.html"
	@echo "  make train          fit GATE-I/GATE-B for one view (VIEW=$(VIEW))"
	@echo "  make train-views    fit every deployment view for the visibility ablation"
	@echo "  make eval           every metric -> reports/metrics.md (leakage suite gates it)"
	@echo "  make loop           run the closed loop: 4 control arms + telemetry"
	@echo "  make archive-report diversity accounting (pre/post-merge coverage)"
	@echo "  make bench          measured end-to-end p99 latency harness"
	@echo "  make money          the MONEY screen data (loop ON/OFF)"
	@echo "  make duallog        render the dual-use reject log"
	@echo "  make verify         scan [VERIFY] markers -> VERIFY_REGISTER.md"
	@echo "  make report         roll every stage's JSON into reports/report.md"
	@echo "  make bundle         assemble the committed offline replay bundle"
	@echo "  make all            everything above, in order, seeded"
	@echo "  make api            serve the FastAPI backend on :8000"
	@echo "  make demo           bring up the UI against the replay bundle (no training)"
	@echo "  make test           run the test suite"
	@echo "  make sensitivity    0.33x/1x/3x mule-cost sweep (SLOW, excluded from make all)"

venv:
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@echo "venv ready. Optional near-line/Treelite/CTGAN deps: pip install -r requirements-optional.txt"

grammar:
	$(PY) -m grammar.cli

sim:
	VAJRA_PRESET=$(PRESET) $(PY) -m sim.cli --preset $(PRESET)

# Generator B: an INDEPENDENTLY authored emitter (card-CNP + UPI-PAY only, different code path, same
# schema), for the cross-generator artifact-independence check.
generator-b:
	$(PY) -m generator_b.cli --preset $(PRESET)

# The Sentinel's benign-drift NULL MODEL: the same world replayed WITHOUT attack campaigns.
no-attacks-null:
	VAJRA_PRESET=$(PRESET) $(PY) -m sim.cli --preset $(PRESET) --generator vajra-sim --no-attacks

fidelity:
	$(PY) -m fidelity.cli

train:
	$(PY) -m gate.cli --view $(VIEW)

train-views:
	@for v in $(VIEWS); do echo "=== training view $$v ==="; $(PY) -m gate.cli --view $$v || exit 1; done

eval:
	$(PY) -m eval.cli --view $(VIEW)

# Headline metrics only, for ITERATING on model quality. Stamped NOT REPORTABLE: no baseline
# replica, no leakage suite, no ablation, no CIs. Minutes instead of hours.
quick-eval:
	$(PY) -m scripts.quick_eval --view $(VIEW) --components

# Refit the FUSION only -- no G1/G2 retrain. First run scores stats+test once and caches the five
# component arrays; after that `make refit-fusion-grid` evaluates any arm in seconds. Read-only until
# you pass ARM, and the previous bundle is copied aside before anything is overwritten.
refit-fusion:
	$(PY) -m scripts.refit_fusion --view $(VIEW)

refit-fusion-grid:
	$(PY) -m scripts.refit_fusion --view $(VIEW) --grid-only

# e.g. make refit-fusion-commit VIEW=issuer ARM=auto
refit-fusion-commit:
	$(PY) -m scripts.refit_fusion --view $(VIEW) --grid-only --write $(ARM)

# Per-rail band diagnosis for a candidate arm, off the cached components. Seconds, read-only.
# ARM defaults to g1_only; compares against the shipped weights so it is like-for-like.
diagnose-bands:
	$(PY) -m scripts.diagnose_bands --view $(VIEW) --arm $(or $(ARM),g1_only)

# How much of the headline does any SINGLE feature explain? Read-only, no refit. Quantifies the
# generator-artifact exposure that the leakage suite structurally cannot see.
artifact-audit:
	$(PY) -m scripts.artifact_audit --view $(VIEW) --top $(or $(TOP),25)

# TICKS drives archive coverage directly: 3 ticks fills 4 of 380 cells, 25 fills ~34.
# The default is the reportable one; override with `make loop TICKS=25` for a fast check.
TICKS ?= 500

loop:
	$(PY) -m loop.cli --ticks $(TICKS)

archive-report:
	$(PY) -m archive.cli

bench:
	$(PY) -m bench.harness

money:
	$(PY) -m scripts.build_money --view $(VIEW)

duallog:
	$(PY) -m scripts.duallog

verify:
	$(PY) -m scripts.verify_register

report:
	$(PY) -m scripts.report

bundle:
	$(PY) -m scripts.build_bundle

# `make all` — the judge's one command. Order matters: sim before fidelity/train, train before eval,
# eval before loop (loop derives its gate difficulty from the trained gate). The leakage suite inside
# `make eval` fails the build if any control fails.
all: grammar sim generator-b fidelity train-views eval loop archive-report money duallog verify bench report bundle
	@echo ""
	@echo "=== make all complete. See reports/report.md for the evidence index. ==="

sensitivity:
	$(PY) -m eval.sensitivity

api:
	$(PY) -m uvicorn api.app:app --host 0.0.0.0 --port 8000

ui:
	cd ui && npm install && npm run dev

# The five-minute demo path: the UI against the committed replay bundle, no training, no network.
demo:
	@echo "Serving the API against the committed replay bundle on :8000, and the UI on :3000."
	@echo "This path touches ONLY committed artifacts, so it works on venue wifi that does not exist."
	$(PY) -m uvicorn api.app:app --host 0.0.0.0 --port 8000 & \
	cd ui && npm install && npm run dev

test:
	$(PY) -m pytest -q tests/

clean:
	rm -rf data reports/*.json reports/*.md reports/*.html
	@echo "cleaned generated data and reports (committed grammar/config/bundle untouched)"
