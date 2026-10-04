"""Handgeschriebene HTML-Parser für strukturlose Leipzig-Stadt-Quellen.

Für Seiten ohne JSON-LD/Feed/API. Jede Funktion nimmt HTML + source_id und
liefert Roh-Event-Dicts im selben Format wie die Extraktoren in extractors.py.
"""
from __future__ import annotations

import html as _html
import re

MONTHS = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
          "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
          "november": 11, "dezember": 12}


def _de_date(text: str) -> str | None:
    """Erstes deutsches Datum (dd.mm.yyyy [hh:mm]) aus Text -> ISO."""
    if not text:
        return None
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    tm = re.search(r"(\d{1,2}):(\d{2})", text)
    hh, mm = (int(tm.group(1)), int(tm.group(2))) if tm else (0, 0)
    return f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:00"


def _clean(s: str | None) -> str | None:
    if s is None:
        return None
    return _html.unescape(re.sub(r"<[^>]+>", "", s)).strip() or None


# ------------------------------------------------------------------ leipzig.de
def parse_leipzig_de(html_text: str, source_id: str) -> list[dict]:
    """TYPO3-Calendarize: <article class="card event-card"> ... </article>.

    Titel in <h3 class="... card-title ...>, Datum/Ort in aufeinanderfolgenden
    <span class="icon-text">-Blöcken (icon 'event' = Datum, 'location_on' = Ort).
    """
    base = "https://www.leipzig.de"
    out = []
    for block in re.findall(r'<article class="card event-card">(.*?)</article>',
                            html_text, re.S):
        href = re.search(r'<a[^>]+href="([^"]+)"', block)
        title = re.search(r'<h3[^>]*card-title[^>]*>(.*?)</h3>', block, re.S)
        if not title:
            continue
        # icon-text-Spans: nach dem inneren <span>ICON</span> folgt <span>WERT</span>
        spans = re.findall(
            r'<span class="icon"[^>]*>(\w+)</span>\s*<span>(.*?)</span>',
            block, re.S)
        date_txt = venue = None
        for icon, val in spans:
            val = _clean(val)
            if icon == "event" and not date_txt:
                date_txt = val
            elif icon == "location_on" and not venue:
                venue = val
        url = href.group(1) if href else None
        if url and url.startswith("/"):
            url = base + url
        out.append({
            "source_id": source_id,
            "source_url": url,
            "title": _clean(title.group(1)),
            "summary": None,
            "start_at": _de_date(date_txt or ""),
            "end_at": None,
            "venue_name": venue,
            "address": venue,
            "price": None,
        })
    return [e for e in out if e["title"]]


# --------------------------------------------------------------- leipzig-im.de
def parse_leipzig_im(html_text: str, source_id: str) -> list[dict]:
    """Karten-Layout (seit 2026): <article class="li-va-karte"> mit Link
    /veranstaltung/<id>/<slug>, Titel <h3 class="li-va-karte-titel">, danach
    meta-Zeilen mit Kalender-Icon (Datum bzw. "von bis") und Ort-Icon (Ort).
    Fällt auf das alte Layout zurück, falls keine Karten gefunden werden.
    """
    base = "https://www.leipzig-im.de"
    out = []
    for block in re.findall(r'<article class="li-va-karte[^"]*">(.*?)</article>',
                            html_text, re.S):
        href = re.search(r'href="([^"]+)"', block)
        title = re.search(r'<h3 class="li-va-karte-titel">(.*?)</h3>', block, re.S)
        if not title:
            continue
        date_txt = venue = None
        for icon, val in re.findall(
                r'icon_(\w+)\.svg"[^>]*>\s*<span>(.*?)</span>', block, re.S):
            val = _clean(val)
            if icon == "kalender" and not date_txt:
                date_txt = val
            elif icon == "ort" and not venue:
                venue = val
        all_dates = re.findall(r"\d{1,2}\.\d{1,2}\.\d{4}", date_txt or "")
        end_at = _de_date(all_dates[-1]) if len(all_dates) > 1 else None
        url = href.group(1) if href else None
        if url and url.startswith("/"):
            url = base + url
        out.append({
            "source_id": source_id,
            "source_url": url,
            "title": _clean(title.group(1)),
            "summary": _clean(_first(r'li-va-karte-untertitel">(.*?)</p>', block)),
            "start_at": _de_date(date_txt or ""),
            "end_at": end_at,
            "venue_name": venue,
            "address": venue,
            "price": "kostenlos" if "li-va-karte-badge-eintrittfrei" in block else None,
        })
    out = [e for e in out if e["title"]]
    return out or _parse_leipzig_im_legacy(html_text, source_id)


