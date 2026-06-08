"""Wortlisten je Sprache fuer das Data Poisoning (siehe ``browser/decoy.py``).

Die Listen liegen pro Sprache in mehreren Dateien (damit kein File riesig wird und mehrere
Beitraege parallel entstehen koennen). Pro Sprache ``<lang>`` gibt es:

* ``<lang>.py``           – Basis-Set mit ``CITIES`` / ``TEMPLATES`` / ``STANDALONE``
* ``<lang>_cities.py``    – zusaetzliche ``CITIES``
* ``<lang>_templates.py`` – zusaetzliche ``TEMPLATES`` (jede mit genau einem ``{}``)
* ``<lang>_std_a.py``     – zusaetzliche ``STANDALONE`` (Tech/Wissen)
* ``<lang>_std_b.py``     – zusaetzliche ``STANDALONE`` (Alltag/Leben)

Konventionen je Liste:
* ``CITIES``     – Stadtnamen, in der jeweiligen Sprache geschrieben
* ``TEMPLATES``  – Such-Vorlagen mit genau einem ``{}`` (Platz fuer eine Stadt)
* ``STANDALONE`` – themenbezogene Anfragen ohne Ort

Hier werden alle Module einer Sprache zusammengefuehrt, normalisiert (strip + lowercase) und
dedupliziert (reihenfolge-erhaltend), sodass Wiederholungen die Zufallsauswahl nicht verzerren.
Eine Datei muss nicht alle drei Listen definieren – fehlende werden als leer behandelt.
"""

import importlib

# Reihenfolge je Sprache: Basis zuerst, dann die Erweiterungen.
_LANG_MODULES = {
    "de": ["de", "de_cities", "de_templates", "de_std_a", "de_std_b"],
    "en": ["en", "en_cities", "en_templates", "en_std_a", "en_std_b"],
    "fr": ["fr", "fr_cities", "fr_templates", "fr_std_a", "fr_std_b"],
    "es": ["es", "es_cities", "es_templates", "es_std_a", "es_std_b"],
    "it": ["it", "it_cities", "it_templates", "it_std_a", "it_std_b"],
}


def _norm(xs):
    """Normalisieren (strip + lowercase) und Duplikate entfernen, Reihenfolge erhalten."""
    return list(dict.fromkeys(s.strip().lower() for s in xs))


def _collect(lang, attr):
    out = []
    for name in _LANG_MODULES[lang]:
        mod = importlib.import_module(f"{__name__}.{name}")
        out.extend(getattr(mod, attr, ()))
    return _norm(out)


CITIES = {lang: _collect(lang, "CITIES") for lang in _LANG_MODULES}
TEMPLATES = {lang: _collect(lang, "TEMPLATES") for lang in _LANG_MODULES}
STANDALONE = {lang: _collect(lang, "STANDALONE") for lang in _LANG_MODULES}
