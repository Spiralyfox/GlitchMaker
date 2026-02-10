"""Translation system — loads lang JSON, provides t() function."""
import json, os, sys

_strings: dict = {}
_lang: str = "en"

# Resolve lang directory: works both normally and when frozen by PyInstaller
if getattr(sys, 'frozen', False):
    _LANG_DIR = os.path.join(sys._MEIPASS, "lang")
else:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    _LANG_DIR = os.path.join(os.path.dirname(_THIS_DIR), "lang")

def set_language(lang: str) -> bool:
    """Charge le fichier de traduction pour la langue donnée."""
    global _strings, _lang
    _lang = lang
    path = os.path.join(_LANG_DIR, f"{lang}.json")
    if not os.path.isfile(path):
        path = os.path.join(_LANG_DIR, "en.json")
    if not os.path.isfile(path):
        _strings = {}; return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            _strings = json.load(f)
        return True
    except Exception:
        _strings = {}; return False

def get_language() -> str:
    """Retourne le code langue actuel (ex : "fr")."""
    return _lang

def t(key: str, **kw) -> str:
    """Traduit une clé (ex : "menu.file") avec substitution optionnelle."""
    text = _strings.get(key)
    if text is None:
        return key.split(".")[-1].replace("_", " ").capitalize()
    if kw:
        try: text = text.format(**kw)
        except (KeyError, IndexError): pass
    return text

set_language("en")
