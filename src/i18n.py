import os
import json
from pathlib import Path

_translations = {}
_current_lang = "zh_CN"

def init_i18n():
    global _current_lang
    lang = os.getenv("LANG", "zh_CN")
    if "en" in lang:
        _current_lang = "en_US"
    else:
        _current_lang = "zh_CN"

    # Load translations
    locales_dir = Path(__file__).parent.parent / "locales"
    for lang_file in locales_dir.glob("*.json"):
        with open(lang_file) as f:
            _translations[lang_file.stem] = json.load(f)

def _(key: str) -> str:
    """Translate a key"""
    return _translations.get(_current_lang, {}).get(key, key)

# Initialize on import
init_i18n()