## Purpose

Documents and enforces the actual minimum Python version the script requires, tied to a specific concrete language or standard-library feature, so the stated requirement never silently drifts out of sync with the code again.

## ADDED Requirements

### Requirement: Documented and Accurate Minimum Python Version
The system's documented minimum Python version (README, Homebrew formula, script docstring) SHALL match the actual minimum version required to run the script without error, and SHALL state the specific language/stdlib feature responsible for the floor.

#### Scenario: Script runs on the documented minimum version
- **WHEN** the script is imported and run on the documented minimum Python version
- **THEN** it starts without raising an import-time or startup-time exception.

#### Scenario: Version floor is explained
- **WHEN** a user reads the README or script docstring for the minimum Python version requirement
- **THEN** they find the specific feature (e.g. `asyncio.to_thread`, added in Python 3.9) that sets the floor, not just a bare version number.

#### Scenario: Annotation syntax does not silently raise the floor
- **WHEN** type annotations using newer syntax (e.g. PEP 604 `X | Y` unions) are used in the source
- **THEN** annotation evaluation is deferred (e.g. via `from __future__ import annotations`) so such syntax does not impose a higher runtime floor than the features actually being used at runtime require.