def _first(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else None


# --------------------------------------------------------------- leipzig-im.de
def _parse_leipzig_im_legacy(html_text: str, source_id: str) -> list[dict]:
    """PHP-Portal: <div class='navigation'> ... <span class='va_titel'> ...
    zwei <span class='grau'> (Datum, Ort), Link via <a ... href='index.php?...'>.
    """
    base = "https://www.leipzig-im.de/"
    out = []
    for block in re.findall(r"<div class='navigation'>(.*?)</div>",
                            html_text, re.S):
        title = re.search(r"<span class='va_titel'>(.*?)</span>", block, re.S)
        if not title:
            continue
        href = re.search(r"href='(index\.php\?section=details[^']+)'", block)
        graus = re.findall(r"<span class='grau'>(.*?)</span>", block, re.S)
        date_txt = _clean(graus[0]) if graus else None
        venue = _clean(graus[1]) if len(graus) > 1 else None
        url = base + _html.unescape(href.group(1)) if href else None
        # Datumsbereich "… 04.07.2026 bis … 16.08.2026" -> Start = 1., Ende = letztes
        all_dates = re.findall(r"\d{1,2}\.\d{1,2}\.\d{4}", date_txt or "")
        end_at = _de_date(all_dates[-1]) if len(all_dates) > 1 else None
        out.append({
            "source_id": source_id,
            "source_url": url,
            "title": _clean(title.group(1)),
            "summary": None,
            "start_at": _de_date(date_txt or ""),
            "end_at": end_at,
            "venue_name": venue,
            "address": venue,
            "price": None,
        })
    return [e for e in out if e["title"]]


# ------------------------------------------------------------------ urbanite.net
def parse_urbanite(html_text: str, source_id: str) -> list[dict]:
    """Server-gerendertes Listing (nur mit Browser-UA): Event-Teaser-Karten.

    Link `/events/<slug>/<YYYY-MM-DD>/` (Datum in der URL), Titel im title-Attribut,
    Ort im folgenden `event-teaser-location`. Zeit best-effort aus der Datums-Spalte.
    """
    out = []
    for m in re.finditer(
            r'<a[^>]+href="(https://www\.urbanite\.net/events/[a-z0-9-]+/(\d{4}-\d{2}-\d{2})/)"'
            r'[^>]*title="([^"]*)"[^>]*>', html_text):
        url, datestr, title = m.group(1), m.group(2), _clean(m.group(3))
        if not title:
            continue
        tail = html_text[m.end():m.end() + 400]
        vm = re.search(r'event-teaser-location"[^>]*title="([^"]*)"', tail)
        venue = _clean(vm.group(1)) if vm else None
        head = html_text[max(0, m.start() - 500):m.start()]
        tmm = re.findall(r'\b(\d{1,2}:\d{2})\b', head)
        start = f"{datestr}T{tmm[-1]}:00" if tmm else f"{datestr}T00:00:00"
        out.append({
            "source_id": source_id, "source_url": url, "title": title,
            "summary": None, "start_at": start, "end_at": None,
            "venue_name": venue, "address": venue, "price": None,
        })
    return out


# ------------------------------------------------- urbanite.net (Tagesseiten)
def parse_urbanite_day(html_text: str, source_id: str, categories: list[str]) -> list[dict]:
    """Tagesseite /leipzig/events/<datum>/: alle Events des Tages, die Rubrik steht als
    CSS-Klasse `event_category-<slug>` am Artikel (Filter läuft sonst nur per JavaScript).
    Es werden nur Artikel der gewünschten Rubriken übernommen."""
    out = []
    for block in re.findall(
            r'<div class="event-date-\d+ col urbanite-event-teasers-filterable">(.*?)</article>',
            html_text, re.S):
        cls = re.search(r'<article[^>]*class="([^"]*)"', block)
        classes = cls.group(1) if cls else ""
        if not any(f"event_category-{c}" in classes for c in categories):
            continue
        link = re.search(r'<a href="(https://www\.urbanite\.net/events/[a-z0-9-]+/(\d{4}-\d{2}-\d{2})/)"'
                         r'[^>]*title="([^"]*)"', block)
        if not link:
            continue
        url, day, title = link.group(1), link.group(2), _clean(link.group(3))
        tm = re.search(r'<div class="fs-6">\s*(\d{1,2}:\d{2})\s*</div>', block)
        loc = re.search(r'event-teaser-location"[^>]*title="([^"]*)"', block)
        place = _clean(loc.group(1)) if loc else None
        venue = place.split(",", 1)[1].strip() if place and "," in place else place
        out.append({
            "source_id": source_id, "source_url": url, "title": title,
            "summary": None,
            "start_at": f"{day}T{tm.group(1)}:00" if tm else f"{day}T00:00:00",
            "end_at": None,
            "venue_name": venue, "address": place, "price": None,
        })
    return [e for e in out if e["title"]]


# ----------------------------------------------- Theater der Jungen Welt (TYPO3)
def parse_tdjw(html_text: str, source_id: str) -> list[dict]:
    """Spielplan-Liste: <article class="event"> mit Titel-Link, Untertitel,
    <time datetime="…">, Spielort (event-location) und "Alter: 5+" im Body."""
    base = "https://www.theaterderjungenweltleipzig.de"
    out = []
    for block in re.findall(r'<article class="event".*?</article>', html_text, re.S):
        link = re.search(r'<a[^>]*class="event-title"[^>]*href="([^"#]+)[^"]*"[^>]*>(.*?)</a>',
                         block, re.S)
        dt = re.search(r'<time class="time event-date__start" datetime="([^"]+)"', block)
        if not (link and dt):
            continue
        sub = _clean(_first(r'class="event-subtitle">(.*?)</p>', block))
        age = re.search(r"Alter:\s*([^<]+)", block)
        summary = " · ".join(x for x in (sub, f"Alter: {age.group(1).strip()}" if age else None) if x)
        loc = _clean(_first(r'class="event-location">(.*?)</p>', block))
        start = dt.group(1)
        out.append({
            "source_id": source_id, "source_url": base + link.group(1),
            "title": _clean(link.group(2)), "summary": summary or None,
            "start_at": start + ":00" if len(start) == 16 else start, "end_at": None,
            "venue_name": loc or "Theater der Jungen Welt",
            "address": f"{loc}, Leipzig" if loc else "Theater der Jungen Welt, Leipzig",
            "price": None,
        })
    return [e for e in out if e["title"]]


PARSERS = {
    "leipzig_de": parse_leipzig_de,
    "leipzig_im": parse_leipzig_im,
    "urbanite": parse_urbanite,
}
