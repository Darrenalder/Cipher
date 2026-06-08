"""Wortlisten je Sprache fuer das Data Poisoning (siehe ``browser/decoy.py``).

Die grossen Listen liegen pro Sprache in ``<lang>.py`` (de/en/fr/es/it), damit ``decoy.py``
schlank bleibt (Logik getrennt von Daten). Jede Sprachdatei definiert drei Listen:

* ``CITIES``     – Stadtnamen, in der jeweiligen Sprache geschrieben (lowercase)
* ``TEMPLATES``  – Such-Vorlagen mit genau einem ``{}`` (Platz fuer eine Stadt), lowercase
* ``STANDALONE`` – themenbezogene Anfragen ohne Ort, lowercase

Hier werden sie zu Dicts ``{lang: [...]}`` zusammengefuehrt und dabei dedupliziert
(reihenfolge-erhaltend), sodass Wiederholungen die Zufallsauswahl nicht verzerren.
"""

from . import de, en, fr, es, it

_LANGS = {"de": de, "en": en, "fr": fr, "es": es, "it": it}


def _norm(xs):
    """Normalisieren (strip + lowercase) und Duplikate entfernen, Reihenfolge erhalten."""
    return list(dict.fromkeys(s.strip().lower() for s in xs))


CITIES = {lang: _norm(mod.CITIES) for lang, mod in _LANGS.items()}
TEMPLATES = {lang: _norm(mod.TEMPLATES) for lang, mod in _LANGS.items()}
STANDALONE = {lang: _norm(mod.STANDALONE) for lang, mod in _LANGS.items()}
