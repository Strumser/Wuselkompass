"""Geschichteter Extraktor-Stapel (stdlib-only).

Reihenfolge/Priorität:
  1. JSON-LD / schema.org Event   -> extract_jsonld   (universell, CMS-egal)
  2. WordPress "The Events Calendar" REST-API -> wp_events_api
  3. iCal (.ics)                   -> extract_ical
  4. RSS/Atom                      -> extract_rss
Ein Fingerprint entscheidet, welcher Weg pro Quelle sinnvoll ist.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime

from . import fetch

EVENT_TYPES = {
    "event", "theaterevent", "childrensevent", "musicevent", "festival",
    "socialevent", "educationevent", "exhibitionevent", "screeningevent",
    "comedyevent", "danceevent", "familyevent", "visualartsevent",
}


# ---------------------------------------------------------------- Fingerprint
def fingerprint(html_text: str) -> dict:
    h = html_text.lower()
    fp = {
        "wordpress": "wp-content" in h or "wp-json" in h,
        "tribe_events": "tribe-events" in h or "the-events-calendar" in h,
        "typo3": "typo3" in h or "/fileadmin/" in h,
        "kommunal_sn": "/portal/seiten/" in h or "/regional/veranstaltungen/" in h,
        "has_jsonld": "application/ld+json" in h,
        "rss_links": re.findall(r'href=["\']([^"\']+)["\'][^>]*type=["\']application/(?:rss\+xml|atom\+xml)',
                                 html_text, re.I)
                     + re.findall(r'type=["\']application/(?:rss\+xml|atom\+xml)["\'][^>]*href=["\']([^"\']+)["\']',
                                  html_text, re.I),
        "ical_links": re.findall(r'href=["\']([^"\']+\.ics)["\']', html_text, re.I),
    }
    return fp


# ------------------------------------------------------------------- JSON-LD
def _walk_jsonld(node, out):
    """Sammelt rekursiv alle Objekte mit einem *Event-@type.

    Steigt in ALLE verschachtelten Werte ab (z. B. WebPage.mainEntity bei ahoi,
    @graph, subEvent, itemListElement …), nicht nur in bestimmte Schlüssel.
    """
    if isinstance(node, list):
        for x in node:
            _walk_jsonld(x, out)
    elif isinstance(node, dict):
        t = node.get("@type")
        types = [t] if isinstance(t, str) else (t or [])
        if any(str(x).lower() in EVENT_TYPES for x in types):
            out.append(node)
        for v in node.values():
            if isinstance(v, (dict, list)):
                _walk_jsonld(v, out)


def extract_jsonld(html_text: str, source_id: str) -> list[dict]:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text, re.S | re.I)
    events = []
    for raw in blocks:
        raw = raw.strip()
        # gelegentlich mehrere JSON-Objekte / trailing commas
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = json.loads(raw.replace("\n", " "))
            except json.JSONDecodeError:
                continue
        found = []
        _walk_jsonld(data, found)
        for e in found:
            events.append(_norm_jsonld_event(e, source_id))
    return [e for e in events if e]


def _get(v):
    """Nimmt aus schema.org-Feldern robust einen String/Objekt-Namen."""
    if isinstance(v, dict):
        return v.get("name") or v.get("url") or ""
    if isinstance(v, list):
        return _get(v[0]) if v else ""
    return v or ""


def _norm_jsonld_event(e: dict, source_id: str) -> dict | None:
    title = _get(e.get("name"))
    if not title:
        return None
    loc = e.get("location") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    venue_name = _get(loc.get("name")) if isinstance(loc, dict) else _get(loc)
    address = ""
    if isinstance(loc, dict):
        addr = loc.get("address")
        if isinstance(addr, dict):
            parts = [addr.get("streetAddress"), addr.get("postalCode"),
                     addr.get("addressLocality")]
            address = ", ".join(p for p in parts if p)
        elif isinstance(addr, str):
            address = addr
    offers = e.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = None
    if isinstance(offers, dict):
        p = offers.get("price")
        price = ("kostenlos" if str(p) in ("0", "0.0")
                 else (f"{p} {offers.get('priceCurrency', '')}".strip() if p else None))
    desc = _get(e.get("description"))
    return {
        "source_id": source_id,
        "source_url": _get(e.get("url")),
        "title": html.unescape(str(title)).strip(),
        "summary": html.unescape(re.sub(r"<[^>]+>", "", str(desc)))[:400].strip() or None,
        "start_at": _parse_dt(e.get("startDate")),
        "end_at": _parse_dt(e.get("endDate")),
        "venue_name": html.unescape(str(venue_name)).strip() or None,
        "address": address or (venue_name or None),
        "price": price,
    }


# --------------------------------------------------------------- WP Events API
def wp_events_api(base_url: str, source_id: str, per_page: int = 50) -> list[dict]:
    url = f"{base_url}/wp-json/tribe/events/v1/events?per_page={per_page}"
    text = fetch.get(url, use_cache=True, max_age=3 * 3600)
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    out = []
    for e in data.get("events", []):
        venue = e.get("venue") or {}
        if isinstance(venue, list):
            venue = venue[0] if venue else {}
        if not isinstance(venue, dict):
            venue = {}
        cost = e.get("cost")
        price = "kostenlos" if cost in ("", "0", "0,00", None) else str(cost)
        out.append({
            "source_id": source_id,
            "source_url": e.get("url"),
            "title": html.unescape(str(e.get("title", ""))).strip(),
            "summary": html.unescape(re.sub(r"<[^>]+>", "", e.get("excerpt") or e.get("description") or ""))[:400].strip() or None,
            "start_at": _parse_dt(e.get("start_date")),
            "end_at": _parse_dt(e.get("end_date")),
            "venue_name": venue.get("venue"),
            "address": ", ".join(x for x in [venue.get("address"), venue.get("zip"),
                                             venue.get("city")] if x) or venue.get("venue"),
            "price": price,
        })
    return [o for o in out if o["title"]]


# -------------------------------------------------------------- rausgegangen API
def rausgegangen_api(source_id: str, lat=51.3397, lng=12.3731, city="leipzig",
                     pages: int = 15) -> list[dict]:
    """rausgegangen.de: /api/v1/search (näherungssortiert = Leipzig zuerst).

    Antwort: {"results":[{title,category,description,url,...}], "numFound":N}.
    description-Format meist "ORT | 09.07.2026 22:00".
    """
    base = "https://rausgegangen.de"
    out = []
    seen = set()
    for page in range(1, pages + 1):
        url = (f"{base}/api/v1/search?lat={lat}&lng={lng}&city={city}&page={page}")
        text = fetch.get(url, use_cache=True, max_age=3 * 3600)
        if not text:
            break
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            break
        results = data.get("results", [])
        if not results:
            break
        for e in results:
            u = e.get("url") or ""
            if u in seen:
                continue
            seen.add(u)
            desc = e.get("description") or ""
            venue = desc.split("|")[0].strip() if "|" in desc else None
            m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", desc)
            start = None
            if m:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                hh = int(m.group(4)) if m.group(4) else 0
                mm = int(m.group(5)) if m.group(5) else 0
                start = f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:00"
            out.append({
                "source_id": source_id,
                "source_url": base + u if u.startswith("/") else (u or None),
                "title": html.unescape(str(e.get("title", ""))).strip(),
                "summary": (e.get("category") or None),
                "start_at": start,
                "end_at": None,
                "venue_name": venue,
                "address": venue,
                "price": None,
                "categories": e.get("category") or "",
            })
    return [o for o in out if o["title"]]


# -------------------------------------------------------------- kreuzer JSON-API
def _kreuzer_date(datestr, timestr, now):
    """kreuzer liefert 'DD.MM.' ohne Jahr -> ISO (Jahr inferieren)."""
    if not datestr:
        return None
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.", datestr.strip())
    if not m:
        return None
    d, mo = int(m.group(1)), int(m.group(2))
    year = now.year + 1 if mo < now.month else now.year
    tm = re.search(r"(\d{1,2}):(\d{2})", timestr or "")
    hh, mm = (int(tm.group(1)), int(tm.group(2))) if tm else (0, 0)
    return f"{year:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:00"


def kreuzer_api(source_id: str, ressort: str = "kinder-familie", ua=None,
                days: int = 21) -> list[dict]:
    """kreuzer-leipzig.de: /termine/filter (JSON je Ressort), über N Tage iteriert.

    Der Endpunkt liefert je `datestart` die Termine des Tages; wir fragen die
    nächsten `days` Tage ab und dedupen (Titel, Start, Ort)."""
    from datetime import date, timedelta
    now = datetime.now()
    seen, out = set(), []
    for i in range(days):
        day = (date.today() + timedelta(days=i)).isoformat()
        text = fetch.get(f"https://kreuzer-leipzig.de/termine/filter?datestart={day}",
                         max_age=3 * 3600,
                         extra_headers={"X-Requested-With": "XMLHttpRequest",
                                        "Accept": "application/json"}, ua=ua)
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        for e in (data.get(ressort) or {}).get("events", []):
            title = html.unescape(str(e.get("title", "")).strip())
            if not title:
                continue
            summary = html.unescape(re.sub(r"<[^>]+>", "", e.get("text") or ""))[:400].strip() or None
            for d in e.get("dates", []):
                venue = (d.get("venue") or {}).get("name")
                for ln in d.get("lines", []):
                    start = _kreuzer_date(ln.get("date"), ln.get("time"), now)
                    key = (title, start, venue)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({
                        "source_id": source_id,
                        "source_url": f"https://kreuzer-leipzig.de/termine/{ressort}",
                        "title": title, "summary": summary,
                        "start_at": start, "end_at": None,
                        "venue_name": venue, "address": venue, "price": None,
                    })
    return out


# --------------------------------------------- generisch: Listing -> Detail-JSON-LD
def listing_detail_jsonld(source_id: str, listing_url: str, link_re: str,
                          base: str, limit: int = 40, ua=None) -> list[dict]:
    """Holt eine Übersichtsseite, sammelt Detail-Links (link_re) und zieht je
    Detailseite die schema.org/Event-JSON-LD. Für JS-Listings mit server-seitig
    eingebetteten Detail-Links (z. B. rausgegangen-Kategorieseiten).
    """
    page = fetch.get(listing_url, ua=ua)
    if not page:
        return []
    links = []
    for m in re.findall(link_re, page):
        full = m if m.startswith("http") else base + m
        if full not in links:
            links.append(full)
    out = []
    for url in links[:limit]:
        detail = fetch.get(url, max_age=12 * 3600, ua=ua)
        if not detail:
            continue
        for ev in extract_jsonld(detail, source_id):
            if not ev.get("source_url"):
                ev["source_url"] = url
            out.append(ev)
    return out


# ------------------------------------------------------- leipziginfo (Microdata)
def leipziginfo_events(source_id: str, ua=None, limit: int = 50) -> list[dict]:
    """leipziginfo.de (TYPO3): Listing -> Detailseiten mit schema.org-Microdata
    (`<meta itemprop="startDate" content>` etc.)."""
    base = "https://www.leipziginfo.de"
    listing = fetch.get(base + "/veranstaltungen/", ua=ua)
    if not listing:
        return []
    links = []
    for m in re.findall(r'/veranstaltungen/event/[a-z0-9-]+/\d+/', listing):
        if m not in links:
            links.append(m)
    out = []
    for path in links[:limit]:
        d = fetch.get(base + path, max_age=12 * 3600, ua=ua)
        if not d:
            continue
        name = re.search(r'itemprop="name"[^>]*>(.*?)<', d, re.S)
        sd = re.search(r'itemprop="startDate"[^>]*content="([^"]+)"', d)
        if not (name and sd):
            continue
        ed = re.search(r'itemprop="endDate"[^>]*content="([^"]+)"', d)
        loc = re.search(r'itemprop="location".*?itemprop="name"[^>]*>(.*?)<', d, re.S)

        def iso(v):
            return v if "T" in v else v + "T00:00:00"
        title = html.unescape(re.sub(r"<[^>]+>", "", name.group(1))).strip()
        venue = html.unescape(re.sub(r"<[^>]+>", "", loc.group(1))).strip() if loc else None
        out.append({
            "source_id": source_id, "source_url": base + path,
            "title": title, "summary": None,
            "start_at": iso(sd.group(1)),
            "end_at": iso(ed.group(1)) if ed else None,
            "venue_name": venue, "address": venue, "price": None,
        })
    return out


# ------------------------------------------------------------------- iCal
def extract_ical(text: str, source_id: str) -> list[dict]:
    out = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        def field(name):
            m = re.search(rf"^{name}[^:]*:(.*)$", block, re.M)
            return m.group(1).strip().replace("\\,", ",").replace("\\n", " ") if m else None
        title = field("SUMMARY")
        if not title:
            continue
        out.append({
            "source_id": source_id,
            "source_url": field("URL"),
            "title": title,
            "summary": (field("DESCRIPTION") or "")[:400] or None,
            "start_at": _parse_dt(field("DTSTART")),
            "end_at": _parse_dt(field("DTEND")),
            "venue_name": field("LOCATION"),
            "address": field("LOCATION"),
            "price": None,
        })
    return out


# ------------------------------------------------------------------- RSS/Atom
def extract_rss(text: str, source_id: str) -> list[dict]:
    out = []
    items = re.findall(r"<item>(.*?)</item>", text, re.S | re.I) \
        or re.findall(r"<entry>(.*?)</entry>", text, re.S | re.I)
    for it in items:
        def tag(name):
            m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", it, re.S | re.I)
            if not m:
                return None
            v = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", m.group(1), flags=re.S)
            return html.unescape(re.sub(r"<[^>]+>", "", v)).strip()
        link = tag("link")
        if link is None:
            m = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', it)
            link = m.group(1) if m else None
        title = tag("title")
        if not title:
            continue
        out.append({
            "source_id": source_id,
            "source_url": link,
            "title": title,
            "summary": (tag("description") or tag("summary") or "")[:400] or None,
            "start_at": _parse_dt(tag("pubDate") or tag("published") or tag("updated")),
            "end_at": None,
            "venue_name": None,
            "address": None,
            "price": None,
        })
    return out


# ------------------------------------------------------------------- Datum
def _parse_dt(v) -> str | None:
    """Parst diverse Datumsformate -> ISO-String (oder None)."""
    if not v:
        return None
    s = str(v).strip()
    # iCal-Basisform: 20260706T090000
    m = re.match(r"^(\d{4})(\d{2})(\d{2})T?(\d{2})?(\d{2})?", s)
    if m and len(m.group(1)) == 4 and "-" not in s:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        hh = m.group(4) or "00"
        mm = m.group(5) or "00"
        return f"{y}-{mo}-{d}T{hh}:{mm}:00"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M",
                "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(s[:len(fmt) + 6] if "%z" in fmt or "%Z" in fmt else s[:len(fmt) + 2], fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            continue
    # ISO mit Zeitzonen-Offset
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
