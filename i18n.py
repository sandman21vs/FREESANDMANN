"""Internacionalização (PT/EN/DE) simples com arquivos JSON."""
import json
import os

_translations = {}
_SUPPORTED = ("pt", "en", "de")
_DEFAULT = "pt"


def _load():
    for lang in _SUPPORTED:
        path = os.path.join(os.path.dirname(__file__), "translations", f"{lang}.json")
        with open(path, encoding="utf-8") as f:
            _translations[lang] = json.load(f)


_load()


def get_lang(session, request):
    """Determina idioma: session > Accept-Language > padrão pt."""
    if session.get("lang") in _SUPPORTED:
        return session["lang"]
    accept = request.headers.get("Accept-Language", "")
    for part in accept.split(","):
        code = part.strip().split(";")[0].split("-")[0].lower()
        if code in _SUPPORTED:
            return code
    return _DEFAULT


def t(key, lang):
    """Traduz uma chave para um idioma."""
    return _translations.get(lang, _translations[_DEFAULT]).get(key, key)
