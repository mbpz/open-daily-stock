"""Test locale files for key parity and translation quality.

P2-3: Multi-language extension — verifies all 4 locale files (zh_CN, en_US,
ja_JP, ko_KR) have identical keys, no empty translations, and no translation
identical to the key name (which would indicate a missing translation).
"""

import json
from pathlib import Path

LOCALES_DIR = Path(__file__).parent.parent / "locales"
REQUIRED_LOCALES = {"zh_CN", "en_US", "ja_JP", "ko_KR"}


def _load_locale(name: str) -> dict:
    path = LOCALES_DIR / f"{name}.json"
    assert path.exists(), f"Missing locale file: {path}"
    with open(path) as f:
        return json.load(f)


def test_all_locale_files_exist():
    """All 4 locale files must be present."""
    existing = {p.stem for p in LOCALES_DIR.glob("*.json")}
    missing = REQUIRED_LOCALES - existing
    assert not missing, f"Missing locale files: {missing}"


def test_all_locales_have_identical_keys():
    """Every locale file must contain the exact same set of keys."""
    locales_data = {name: _load_locale(name) for name in REQUIRED_LOCALES}
    ref_name = "en_US"
    ref_keys = set(locales_data[ref_name].keys())

    for name in REQUIRED_LOCALES - {ref_name}:
        keys = set(locales_data[name].keys())
        missing_keys = ref_keys - keys
        extra_keys = keys - ref_keys
        assert not missing_keys, (
            f"{name} missing keys (vs {ref_name}): {missing_keys}"
        )
        assert not extra_keys, (
            f"{name} has extra keys (vs {ref_name}): {extra_keys}"
        )
        assert ref_keys == keys, (
            f"{name} key set differs from {ref_name}"
        )


def test_no_empty_translations():
    """No translation value may be empty or whitespace-only."""
    for name in REQUIRED_LOCALES:
        data = _load_locale(name)
        for key, value in data.items():
            assert value and value.strip(), (
                f"{name}: key '{key}' has empty translation"
            )


def test_no_translation_equals_key():
    """No translation should be identical to its key name.

    The key is the lookup identifier — if the value equals the key, it means
    the translation was never provided and the raw key would be shown to users.

    zh_CN is excluded because some keys ARE Chinese characters (e.g. 财务报表)
    and their Chinese translation is naturally identical to the key.
    """
    for name in REQUIRED_LOCALES - {"zh_CN"}:
        data = _load_locale(name)
        for key, value in data.items():
            assert value != key, (
                f"{name}: key '{key}' has value identical to key (missing translation)"
            )


def test_locale_key_count():
    """All locale files must have the expected number of keys."""
    ref_data = _load_locale("en_US")
    expected_count = len(ref_data)
    for name in REQUIRED_LOCALES:
        data = _load_locale(name)
        assert len(data) == expected_count, (
            f"{name}: expected {expected_count} keys, got {len(data)}"
        )


def test_ja_jp_uses_japanese_chars():
    """Smoke test: Japanese locale contains kana/kanji."""
    data = _load_locale("ja_JP")
    values = " ".join(data.values())
    # Japanese-specific Unicode ranges: Hiragana, Katakana, CJK
    has_kana = any(
        "぀" <= ch <= "ゟ" or "゠" <= ch <= "ヿ"
        for ch in values
    )
    assert has_kana, "ja_JP values contain no hiragana/katakana"


def test_ko_kr_uses_korean_chars():
    """Smoke test: Korean locale contains Hangul."""
    data = _load_locale("ko_KR")
    values = " ".join(data.values())
    has_hangul = any(
        "가" <= ch <= "힯" for ch in values
    )
    assert has_hangul, "ko_KR values contain no Hangul"
