"""Zentrales QWebEngineProfile.

Privacy-Politik: keine Google-Schicht (gibt es bei QtWebEngine ohnehin nicht),
Drittanbieter-Cookies werden geblockt, Standardsuche ist Startpage
(echte Google-Ergebnisse, aber anonymisiert).
Das Profil ist persistent (Cookies/Cache lokal im Projektordner) und bekommt
den Handler für die app://newtab-Startseite installiert.
"""

from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

from .paths import PROFILE_DIR

# {} wird mit der URL-kodierten Suchanfrage gefuellt.
SEARCH_ENGINES = {
    "Startpage": "https://www.startpage.com/sp/search?query={}",
    "Google": "https://www.google.com/search?q={}",
    "DuckDuckGo": "https://duckduckgo.com/?q={}",
    "Brave Search": "https://search.brave.com/search?q={}",
    "Bing": "https://www.bing.com/search?q={}",
    "Wikipedia (DE)": "https://de.wikipedia.org/w/index.php?search={}",
}

_search_url = SEARCH_ENGINES["Startpage"]
_block_third_party = True
_profile: QWebEngineProfile | None = None


def set_search_engine(name: str) -> None:
    global _search_url
    _search_url = SEARCH_ENGINES.get(name, _search_url)


def get_search_url() -> str:
    return _search_url


def set_block_third_party(block: bool) -> None:
    global _block_third_party
    _block_third_party = bool(block)


def _cookie_filter(request) -> bool:
    """True = Cookie erlauben. Drittanbieter-Cookies optional blocken."""
    if not _block_third_party:
        return True
    return not request.thirdParty


def get_profile() -> QWebEngineProfile:
    """Liefert das (einmalig erzeugte) gemeinsame Profil."""
    global _profile
    if _profile is not None:
        return _profile

    storage = PROFILE_DIR  # schreibbar (Bundle: %LOCALAPPDATA%\Cipher, nicht read-only Install-Dir)
    storage.mkdir(parents=True, exist_ok=True)

    profile = QWebEngineProfile("own-browser")  # benannt -> persistent
    profile.setPersistentStoragePath(str(storage))
    profile.setCachePath(str(storage / "cache"))
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
    )

    # Drittanbieter-Cookies (Tracking) blocken.
    profile.cookieStore().setCookieFilter(_cookie_filter)

    # Startseiten-Schema (app://newtab) bedienen.
    from .newtab import get_handler, SCHEME

    profile.installUrlSchemeHandler(SCHEME, get_handler())

    s = profile.settings()
    s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
    # Autoplay erlauben, damit Video-Wallpaper auf der Startseite laufen.
    s.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)

    _profile = profile
    return profile
