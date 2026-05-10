"""i18n compatibility shim — delegates to src.shared.i18n."""
from src.shared.i18n import t as _, get_current_lang, get_available_languages, TRANSLATIONS, DEFAULT_LANG, _normalize_lang


def set_language(lang: str) -> None:
    """Set current language, persisting to config.

    Accepts both 'zh_CN' (old format) and 'zh' (new format).
    """
    lang = _normalize_lang(lang)
    try:
        from src.config import get_config
        config = get_config()
        config.language = lang
    except Exception:
        pass  # Config unavailable; language is set only for this session
