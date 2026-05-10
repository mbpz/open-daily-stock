# -*- coding: utf-8 -*-
"""i18n module tests."""
import pytest
from unittest.mock import patch

from src.shared.i18n import (
    TRANSLATIONS,
    DEFAULT_LANG,
    _normalize_lang,
    get_current_lang,
    t,
    get_available_languages,
)


class TestNormalizeLang:
    """Tests for _normalize_lang helper."""

    def test_normalize_strips_country_suffix(self):
        assert _normalize_lang("zh_CN") == "zh"
        assert _normalize_lang("ja_JP") == "ja"
        assert _normalize_lang("ko_KR") == "ko"

    def test_normalize_strips_dash_suffix(self):
        assert _normalize_lang("zh-CN") == "zh"

    def test_normalize_preserves_two_letter_code(self):
        assert _normalize_lang("zh") == "zh"
        assert _normalize_lang("ja") == "ja"
        assert _normalize_lang("ko") == "ko"

    def test_normalize_handles_whitespace(self):
        assert _normalize_lang("  zh_CN  ") == "zh"


class TestTranslations:
    """Tests for translation data integrity."""

    def test_all_languages_loaded(self):
        assert "zh" in TRANSLATIONS
        assert "ja" in TRANSLATIONS
        assert "ko" in TRANSLATIONS

    def test_all_languages_have_same_keys(self):
        """Verify all language dicts have identical key sets."""
        zh_keys = set(TRANSLATIONS["zh"].keys())
        for lang in ("ja", "ko"):
            assert set(TRANSLATIONS[lang].keys()) == zh_keys, \
                f"Keys mismatch for {lang}"

    def test_no_empty_translations(self):
        """Verify no translation value is empty."""
        for lang_code, lang_dict in TRANSLATIONS.items():
            for key, value in lang_dict.items():
                assert value.strip(), \
                    f"Empty translation: {lang_code}.{key}"


class TestTranslate:
    """Tests for the t() translation function."""

    def test_translate_chinese_default(self):
        assert t("markets.title", lang="zh") == "自选股行情"
        assert t("app.subtitle", lang="zh") == "智能股票分析系统"

    def test_translate_japanese(self):
        assert t("markets.title", lang="ja") == "お気に入り銘柄"
        assert t("app.subtitle", lang="ja") == "スマート株式分析システム"

    def test_translate_korean(self):
        assert t("markets.title", lang="ko") == "관심 종목"
        assert t("app.subtitle", lang="ko") == "스마트 주식 분석 시스템"

    def test_translate_missing_key_returns_key(self):
        assert t("nonexistent.key", lang="zh") == "nonexistent.key"

    def test_translate_missing_lang_falls_back_to_default(self):
        """When lang code is unknown, fall back to DEFAULT_LANG."""
        result = t("markets.title", lang="fr")
        assert result == TRANSLATIONS[DEFAULT_LANG]["markets.title"]

    def test_translate_no_lang_uses_current_lang(self):
        """When lang is None, uses the config current language."""
        result = t("markets.title")
        assert result is not None
        assert result != "markets.title"  # Should find a real translation

    def test_translate_unknown_key_and_lang_returns_key(self):
        """When key is unknown and lang is unknown, return key itself."""
        result = t("completely.bogus.key", lang="zz")
        assert result == "completely.bogus.key"

    def test_translate_app_title_same_for_all(self):
        """'app.title' should be the same in all languages."""
        for lang in ("zh", "ja", "ko"):
            assert t("app.title", lang=lang) == "open-daily-stock"


class TestGetAvailableLanguages:
    """Tests for get_available_languages()."""

    def test_returns_dict(self):
        langs = get_available_languages()
        assert isinstance(langs, dict)
        assert len(langs) == 3

    def test_contains_all_languages(self):
        langs = get_available_languages()
        assert "zh" in langs
        assert "ja" in langs
        assert "ko" in langs

    def test_native_names(self):
        langs = get_available_languages()
        assert langs["zh"] == "中文"
        assert langs["ja"] == "日本語"
        assert langs["ko"] == "한국어"


class TestGetCurrentLang:
    """Tests for get_current_lang()."""

    def test_returns_default_when_no_config(self):
        """Should return DEFAULT_LANG if config is unavailable."""
        with patch("src.config.get_config", side_effect=ImportError):
            assert get_current_lang() == DEFAULT_LANG

    def test_returns_zh_from_config(self):
        """Should return normalized 'zh' when config has 'zh'."""
        mock_config = type("MockConfig", (), {"language": "zh"})()
        with patch("src.config.get_config", return_value=mock_config):
            assert get_current_lang() == "zh"

    def test_normalizes_zh_cn_to_zh(self):
        """Should normalize 'zh_CN' (old default) to 'zh'."""
        mock_config = type("MockConfig", (), {"language": "zh_CN"})()
        with patch("src.config.get_config", return_value=mock_config):
            assert get_current_lang() == "zh"

    def test_normalizes_ja_jp_to_ja(self):
        mock_config = type("MockConfig", (), {"language": "ja_JP"})()
        with patch("src.config.get_config", return_value=mock_config):
            assert get_current_lang() == "ja"

    def test_unknown_lang_falls_back_to_default(self):
        mock_config = type("MockConfig", (), {"language": "fr"})()
        with patch("src.config.get_config", return_value=mock_config):
            assert get_current_lang() == DEFAULT_LANG


class TestDataServiceGetLanguages:
    """Tests for DataService _handle_get_languages."""

    @pytest.fixture
    def service(self):
        from src.data_service import DataService
        return DataService()

    def test_handle_get_languages_success(self, service):
        response = service._handle_get_languages({})
        assert response["status"] == "ok"
        data = response["data"]
        assert "available" in data
        assert "current" in data
        assert data["available"]["zh"] == "中文"
        assert data["available"]["ja"] == "日本語"
        assert data["available"]["ko"] == "한국어"
        assert data["current"] in ("zh", "ja", "ko")


class TestDataServiceSetLanguage:
    """Tests for DataService _handle_set_language."""

    @pytest.fixture
    def service(self):
        from src.data_service import DataService
        return DataService()

    def test_set_language_valid(self, service):
        response = service._handle_set_language({"language": "ja"})
        assert response["status"] == "ok"
        assert "语言已切换为" in response["message"] or "日本語" in response["message"]

    def test_set_language_invalid(self, service):
        response = service._handle_set_language({"language": "fr"})
        assert response["status"] == "error"
        assert "不支持的语言" in response["message"]

    def test_set_language_defaults_to_zh(self, service):
        """When no language specified, defaults to 'zh'."""
        response = service._handle_set_language({})
        assert response["status"] == "ok"
