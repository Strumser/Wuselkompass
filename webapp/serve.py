"""Webapp (stdlib http.server): Liste + Karte + Filter, liest data/events.db.

Aufruf:  python3 -m webapp.serve   ->   http://localhost:8000
"""
from __future__ import annotations

import html
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)   # damit 'crawler'/'db' importierbar sind

DB = os.path.join(os.path.dirname(__file__), "..", "data", "events.db")
SOURCES = os.path.join(os.path.dirname(__file__), "..", "sources.json")
STATUS = os.path.join(os.path.dirname(__file__), "..", "data", "status.json")
PORT = 8000


def q(params, key, default=""):
    return params.get(key, [default])[0]


def general_source_ids() -> set:
    """IDs der allgemeinen Aggregatoren (scope=general) – nur in Ansicht 'Alle Events'."""
    try:
        with open(SOURCES, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return set()
    return {s["id"] for s in cfg["sources"] if s.get("scope") == "general"}


def query_events(p) -> list[dict]:
    text = q(p, "q").strip()
    today = datetime.now().strftime("%Y-%m-%d")
    date_sel = q(p, "date", today).strip()
    if date_sel < today:            # keine Vergangenheit anzeigen
        date_sel = today
    ort = q(p, "ort").strip()
    stadtteil = q(p, "stadtteil").strip()
    # Ansicht: 'familie' (Standard, nur kuratierte Quellen) | 'alle' (ungefiltert,
    # inkl. allgemeiner Aggregatoren). Kein Rating/Schlagwortfilter mehr.
    show_all = q(p, "ansicht") == "alle"

    where, args = ["1=1"], []
    if not show_all:
        gen = general_source_ids()
        if gen:
            where.append("source_id NOT IN (%s)" % ",".join("?" * len(gen)))
            args += sorted(gen)
    if ort:
        where.append("ort=?")
        args.append(ort)
    if stadtteil:
        where.append("stadtteil=?")
        args.append(stadtteil)
    if text:
        where.append("(LOWER(title) LIKE ? OR LOWER(summary) LIKE ?)")
        args += [f"%{text.lower()}%", f"%{text.lower()}%"]
    if date_sel:
        # aktiv am gewählten Tag: Start <= Tag <= Ende (Ende = end_at, sonst start_at).
        # Mehrtägige Veranstaltungen erscheinen so an jedem Tag ihres Zeitraums.
        where.append("start_at<>'' AND substr(start_at,1,10) <= ? "
                     "AND substr(COALESCE(NULLIF(end_at,''), start_at),1,10) >= ?")
        args += [date_sel, date_sel]

    sql = (f"SELECT * FROM events WHERE {' AND '.join(where)} "
           f"ORDER BY start_at, family_score DESC LIMIT 1000")
    with sqlite3.connect(DB, timeout=5) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def distinct_orte() -> list[tuple[str, int]]:
    with sqlite3.connect(DB, timeout=5) as c:
        return [(r[0], r[1]) for r in c.execute(
            "SELECT ort, COUNT(*) n FROM events WHERE ort IS NOT NULL "
            "GROUP BY ort ORDER BY n DESC").fetchall()]


def distinct_stadtteile(ort: str) -> list[tuple[str, int]]:
    """Stadtteile — nur sinnvoll für Leipzig."""
    if ort and ort != "Leipzig":
        return []
    with sqlite3.connect(DB, timeout=5) as c:
        return [(r[0], r[1]) for r in c.execute(
            "SELECT stadtteil, COUNT(*) n FROM events "
            "WHERE stadtteil IS NOT NULL GROUP BY stadtteil ORDER BY stadtteil").fetchall()]


def options(items, selected, all_label) -> str:
    out = [f'<option value="" {"selected" if not selected else ""}>{all_label}</option>']
    for name, n in items:
        sel = "selected" if selected == name else ""
        out.append(f'<option value="{html.escape(name)}" {sel}>{html.escape(name)} ({n})</option>')
    return "".join(out)


def query_sources() -> dict:
    """Liest sources.json und ergänzt Live-Zähler aus der DB."""
    with open(SOURCES, encoding="utf-8") as f:
        cfg = json.load(f)
    with sqlite3.connect(DB, timeout=5) as c:
        counts = dict(c.execute("SELECT source_id,COUNT(*) FROM events GROUP BY source_id").fetchall())
    out = []
    for s in cfg["sources"]:
        n = counts.get(s["id"], 0)
        out.append({
            "id": s["id"], "type": s["type"], "active": s.get("active", True),
            "url": s.get("url") or s.get("base", ""),
            "note": s.get("note", ""), "n": n,
            "ansicht": ("Gegenprobe" if s.get("check")
                        else "Alle Events" if s.get("scope") == "general" else "Familie"),
        })
    out.sort(key=lambda r: (-r["n"], r["id"]))
    return {"sources": out, "venues": cfg.get("venues_seed", [])}


def render_sources() -> str:
    data = query_sources()
    live = [s for s in data["sources"] if s["n"] > 0]
    inactive = [s for s in data["sources"] if s["n"] == 0]
    total = sum(s["n"] for s in live)

    def row(s):
        host = s["url"].split("/")[2] if "://" in s["url"] else s["url"]
        return f"""<tr>
          <td><a href="{html.escape(s['url'])}" target="_blank" rel="noopener">{html.escape(s['id'])}</a>
              <div class="host">{html.escape(host)}</div></td>
          <td><code>{html.escape(s['type'])}</code></td>
          <td class="num">{s['n']}</td>
          <td>{html.escape(s['ansicht'])}</td>
          <td class="note">{html.escape(s['note'])}</td>
        </tr>"""

    live_rows = "".join(row(s) for s in live)
    inact_rows = "".join(
        f"<tr class='off'><td><div class='host'>{html.escape(s['id'])}</div></td>"
        f"<td><code>{html.escape(s['type'])}</code></td><td class='num'>–</td>"
        f"<td>{html.escape(s['ansicht'])}</td><td class='note'>{html.escape(s['note'])}</td></tr>"
        for s in inactive)
    venue_items = "".join(
        f"<li><a href='{html.escape(v.get('url',''))}' target='_blank' rel='noopener'>"
        f"{html.escape(v['name'])}</a> <span class='vk'>{html.escape(v.get('kind',''))}"
        f" · {html.escape(v.get('age_hint',''))}</span></li>"
        for v in data["venues"])

    return TEMPLATE_SOURCES.format(
        style=SOURCES_CSS,
        header=header_html("quellen", status_html()),
        total=total, nlive=len(live), nvenue=len(data["venues"]),
        live_rows=live_rows, inact_rows=inact_rows, venue_items=venue_items)


def fmt_date(s):
    if not s:
        return "Termin offen"
    try:
        return datetime.fromisoformat(s).strftime("%a %d.%m.%Y · %H:%M")
    except ValueError:
        return s


MONTHS_DE = ["", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
             "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
WD_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def day_chip(s):
    """(Tag, Monat, Wochentag, Uhrzeit) für den Kalender-Chip."""
    if not s:
        return ("·", "offen", "", "")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return ("·", "", "", "")
    tm = d.strftime("%H:%M")
    return (str(d.day), MONTHS_DE[d.month], WD_DE[d.weekday()],
            "" if tm == "00:00" else tm)


def render(p) -> str:
    evs = query_events(p)
    today = datetime.now().strftime("%Y-%m-%d")
    date_val = q(p, "date", today).strip()
    if date_val < today:
        date_val = today

    # Heute startende Events zuerst, danach schon laufende mehrtägige.
    starts = [e for e in evs if (e.get("start_at") or "")[:10] >= date_val]
    ongoing = [e for e in evs if (e.get("start_at") or "")[:10] < date_val]
    ordered = starts + ongoing

    cards = []
    for e in ordered:
        is_ongoing = (e.get("start_at") or "")[:10] < date_val
        if is_ongoing and e.get("end_at"):
            # „läuft noch bis …": Chip zeigt das ENDE, nicht das alte Startdatum.
            ed = day_chip(e.get("end_at"))
            day, mon, wd, tm = ed[0], ed[1], "bis", ""
        else:
            day, mon, wd, tm = day_chip(e.get("start_at"))
        venue = e.get("venue_name") or e.get("address") or ""
        loc = e.get("stadtteil") or e.get("ort") or ""
        parts = []
        if is_ongoing:
            parts.append("läuft noch")
        elif not tm:
            parts.append("ganztägig")
        if venue:
            parts.append(venue)
        if loc and loc != venue:
            parts.append(loc)
        if e.get("price") and "kostenlos" in (e["price"] or "").lower():
            parts.append("kostenlos")
        meta = " · ".join(html.escape(p) for p in parts)
        link = e.get("source_url") or ""
        host = link.split("/")[2].replace("www.", "") if "://" in link else (e.get("source_id") or "")
        title = html.escape(e.get("title") or "")
        title_html = (f'<a href="{html.escape(link)}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;">{title}</a>'
                      if link else title)
        source_html = (f'Quelle: <a href="{html.escape(link)}" target="_blank" rel="noopener" style="text-decoration:none;font-weight:700;">{html.escape(host)} ↗</a>'
                       if link else f'Quelle: {html.escape(host)}')
        time_html = (f'<div style="font-size:12px;font-weight:700;color:#D9663B;margin-top:2px;">{html.escape(tm)}</div>'
                     if tm else "")
        cards.append(f"""
        <div class="sr-row" style="display:flex;gap:18px;align-items:center;padding:16px;border-radius:14px;">
          <div style="width:58px;text-align:center;flex-shrink:0;">
            <div style="font-size:12px;font-weight:800;color:#B0A398;text-transform:uppercase;">{html.escape(wd)}</div>
            <div style="font-family:'Baloo 2',sans-serif;font-size:24px;font-weight:700;color:#3A2E28;line-height:1.05;">{html.escape(day)}</div>
            <div style="font-size:11px;font-weight:700;color:#B0A398;text-transform:uppercase;">{html.escape(mon)}</div>
            {time_html}
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-family:'Baloo 2',sans-serif;font-weight:600;font-size:19px;color:#2E241D;">{title_html}</div>
            <div style="font-size:13.5px;color:#8A7A6B;margin-top:3px;">{meta}</div>
          </div>
          <div class="sr-source" style="flex-shrink:0;font-size:12.5px;color:#B0A398;">{source_html}</div>
        </div>""")

    cur_ort = q(p, "ort").strip()
    ansicht = "alle" if q(p, "ansicht") == "alle" else "familie"
    ansicht_options = (
        f'<option value="familie"{" selected" if ansicht == "familie" else ""}>Familie</option>'
        f'<option value="alle"{" selected" if ansicht == "alle" else ""}>Alle Events</option>')
    return TEMPLATE.format(
        style=BASE_CSS,
        header=header_html("entdecken", status_html()),
        count=len(evs),
        q=html.escape(q(p, "q")),
        ansicht_options=ansicht_options,
        date=html.escape(date_val),
        today=today,
        ort_options=options(distinct_orte(), cur_ort, "alle Orte"),
        stadtteil_options=options(distinct_stadtteile(cur_ort), q(p, "stadtteil").strip(), "alle Stadtteile"),
        cards="".join(cards) or "<div style='padding:2.5rem 1rem;text-align:center;color:#B0A398;font-size:14px;'>Keine Termine an diesem Tag – wähle ein anderes Datum.</div>",
    )



def status_html() -> str:
    """Kleiner Status-Indikator: Sync läuft … / Aktualisiert: <Zeit>."""
    try:
        with open(STATUS, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return '<span class="sr-status"><span class="dot"></span>noch nicht synchronisiert</span>'
    if st.get("state") == "running":
        return '<span class="sr-status run"><span class="dot"></span>Sync läuft …</span>'
    at = st.get("at", "")
    try:
        when = datetime.fromisoformat(at).strftime("%d.%m. %H:%M")
    except ValueError:
        when = at
    return f'<span class="sr-status"><span class="dot"></span>Aktualisiert: {html.escape(when)} Uhr</span>'


_ILLUS_SVG = """<svg viewBox="0 0 900 260" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
<rect width="900" height="260" fill="#F2A73B"></rect>
<path d="M-10 200 Q100 150 230 185 Q330 210 450 178 Q560 150 680 190 Q790 220 910 178 L910 260 L-10 260 Z" fill="#8FAE8B"></path>
<path d="M-10 200 Q100 150 230 185 Q330 210 450 178 Q560 150 680 190 Q790 220 910 178" fill="none" stroke="#6F9468" stroke-width="2.5" opacity="0.7"></path>
<path d="M-10 232 Q120 205 260 228 Q380 248 500 218 Q620 194 910 224 L910 260 L-10 260 Z" fill="#7A9C75"></path>
<path d="M0 42 Q300 20 450 42 Q650 28 900 42" fill="none" stroke="#FBF3EA" stroke-width="3" stroke-linecap="round"></path>
<circle cx="0" cy="42" r="4" fill="#FBF3EA"></circle>
<circle cx="900" cy="42" r="4" fill="#FBF3EA"></circle>
<g>
<path d="M70 40 L102 38 L83 68 Z" fill="#C2555C"></path>
<path d="M142 39 L174 38 L155 68 Z" fill="#FBF3EA"></path>
<path d="M212 39 L244 39 L225 68 Z" fill="#8FAE8B"></path>
<path d="M282 40 L314 39 L295 68 Z" fill="#C2555C"></path>
<path d="M352 41 L384 39 L365 68 Z" fill="#FBF3EA"></path>
<path d="M422 41 L454 39 L435 68 Z" fill="#8FAE8B"></path>
<path d="M492 40 L524 39 L505 68 Z" fill="#C2555C"></path>
<path d="M562 39 L594 39 L575 68 Z" fill="#FBF3EA"></path>
<path d="M632 39 L664 38 L645 68 Z" fill="#8FAE8B"></path>
<path d="M702 38 L734 38 L715 68 Z" fill="#C2555C"></path>
<path d="M772 39 L804 39 L785 68 Z" fill="#FBF3EA"></path>
</g>
<path d="M700 176 Q686 176 690 162 Q694 148 706 150 Q718 152 716 166 Q714 178 700 176 Z" fill="#3A2E28"></path>
<path d="M688 190 Q690 210 692 216 Q700 220 710 216 Q712 210 712 190 Q700 184 688 190 Z" fill="#C2555C"></path>
<path d="M629 184 Q618 183 622 172 Q626 161 636 163 Q646 165 644 177 Q642 186 629 184 Z" fill="#3A2E28"></path>
<path d="M630 196 Q631 212 633 216 Q640 220 648 216 Q650 212 649 196 Q640 191 630 196 Z" fill="#FCDE9F"></path>
<path d="M770 55 Q762 44 776 40 Q788 36 794 48 Q800 58 788 64 Q774 70 770 55 Z" fill="#FBF3EA" opacity="0.7"></path>
<path d="M800 86 Q794 78 804 76 Q814 74 816 84 Q818 92 808 94 Q798 96 800 86 Z" fill="#FBF3EA" opacity="0.6"></path>
</svg>"""

_LOGO_SVG = """<svg width="54" height="54" viewBox="0 0 76 76" aria-hidden="true">
<path d="M22 46 Q11 28 36 18 Q59 9 68 32 Q76 53 51 64 Q27 76 14 55 Q10 50 22 46 Z" fill="#FCE2A6" stroke="#F2C77A" stroke-width="2" opacity="0.95"></path>
<path d="M40 6 L42 -4 M58 14 L67 6 M70 33 L81 33 M65 54 L73 62 M45 68 L46 78 M22 63 L17 72 M8 44 L-2 46 M14 21 L6 13" stroke="#D9663B" stroke-width="4" stroke-linecap="round"></path>
</svg>"""


def header_html(active: str, status: str = "") -> str:
    ent = "on" if active == "entdecken" else ""
    que = "q on" if active == "quellen" else "q"
    return (
        '<div class="sr-head">' + _ILLUS_SVG +
        '<div class="sr-ov"><div style="display:flex;align-items:center;gap:12px;">'
        + _LOGO_SVG +
        '<span class="sr-brand">Wuselkompass</span></div>'
        '<div class="sr-subtitle">Kinder- und Familienprogramm für Leipzig und Umgebung</div>'
        '</div></div>'
        f'<div class="sr-tabs"><a href="/" class="{ent}">Entdecken</a>'
        f'<a href="/quellen" class="{que}">Quellen</a>{status}</div>'
    )


BASE_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#EFE7DC;color:#3A2E28;font-family:'Nunito',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.sr-wrap{max-width:940px;margin:0 auto;padding:32px 20px 80px}
.sr-card{background:#FFFDFA;border-radius:20px;overflow:hidden;box-shadow:0 20px 50px rgba(60,40,20,.12)}
.sr-head{position:relative;background:#F2A73B;height:260px;overflow:hidden}
.sr-head>svg{position:absolute;inset:0;width:100%;height:100%}
.sr-ov{position:relative;height:260px;display:flex;flex-direction:column;justify-content:center;padding:0 40px}
.sr-brand{font-family:'Baloo 2',sans-serif;font-weight:700;font-size:44px;color:#FFFDFA;line-height:1}
.sr-subtitle{font-weight:700;font-size:16px;color:#FFF6E8;margin-top:6px}
.sr-tabs{display:flex;align-items:center;gap:6px;padding:16px 32px 0}
.sr-tabs a{font-family:'Baloo 2',sans-serif;font-weight:600;font-size:17px;text-decoration:none;color:#B0A398;padding:8px 4px}
.sr-tabs a.on{color:#D9663B;border-bottom:3px solid #D9663B}
.sr-tabs a.q{margin-left:16px}
.sr-status{margin-left:auto;display:flex;align-items:center;gap:7px;font-size:12.5px;font-weight:700;color:#8A7A6B}
.sr-status .dot{width:8px;height:8px;border-radius:50%;background:#2F9E44;flex-shrink:0}
.sr-status.run{color:#B15A34}
.sr-status.run .dot{background:#D9663B;animation:srpulse 1s infinite}
@keyframes srpulse{0%,100%{opacity:1}50%{opacity:.25}}
.sr-filter{display:flex;gap:10px;flex-wrap:wrap;padding:18px 32px 6px}
.sr-input{font-family:'Nunito',sans-serif;font-size:14px;color:#3A2E28;border:1px solid #EADFD0;background:#FBF6EF;border-radius:14px;padding:11px 16px;outline:none}
.sr-input::placeholder{color:#A99C8E}
.sr-count{padding:10px 32px 0;font-size:12.5px;font-weight:700;color:#B0A398}
.sr-list{padding:8px 16px 24px}
.sr-row:hover{background:#FBF6EF}
.sr-source a{color:#B15A34}
.sr-source a:hover{color:#8F4526}
@media(max-width:560px){.sr-brand{font-size:32px}.sr-head,.sr-ov{height:210px}.sr-tabs,.sr-filter,.sr-count{padding-left:18px;padding-right:18px}.sr-list{padding:8px 10px 24px}.sr-status{display:none}}
"""

SOURCES_CSS = BASE_CSS + """
.sr-body{padding:8px 32px 32px}
.sr-lead{color:#8A7A6B;font-size:13px;margin:10px 0 4px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(60,40,20,.06);margin:.5rem 0 1.4rem}
th,td{text-align:left;padding:.55rem .7rem;border-bottom:1px solid #F0E9DF;font-size:.86rem;vertical-align:top}
th{background:#FBF6EF;color:#8A7A6B;font-size:.72rem;text-transform:uppercase;letter-spacing:.03em;font-weight:800}
td a{color:#B15A34;text-decoration:none;font-weight:700}
.host{color:#B0A398;font-size:.72rem}
.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
.note{color:#6B5F54;font-size:.8rem}
code{background:#F0E9DF;padding:.05rem .35rem;border-radius:5px;font-size:.78rem}
tr.off{opacity:.55}
h2{font-family:'Baloo 2',sans-serif;font-weight:600;font-size:18px;margin:1.4rem 0 .3rem;color:#3A2E28}
ul.venues{columns:2;gap:1.4rem;list-style:none;padding:0}
ul.venues li{margin:.2rem 0;font-size:.86rem;break-inside:avoid}
ul.venues a{color:#B15A34;text-decoration:none;font-weight:700}
.vk{color:#B0A398;font-size:.74rem}
@media(max-width:640px){ul.venues{columns:1}}
"""

_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
          '<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">')

TEMPLATE = """<!doctype html><html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wuselkompass · Familienveranstaltungen Leipzig</title>
""" + _FONTS + """
<style>{style}</style></head><body>
<div class="sr-wrap"><div class="sr-card">
{header}
<form method="get" class="sr-filter">
  <input class="sr-input" name="q" value="{q}" placeholder="Suche nach Veranstaltung…" style="flex:2;min-width:180px">
  <select class="sr-input" name="ansicht" onchange="this.form.submit()" title="Ansicht wählen">{ansicht_options}</select>
  <input class="sr-input" type="date" name="date" value="{date}" min="{today}" onchange="this.form.submit()" title="Datum wählen">
  <select class="sr-input" name="ort" onchange="this.form.stadtteil.value='';this.form.submit()">{ort_options}</select>
  <select class="sr-input" name="stadtteil" onchange="this.form.submit()">{stadtteil_options}</select>
</form>
<div class="sr-count">{count} Veranstaltungen an diesem Tag</div>
<div class="sr-list">
{cards}
</div>
</div></div>
</body></html>"""

TEMPLATE_SOURCES = """<!doctype html><html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quellen · Wuselkompass</title>
""" + _FONTS + """
<style>{style}</style></head><body>
<div class="sr-wrap"><div class="sr-card">
{header}
<div class="sr-body">
  <p class="sr-lead">{nlive} liefernde Quellen · aktuell {total} Events · {nvenue} Dauer-Locations. Spalte Ansicht = in welcher Ansicht die Quelle erscheint (Familie = kuratiert, Alle Events = ungefiltert).</p>
  <h2>Aktive Event-Quellen</h2>
  <table><tr><th>Quelle</th><th>Extraktor</th><th>Events</th><th>Ansicht</th><th>Notiz</th></tr>{live_rows}</table>
  <h2>Vorgemerkt / in Arbeit</h2>
  <table><tr><th>Quelle</th><th>Extraktor</th><th>Events</th><th>Ansicht</th><th>Status</th></tr>{inact_rows}</table>
  <h2>Dauer-Locations</h2>
  <ul class="venues">{venue_items}</ul>
</div>
</div></div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/events.json":
            body = json.dumps(query_events(parse_qs(u.query)), ensure_ascii=False).encode()
            ctype = "application/json; charset=utf-8"
        elif u.path == "/quellen":
            body = render_sources().encode()
            ctype = "text/html; charset=utf-8"
        elif u.path in ("/", "/index.html"):
            body = render(parse_qs(u.query)).encode()
            ctype = "text/html; charset=utf-8"
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


MAX_AGE_H = 6   # ab dieser Sync-Alterung wird beim Start neu gecrawlt


def _last_sync():
    """Zeitpunkt des letzten abgeschlossenen Crawls (aus status.json)."""
    try:
        with open(STATUS, encoding="utf-8") as f:
            return datetime.fromisoformat(json.load(f).get("at", ""))
    except (OSError, ValueError):
        return None


def refresh_on_start():
    """Crawlt beim App-Start nur, wenn der letzte Sync älter als MAX_AGE_H ist.

    Fehlt die DB, wird einmalig blockierend gecrawlt (damit sofort Daten da sind).
    Ist der letzte Sync jünger als 6 h, passiert nichts – die App startet sofort
    und zeigt den vorhandenen Stand (der Zeitstempel bleibt korrekt stehen).
    Sonst läuft der Crawl im Hintergrund (eigener Prozess = saubere DB-Isolierung).
    """
    cmd = [sys.executable, "-m", "crawler.run"]
    if not os.path.exists(DB):
        print("Keine Daten vorhanden – initialer Crawl (einmalig, kann 1–2 Min dauern) …")
        subprocess.run(cmd, cwd=ROOT)
        return
    last = _last_sync()
    if last and (datetime.now() - last).total_seconds() < MAX_AGE_H * 3600:
        mins = int((datetime.now() - last).total_seconds() // 60)
        print(f"Letzter Sync vor {mins} min (<{MAX_AGE_H} h) – kein neuer Crawl beim Start.")
        return
    print(f"Letzter Sync älter als {MAX_AGE_H} h – Aktualisierung im Hintergrund …")
    subprocess.Popen(cmd, cwd=ROOT)


if __name__ == "__main__":
    refresh_on_start()
    print(f"Webapp läuft auf http://localhost:{PORT}  (Strg+C zum Beenden)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
