## Context

See `proposal.md` for motivation. This change addresses three workflow and tooling alignments:
1. Multi-version CI testing in GitHub Actions.
2. Homebrew automated tap release assertion consistency.
3. Post-mortem log parser recovery state alignment with the core monitor's `INFO` classification.

## Goals / Non-Goals

**Goals:**
- Configure matrix testing in `.github/workflows/tests.yml` across Python `3.9`, `3.10`, `3.11`, `3.12`, `3.13`.
- Update formula test string assertion in `.github/workflows/publish-formula.yml` to `assert_match "ping_checker #{version}"`.
- Update `extract_incidents` in `.github/skills/zscaler-outage-analysis/incident_report.py` to close open incidents on `HEALTHY` or `INFO`.

**Non-Goals:**
- Modifying core ping probe mechanics or adding heavy CI dependencies.

## Decisions

### Decision 1: GitHub Actions Strategy Matrix
Use `strategy.matrix.python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]` on `macos-latest` in `.github/workflows/tests.yml`.

### Decision 2: Formula Test String
Match the exact string output produced by `ping_checker.py` `--version` (`ping_checker 1.2.0 ...`) in `.github/workflows/publish-formula.yml`.

### Decision 3: Incident Report Log Classification Handling
In `incident_report.py`, treat `status in ('HEALTHY', 'INFO')` as non-incident states that terminate an active incident sequence.

## Risks / Trade-offs

- **[Risk] CI Runner Time**: Running 5 matrix jobs instead of 1.
  - *Mitigation*: The test suite executes in under 0.2s, so total matrix runtime overhead is negligible.
