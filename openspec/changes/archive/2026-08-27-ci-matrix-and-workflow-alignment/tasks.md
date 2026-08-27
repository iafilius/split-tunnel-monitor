## 1. CI Workflow Matrix Configuration

- [x] 1.1 Update `.github/workflows/tests.yml` to run a matrix strategy across Python 3.9, 3.10, 3.11, 3.12, and 3.13.

## 2. Release & Tap Automation Alignment

- [x] 2.1 Update `.github/workflows/publish-formula.yml` to assert `ping_checker #{version}` in the generated Homebrew formula test block.

## 3. Incident Analysis Tool Recovery State Alignment

- [x] 3.1 Update `.github/skills/zscaler-outage-analysis/incident_report.py` to close open incidents when encountering `HEALTHY` or `INFO` states.

## 4. Verification

- [x] 4.1 Run `pytest -v` and `openspec validate --all` to verify full workspace correctness.
