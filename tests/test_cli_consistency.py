"""
Tests that CLI arguments in argparse match the README CLI Reference table.

Catches:
- A new flag added to argparse but not documented in README
- A stale flag left in README after removal from argparse
- A default value in README that drifts from the argparse default
- A store_true flag shown with a value other than 'off' in README
"""
import argparse
import re
import os

import pytest

from ping_checker import _build_parser

README_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "README.md")

# Flags that exist in argparse but are intentionally absent from the README table
_EXCLUDED = {"--help", "--version"}


def _readme_table_flags() -> dict[str, str]:
    """Parse the CLI Reference table from README.md.

    Returns {--flag: default_str} for every row whose first column
    contains a backtick-quoted ``--flag``.
    """
    with open(README_PATH, encoding="utf-8") as fh:
        content = fh.read()

    result: dict[str, str] = {}
    for line in content.splitlines():
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 2:
            continue
        flags = re.findall(r"`(--[\w-]+)`", cols[0])
        if not flags:
            continue
        # Strip backticks and whitespace from the default column
        default = cols[1].strip("`").strip()
        for flag in flags:
            result[flag] = default
    return result


def _parser_flags() -> dict[str, argparse.Action]:
    """Return {--flag: action} for all non-meta flags in _build_parser()."""
    parser = _build_parser()
    result: dict[str, argparse.Action] = {}
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._VersionAction)):
            continue
        for opt in action.option_strings:
            if opt.startswith("--"):
                result[opt] = action
    return result


class TestCliConsistency:
    def test_all_argparse_flags_documented(self):
        """Every --flag defined in argparse must appear in the README CLI table."""
        missing = _parser_flags().keys() - _readme_table_flags().keys() - _EXCLUDED
        assert not missing, (
            f"Flags in argparse but missing from README CLI table: {sorted(missing)}"
        )

    def test_no_stale_readme_flags(self):
        """Every --flag in the README CLI table must exist in argparse."""
        stale = _readme_table_flags().keys() - _parser_flags().keys()
        assert not stale, (
            f"Flags in README CLI table but not in argparse: {sorted(stale)}"
        )

    def test_store_true_flags_show_off(self):
        """Flags with action='store_true' (default False) must show 'off' in README."""
        readme = _readme_table_flags()
        for flag, action in _parser_flags().items():
            if not isinstance(action, argparse._StoreTrueAction):
                continue
            readme_default = readme.get(flag, "<missing>")
            assert readme_default == "off", (
                f"{flag} is store_true but README shows '{readme_default}' (expected 'off')"
            )

    def test_numeric_defaults_match_readme(self):
        """Numeric argparse defaults must match the value shown in the README table."""
        readme = _readme_table_flags()
        for flag, action in _parser_flags().items():
            if flag not in readme:
                continue
            if not isinstance(action.default, (int, float)) or isinstance(action.default, bool):
                continue
            readme_val = readme[flag]
            try:
                readme_num = float(readme_val)
            except ValueError:
                pytest.fail(
                    f"{flag}: argparse default is {action.default!r} "
                    f"but README shows '{readme_val}' which is not numeric"
                )
            assert float(action.default) == readme_num, (
                f"{flag}: argparse default {action.default!r} != README '{readme_val}'"
            )

    def test_string_defaults_match_readme(self):
        """String argparse defaults must match the README table."""
        readme = _readme_table_flags()
        for flag in ("--target-pool",):
            action = _parser_flags().get(flag)
            if action is None or flag not in readme:
                continue
            assert action.default == readme[flag], (
                f"{flag}: argparse default {action.default!r} != README '{readme[flag]}'"
            )

    def test_optional_override_defaults_match_readme(self):
        """Optional string overrides (default None) must show 'off' in README."""
        readme = _readme_table_flags()
        for flag in ("--isp-target", "--target-direct", "--zscaler-target", "--target-zscaler"):
            action = _parser_flags().get(flag)
            if action is None or flag not in readme:
                continue
            assert readme[flag] == "off", (
                f"{flag}: optional override default {action.default!r} != README '{readme[flag]}'"
            )
