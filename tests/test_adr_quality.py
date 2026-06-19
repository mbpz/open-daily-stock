"""Tests for ADR documentation quality.

ADRs are the institutional memory of design decisions. They must:
  - have a parseable Status field
  - reference each other when the decision depends on prior work
  - not silently grow stale (every referenced module must still exist)
"""
import re
from pathlib import Path

import pytest


ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"


def _read_adrs():
    return sorted(ADR_DIR.glob("ADR-*.md"))


def test_adr_index_exists():
    """An index file in the ADR directory makes the records discoverable."""
    assert (ADR_DIR / "README.md").exists(), "docs/adr/README.md index missing"


def test_every_adr_listed_in_index():
    """Every ADR file must appear as a row in the index table."""
    adrs = _read_adrs()
    index = (ADR_DIR / "README.md").read_text()
    missing = [a.name for a in adrs if a.name not in index]
    assert missing == [], f"ADRs not listed in README.md index: {missing}"


# Status translations accepted (older ADRs use Chinese headings)
_STATUS_PATTERNS = [
    re.compile(r"^##\s+Status\s*$", re.MULTILINE),
    re.compile(r"^\*\*状态[：:]\s*\*\*", re.MULTILINE),  # "**状态：** 已接受" in older ADRs
]


def test_every_adr_has_status_section():
    """A missing Status makes it ambiguous whether the decision is live."""
    for adr in _read_adrs():
        text = adr.read_text()
        ok = any(p.search(text) for p in _STATUS_PATTERNS)
        assert ok, (
            f"{adr.name} is missing a Status indicator "
            f"(expected '## Status' or '**状态：**' header)"
        )


# Section heading translations: English (new) and Chinese (legacy)
_SECTION_ALIASES = {
    "Context":     ["Context", "背景"],
    "Decision":    ["Decision", "决策"],
    "Consequences": ["Consequences", "后果"],
}


def test_every_adr_has_required_sections():
    for adr in _read_adrs():
        text = adr.read_text()
        for canonical, aliases in _SECTION_ALIASES.items():
            ok = any(
                re.search(rf"^##\s+{re.escape(name)}\s*$", text, re.MULTILINE)
                for name in aliases
            )
            assert ok, (
                f"{adr.name} is missing required section for {canonical} "
                f"(tried: {aliases})"
            )


def test_adr_referenced_modules_still_exist():
    """If an ADR mentions a module path, that path must still exist in the repo.

    Only flags paths that are either (a) *.py files, or (b) directories
    under src/ / gui/ / tests/ that contain a __init__.py or .py file.
    A bare word like `src.notify._chunking` is too ambiguous to assert
    on, so we skip it.
    """
    repo_root = ADR_DIR.parent.parent
    for adr in _read_adrs():
        text = adr.read_text()
        # Only check .py files; this avoids the ambiguity of dotted
        # module references in prose.
        candidates = re.findall(r"`((?:src|gui|tests)/[\w/]+\.py)`", text)
        for path in set(candidates):
            full = repo_root / path
            assert full.exists(), (
                f"{adr.name} references missing path `{path}`"
            )


def test_adr_007_mentions_actual_mixin_path():
    """ADR-007 must reference the actual mixin file we created."""
    adr = ADR_DIR / "ADR-007-async-task-mixin.md"
    text = adr.read_text()
    assert "gui/components/async_task.py" in text
    assert "AsyncTaskMixin" in text


def test_adr_006_mentions_migration_completion_signal():
    """ADR-006 must explain what 'done' means for the migration."""
    adr = ADR_DIR / "ADR-006-notification-migration.md"
    text = adr.read_text()
    # The P7-5 phase must have an explicit definition of done
    assert "P7-5" in text
    # Must mention one of the test signals (deprecation warning) to be measurable
    assert "DeprecationWarning" in text or "deprecation" in text.lower()


def test_adr_numbering_is_sequential():
    """ADR numbers should be 001, 002, ... with no gaps."""
    nums = []
    for adr in _read_adrs():
        m = re.match(r"ADR-(\d+)-", adr.name)
        assert m, f"malformed ADR filename: {adr.name}"
        nums.append(int(m.group(1)))
    expected = list(range(1, len(nums) + 1))
    assert nums == expected, f"ADR numbering should be 1..{len(nums)}; got {nums}"
