"""Webapp (stdlib http.server): Entdecken (Termine + Wochenraster), Orte, Quellen (Gesundheit).

Liest data/events.db. Aufruf:  python3 -m webapp.serve   ->   http://localhost:8000
Die Seite ist nur lokal erreichbar (127.0.0.1).
"""
from __future__ import annotations

import html
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)   # damit 'crawler'/'db' importierbar sind

from crawler import health          # noqa: E402
from db import store                # noqa: E402

DB = os.path.join(os.path.dirname(__file__), "..", "data", "events.db")
SOURCES = os.path.join(os.path.dirname(__file__), "..", "sources.json")
STATUS = os.path.join(os.path.dirname(__file__), "..", "data", "status.json")
PORT = 8000

REGION_LABEL = {"leipzig": "Leipzig", "halle": "Halle (Saale)", "chemnitz": "Chemnitz"}
KIND_LABEL = {"spielcafe": "Spielcafé / Eltern-Kind-Café", "indoor": "Indoor-Spielplatz",
              "familienzentrum": "Familienzentrum / offener Treff", "bibliothek": "Bibliothek",
              "museum": "Museum / Schloss", "bad": "Bad", "tiere": "Tierpark / Streichelzoo",
              "freizeit": "Freizeit / Erlebnis"}
BELEG = {"ok": ("✓ belegt", "ok"), "mid": ("~ Portal", "mid"), "low": ("? unbestätigt", "low")}
AMPEL = {"rot": "Rot", "gelb": "Gelb", "gruen": "Grün", "grau": "Aus", "offen": "Offen"}
AMPEL_ORDER = {"rot": 0, "gelb": 1, "offen": 2, "gruen": 3, "grau": 4}
LOCAL_HOSTS = ("localhost", "127.0.0.1")


def q(params, key, default=""):
    return params.get(key, [default])[0]


def connect():
    c = sqlite3.connect(DB, timeout=5)
    c.row_factory = sqlite3.Row
    return c


def read_cfg() -> dict:
    with open(SOURCES, encoding="utf-8") as f:
        return json.load(f)


def general_source_ids() -> set:
    """IDs der allgemeinen Aggregatoren (scope=general) – nur in Ansicht 'Alle Events'."""
    try:
        return {s["id"] for s in read_cfg()["sources"] if s.get("scope") == "general"}
    except (OSError, ValueError):
        return set()


# ------------------------------------------------------------------ Alter / Region
def parse_age(p):
    a = q(p, "alter")
    return int(a) if a in ("2", "3", "4") else None


def _num(x) -> str:
    x = float(x)
    return str(int(x)) if x == int(x) else str(x).replace(".", ",")


def age_text(mn, mx) -> str:
    if mn is None and mx is None:
        return "Alter offen"
    if mn is not None and mx is not None:
        return f"{_num(mn)}–{_num(mx)} Jahre"
    return f"ab {_num(mn)} Jahren" if mn is not None else f"bis {_num(mx)} Jahre"


def age_ok(mn, mx, age, only) -> bool:
    if only and mn is None and mx is None:
        return False
    if age is None:
        return True
    return (mn is None or mn <= age) and (mx is None or mx >= age)


def age_sql(cmin, cmax, age, only):
    parts, args = [], []
    if age is not None:
        parts += [f"({cmin} IS NULL OR {cmin} <= ?)", f"({cmax} IS NULL OR {cmax} >= ?)"]
        args += [age, age]
    if only:
        parts.append(f"({cmin} IS NOT NULL OR {cmax} IS NOT NULL)")
    return parts, args


def region_of_params(p) -> str:
    r = q(p, "region")
    return r if r in REGION_LABEL else ""


# ------------------------------------------------------------------ Termine
# Alter für Filter: Angabe aus dem Termin, sonst die geschätzte aus der Bewertung
_NO_AGE = "(age_min IS NULL AND age_max IS NULL)"
_AGE_MIN = f"(CASE WHEN {_NO_AGE} THEN est_min ELSE age_min END)"
_AGE_MAX = f"(CASE WHEN {_NO_AGE} THEN est_max ELSE age_max END)"


def query_events(p) -> list[dict]:
    text = q(p, "q").strip()
    today = datetime.now().strftime("%Y-%m-%d")
    date_sel = q(p, "date", today).strip()
    if date_sel < today:            # keine Vergangenheit anzeigen
        date_sel = today
    ort, stadtteil = q(p, "ort").strip(), q(p, "stadtteil").strip()
    region = region_of_params(p)
    age, only = parse_age(p), q(p, "nur_alter") == "1"
    show_all = q(p, "ansicht") == "alle"

    where, args = ["archived_at IS NULL", "dup_of IS NULL"], []
    if not show_all:
        # Familie = Bewertung „passt"/„vielleicht" (aus jeder Quelle) + noch unbewertete
        # Termine der Familienquellen. „nein" erscheint nur unter „Alle Events".
        gen = sorted(general_source_ids()) or [""]
        where.append("((source_id NOT IN (%s) AND verdict IS NULL) OR verdict IN ('passt','vielleicht'))"
                     % ",".join("?" * len(gen)))
        args += gen
    if region:
        where.append("region=?")
        args.append(region)
    if ort:
        where.append("ort=?")
        args.append(ort)
    if stadtteil:
        where.append("stadtteil=?")
        args.append(stadtteil)
    if text:
        where.append("(LOWER(title) LIKE ? OR LOWER(summary) LIKE ?)")
        args += [f"%{text.lower()}%", f"%{text.lower()}%"]
    a_parts, a_args = age_sql(_AGE_MIN, _AGE_MAX, age, only)
    where += a_parts
    args += a_args
    # aktiv am gewählten Tag: Start <= Tag <= Ende (Ende = end_at, sonst start_at).
    where.append("start_at<>'' AND substr(start_at,1,10) <= ? "
                 "AND substr(COALESCE(NULLIF(end_at,''), start_at),1,10) >= ?")
    args += [date_sel, date_sel]
    sql = (f"SELECT events.*, verdict, reason, est_min, est_max FROM events "
           f"LEFT JOIN ratings USING (rkey) WHERE {' AND '.join(where)} "
           f"ORDER BY start_at, family_score DESC LIMIT 1000")
    with connect() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def rating_note() -> str:
    """Vermerk: Die Ansicht „Familie" beruht auf einer KI-Bewertung (Claude), die in einer
    Claude-Sitzung angestoßen werden muss. Zeigt, wie viele Titel der nächsten 14 Tage noch offen sind."""
    until = (date.today() + timedelta(days=14)).isoformat()
    with connect() as c:
        n = c.execute(
            "SELECT COUNT(DISTINCT events.rkey) FROM events LEFT JOIN ratings USING (rkey) "
            "WHERE archived_at IS NULL AND dup_of IS NULL AND start_at<>'' "
            "AND substr(start_at,1,10) <= ? AND verdict IS NULL", (until,)).fetchone()[0]
        last = c.execute("SELECT MAX(rated_at) FROM ratings").fetchone()[0]
    stand = f" Letzte Bewertung: {datetime.fromisoformat(last).strftime('%d.%m.%Y')}." if last else ""
    if not n:
        return (f'<div class="ai-note">Die Auswahl „Familie" beruht auf einer Bewertung durch KI (Claude).{stand}</div>')
    return (f'<div class="ai-note ai-open"><b>KI-Bewertung nötig:</b> {n} Termine der nächsten 14 Tage sind noch nicht '
            f'bewertet, die Ansicht „Familie" ist deshalb unvollständig.{stand} Bewertung in einer Claude-Sitzung '
            f'anstoßen: „Bewerte die neuen Termine".</div>')


def recurring_on(day: date, region: str, age, only) -> list[dict]:
    """Wiederkehrende Angebote, die an diesem Tag stattfinden (Regel je Eintrag)."""
    with connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM recurring WHERE weekday=? ORDER BY COALESCE(von,'99:99'), place_name",
            (day.weekday(),)).fetchall()]
    merged: dict = {}
    for r in rows:
        if region and r["region"] != region:
            continue
        rule, note = r["rule"], None
        if rule == "biweekly":
            if r["anchor"]:
                a = date.fromisoformat(r["anchor"])
                if day < a or (day - a).days % 14:
                    continue
            else:
                note = "14-tägig"
        elif rule == "1st3rd":
            if ((day.day - 1) // 7) + 1 not in (1, 3):
                continue
        elif rule == "last":
            if (day + timedelta(days=7)).month == day.month:
                continue
        elif rule == "monthly":
            note = "monatlich, Termin erfragen"
        key = (r["offer_id"], r["von"], r["bis"])
        if key in merged:                 # gleiche Zeit, andere Altersstufe -> Altersbereich vereinigen
            m = merged[key]
            m["age_min"] = None if m["age_min"] is None or r["age_min"] is None else min(m["age_min"], r["age_min"])
            m["age_max"] = None if m["age_max"] is None or r["age_max"] is None else max(m["age_max"], r["age_max"])
        else:
            r["_note"] = note
            merged[key] = r
    return [r for r in merged.values() if age_ok(r["age_min"], r["age_max"], age, only)]


def distinct_orte(region: str = "") -> list[tuple[str, int]]:
    sql = "SELECT ort, COUNT(*) n FROM events WHERE ort IS NOT NULL AND archived_at IS NULL AND dup_of IS NULL"
    args = []
    if region:
        sql += " AND region=?"
        args.append(region)
    with connect() as c:
        return [(r[0], r[1]) for r in c.execute(sql + " GROUP BY ort ORDER BY n DESC", args).fetchall()]


def distinct_stadtteile(ort: str) -> list[tuple[str, int]]:
    """Stadtteile — nur sinnvoll für Leipzig."""
    if ort and ort != "Leipzig":
        return []
    with connect() as c:
        return [(r[0], r[1]) for r in c.execute(
            "SELECT stadtteil, COUNT(*) n FROM events WHERE stadtteil IS NOT NULL AND archived_at IS NULL AND dup_of IS NULL "
            "GROUP BY stadtteil ORDER BY stadtteil").fetchall()]


def options(items, selected, all_label) -> str:
    out = [f'<option value="" {"selected" if not selected else ""}>{all_label}</option>']
    for name, n in items:
        sel = "selected" if selected == name else ""
        out.append(f'<option value="{html.escape(name)}" {sel}>{html.escape(name)} ({n})</option>')
    return "".join(out)


def simple_options(pairs, selected) -> str:
    return "".join(f'<option value="{html.escape(v)}"{" selected" if selected == v else ""}>{html.escape(l)}</option>'
                   for v, l in pairs)


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



def keep_params(p, keys=("region", "alter")) -> str:
    """Region und Alter wandern beim Wechsel zwischen den Reitern mit."""
    d = {k: q(p, k) for k in keys if q(p, k)}
    return ("?" + urlencode(d)) if d else ""


def common_filters(p) -> str:
    """Region- und Alters-Auswahl (gemeinsam für Entdecken und Orte)."""
    region, age = region_of_params(p), q(p, "alter")
    reg = simple_options([("", "alle Regionen")] + list(REGION_LABEL.items()), region)
    alt = simple_options([("", "Alter: alle"), ("2", "Mein Kind: 2 Jahre"), ("3", "Mein Kind: 3 Jahre"),
                          ("4", "Mein Kind: 4 Jahre")], age)
    nur = f'<label class="sr-chk"><input type="checkbox" name="nur_alter" value="1" {"checked" if q(p, "nur_alter") == "1" else ""} onchange="this.form.submit()"> nur mit Altersangabe</label>'
    return (f'<select class="sr-input" name="region" onchange="this.form.submit()" title="Region">{reg}</select>'
            f'<select class="sr-input" name="alter" onchange="this.form.submit()" title="Alter des Kindes">{alt}</select>{nur}')


# ------------------------------------------------------------------ Seite: Entdecken
def render(p) -> str:
    evs = query_events(p)
    today = datetime.now().strftime("%Y-%m-%d")
    date_val = q(p, "date", today).strip()
    if date_val < today:
        date_val = today
    day = date.fromisoformat(date_val)
    age, only, region = parse_age(p), q(p, "nur_alter") == "1", region_of_params(p)
    text = q(p, "q").strip()

    # Heute startende Events zuerst, danach schon laufende mehrtägige.
    starts = [e for e in evs if (e.get("start_at") or "")[:10] >= date_val]
    ongoing = [e for e in evs if (e.get("start_at") or "")[:10] < date_val]

    # Bewertung „passt" zuerst, dann vielleicht/unbewertet, „nein" zuletzt (innerhalb stabil nach Zeit)
    rank = {"passt": 0, "vielleicht": 1, None: 1, "nein": 2}
    ordered = sorted(starts + ongoing, key=lambda e: rank.get(e.get("verdict"), 1))

    cards = []
    for e in ordered:
        is_ongoing = (e.get("start_at") or "")[:10] < date_val
        if is_ongoing and e.get("end_at"):
            ed = day_chip(e.get("end_at"))       # „läuft noch bis …": Chip zeigt das ENDE
            dnum, mon, wd, tm = ed[0], ed[1], "bis", ""
        else:
            dnum, mon, wd, tm = day_chip(e.get("start_at"))
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
        meta = " · ".join(html.escape(x) for x in parts)
        known = e.get("age_min") is not None or e.get("age_max") is not None
        est = not known and (e.get("est_min") is not None or e.get("est_max") is not None)
        if est:
            pill = f'<span class="pill pill-est" title="von Claude geschätzt">≈ {html.escape(age_text(e["est_min"], e["est_max"]))}</span>'
        else:
            pill = (f'<span class="pill {"" if known else "pill-off"}">{html.escape(age_text(e.get("age_min"), e.get("age_max")))}</span>')
        if e.get("verdict"):
            vlabel = {"passt": "passt für 2–4", "vielleicht": "vielleicht", "nein": "eher nicht"}[e["verdict"]]
            pill += (f' <span class="pill v-{e["verdict"]}" title="{html.escape(e.get("reason") or "")}">'
                     f'{vlabel}</span>')
            if e.get("reason"):
                pill += f'<div class="v-reason">{html.escape(e["reason"])}</div>' 
        link = e.get("source_url") or ""
        host = link.split("/")[2].replace("www.", "") if "://" in link else (e.get("source_id") or "")
        title = html.escape(e.get("title") or "")
        title_html = (f'<a href="{html.escape(link)}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;">{title}</a>'
                      if link else title)
        source_html = (f'Quelle: <a href="{html.escape(link)}" target="_blank" rel="noopener" style="text-decoration:none;font-weight:700;">{html.escape(host)} ↗</a>'
                       if link else f'Quelle: {html.escape(host)}')
        if e.get("also_in"):
            source_html += f'<div style="font-size:11.5px;margin-top:2px;">auch bei: {html.escape(e["also_in"])}</div>'
        time_html = (f'<div style="font-size:12px;font-weight:700;color:#D9663B;margin-top:2px;">{html.escape(tm)}</div>'
                     if tm else "")
        cards.append(f"""
        <div class="sr-row" style="display:flex;gap:18px;align-items:center;padding:16px;border-radius:14px;">
          <div style="width:58px;text-align:center;flex-shrink:0;">
            <div style="font-size:12px;font-weight:800;color:#B0A398;text-transform:uppercase;">{html.escape(wd)}</div>
            <div style="font-family:'Baloo 2',sans-serif;font-size:24px;font-weight:700;color:#3A2E28;line-height:1.05;">{html.escape(dnum)}</div>
            <div style="font-size:11px;font-weight:700;color:#B0A398;text-transform:uppercase;">{html.escape(mon)}</div>
            {time_html}
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-family:'Baloo 2',sans-serif;font-weight:600;font-size:19px;color:#2E241D;">{title_html}</div>
            <div style="font-size:13.5px;color:#8A7A6B;margin-top:3px;">{meta} {pill}</div>
          </div>
          <div class="sr-source" style="flex-shrink:0;font-size:12.5px;color:#B0A398;">{source_html}</div>
        </div>""")

    # Wochenraster: nur ohne Textsuche (Suche meint Termine)
    rec = recurring_on(day, region, age, only) if not text else []
    rec_html = ""
    if rec:
        rows = []
        for r in rec:
            zeit = (f"{r['von']}–{r['bis']}" if r["von"] and r["bis"] else r["von"] or "Zeit offen")
            bits = [age_text(r["age_min"], r["age_max"])]
            if r["_note"]:
                bits.append(r["_note"])
            if r["hinweis"]:
                bits.append(r["hinweis"])
            lvl = BELEG.get(r["beleg"] or "low", BELEG["low"])
            rows.append(
                f'<div class="rec-row"><div class="rec-t">{html.escape(zeit)}</div>'
                f'<div class="rec-m"><div class="rec-title">{html.escape(r["title"])}'
                f' <span class="tag tag-{lvl[1]}">{lvl[0]}</span></div>'
                f'<div class="rec-sub">{html.escape(r["place_name"] or "")} · {html.escape(REGION_LABEL.get(r["region"], ""))}'
                f' · {html.escape(" · ".join(bits))}</div></div></div>')
        rec_html = (f'<div class="rec"><div class="rec-h">Jede Woche an diesem Tag '
                    f'<span class="rec-n">{len(rec)} Angebote</span></div>{"".join(rows)}'
                    f'<div class="rec-f">Zeiten laut Quellen, bitte vorher prüfen (zuletzt geprüft Okt. 2026).</div></div>')

    cur_ort = q(p, "ort").strip()
    ansicht = "alle" if q(p, "ansicht") == "alle" else "familie"
    ansicht_options = simple_options([("familie", "Familie"), ("alle", "Alle Events")], ansicht)
    body = f"""
<form method="get" class="sr-filter">
  <input class="sr-input" name="q" value="{html.escape(q(p, "q"))}" placeholder="Suche nach Veranstaltung…" style="flex:2;min-width:180px">
  <select class="sr-input" name="ansicht" onchange="this.form.submit()" title="Ansicht wählen">{ansicht_options}</select>
  <input class="sr-input" type="date" name="date" value="{html.escape(date_val)}" min="{today}" onchange="this.form.submit()" title="Datum wählen">
  {common_filters(p)}
  <select class="sr-input" name="ort" onchange="this.form.stadtteil.value='';this.form.submit()">{options(distinct_orte(region), cur_ort, "alle Orte")}</select>
  <select class="sr-input" name="stadtteil" onchange="this.form.submit()">{options(distinct_stadtteile(cur_ort), q(p, "stadtteil").strip(), "alle Stadtteile")}</select>
</form>
{rec_html}
{rating_note()}
<div class="sr-count">{len(evs)} Veranstaltungen an diesem Tag</div>
<div class="sr-list">
{"".join(cards) or "<div style='padding:2.5rem 1rem;text-align:center;color:#B0A398;font-size:14px;'>Keine Termine an diesem Tag – wähle ein anderes Datum.</div>"}
</div>"""
    return page_html("Wuselkompass · Familienveranstaltungen", "entdecken", body, BASE_CSS + EXTRA_CSS, p)


# ------------------------------------------------------------------ Seite: Orte
def query_places(p) -> list[dict]:
    where, args = ["status='aktiv'"], []
    region, kind, drin = region_of_params(p), q(p, "art"), q(p, "drinnen")
    age, only, text = parse_age(p), q(p, "nur_alter") == "1", q(p, "q").strip().lower()
    if region:
        where.append("region=?")
        args.append(region)
    if kind in KIND_LABEL:
        where.append("kind=?")
        args.append(kind)
    if drin == "ja":
        where.append("indoor IN ('ja','teils')")
    elif drin == "nein":
        where.append("indoor IN ('nein','teils')")
    if text:
        where.append("(LOWER(name) LIKE ? OR LOWER(COALESCE(note,'')) LIKE ? OR LOWER(COALESCE(ort,'')) LIKE ?)")
        args += [f"%{text}%"] * 3
    a_parts, a_args = age_sql("age_min", "age_max", age, only)
    where += a_parts
    args += a_args
    with connect() as c:
        return [dict(r) for r in c.execute(
            f"SELECT * FROM places WHERE {' AND '.join(where)} "
            "ORDER BY CASE kind WHEN 'spielcafe' THEN 0 WHEN 'indoor' THEN 1 WHEN 'familienzentrum' THEN 2 ELSE 3 END, "
            "region, name", args).fetchall()]


def _note_without_addr(o: dict) -> str:
    """Die Notiz beginnt oft mit der Adresse (steht schon in der Kopfzeile) – nicht doppelt zeigen."""
    note, addr = (o.get("note") or ""), (o.get("address") or "")
    if addr and note.startswith(addr):
        note = note[len(addr):].lstrip(" ·–-")
    return note[:230]


def render_places(p) -> str:
    places = query_places(p)
    region, kind, drin = region_of_params(p), q(p, "art"), q(p, "drinnen")
    with connect() as c:
        kinds = dict(c.execute("SELECT kind, COUNT(*) FROM places WHERE status='aktiv' GROUP BY kind").fetchall())
        total = c.execute("SELECT COUNT(*) FROM places WHERE status='aktiv'").fetchone()[0]
    art_opts = simple_options([("", f"alle Arten ({total})")] + [(k, f"{l} ({kinds.get(k, 0)})") for k, l in KIND_LABEL.items() if kinds.get(k)], kind)
    drin_opts = simple_options([("", "drinnen & draußen"), ("ja", "Indoor (drinnen)"), ("nein", "draußen")], drin)
    chips = "".join(
        f'<a class="chip{" chip-on" if kind == k else ""}" href="/orte?{urlencode({**{a: q(p, a) for a in ("region", "alter", "nur_alter", "drinnen") if q(p, a)}, "art": k})}">{html.escape(l)}</a>'
        for k, l in (("spielcafe", "Kindercafé"), ("indoor", "Indoor-Spielplätze"), ("familienzentrum", "Familienzentren"), ("bad", "Bäder"), ("museum", "Museen")))
    indoor_chip = (f'<a class="chip{" chip-on" if drin == "ja" else ""}" href="/orte?{urlencode({**{a: q(p, a) for a in ("region", "alter", "nur_alter", "art") if q(p, a)}, "drinnen": "ja"})}">Alles drinnen</a>')
    cards = []
    for o in places:
        lvl = BELEG.get(o["beleg"] or "low", BELEG["low"])
        name = html.escape(o["name"])
        name_html = f'<a href="{html.escape(o["url"])}" target="_blank" rel="noopener">{name} ↗</a>' if o.get("url") else name
        known = o["age_min"] is not None or o["age_max"] is not None
        loc = ", ".join(x for x in (o.get("address"), o.get("ort")) if x)
        if o.get("address") and o.get("ort") and o["ort"] in o["address"]:
            loc = o["address"]
        cards.append(
            f'<div class="place"><div class="place-h"><div class="place-name">{name_html}</div>'
            f'<span class="tag tag-{lvl[1]}">{lvl[0]}</span></div>'
            f'<div class="place-meta"><span class="kind">{html.escape(KIND_LABEL.get(o["kind"], ""))}</span>'
            f'<span class="pill {"" if known else "pill-off"}">{html.escape(age_text(o["age_min"], o["age_max"]))}</span>'
            f'<span class="where">{html.escape(REGION_LABEL.get(o["region"], ""))} · {html.escape(loc)}</span></div>'
            f'<div class="place-note">{html.escape(_note_without_addr(o))}</div>'
            f'<div class="place-f">{html.escape(o.get("id") or "")} · zuletzt geprüft {html.escape(o.get("checked_at") or "–")}</div></div>')
    body = f"""
<form method="get" action="/orte" class="sr-filter">
  <input class="sr-input" name="q" value="{html.escape(q(p, "q"))}" placeholder="Ort suchen…" style="flex:2;min-width:160px">
  {common_filters(p)}
  <select class="sr-input" name="art" onchange="this.form.submit()">{art_opts}</select>
  <select class="sr-input" name="drinnen" onchange="this.form.submit()">{drin_opts}</select>
</form>
<div class="chips">{indoor_chip}{chips}<a class="chip" href="/orte{keep_params(p)}">Zurücksetzen</a></div>
<div class="sr-count">{len(places)} Orte</div>
<div class="places">{"".join(cards) or "<div style='padding:2rem;text-align:center;color:#B0A398'>Keine Orte für diese Auswahl.</div>"}</div>"""
    return page_html("Orte · Wuselkompass", "orte", body, BASE_CSS + EXTRA_CSS, p)


# ------------------------------------------------------------------ Seite: Quellen (Gesundheit)
def _spark(values: list[int]) -> str:
    if not values:
        return '<span class="host">–</span>'
    mx = max(values) or 1
    bars = "".join(f'<rect x="{i * 7}" y="{18 - round(16 * v / mx)}" width="5" height="{max(round(16 * v / mx), 1)}" rx="1"></rect>'
                   for i, v in enumerate(values[-10:]))
    return f'<svg class="spark" width="{min(len(values), 10) * 7}" height="18" aria-label="Verlauf der letzten Läufe">{bars}</svg>'


def render_sources(p) -> str:
    cfg = read_cfg()
    with connect() as c:
        counts = dict(c.execute("SELECT source_id, COUNT(*) FROM events WHERE archived_at IS NULL GROUP BY source_id").fetchall())
        res = health.evaluate(c, cfg)
        n_places = c.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    res.sort(key=lambda r: (AMPEL_ORDER[r["status"]], -counts.get(r["id"], 0), r["id"]))
    tally = {k: sum(1 for r in res if r["status"] == k) for k in AMPEL}

    def row(r):
        last, chk = r["last"], r["check_row"]
        host = r["url"].split("/")[2] if "://" in r["url"] else r["url"]
        ans = "Gegenprobe" if r["check"] else "Alle Events" if r["scope"] == "general" else "Familie"
        n = counts.get(r["id"], 0)
        only = last["unique_n"] if last and last.get("unique_n") is not None else None
        letzter = (last["run_at"][5:10].replace("-", ".") + "." + f" · {last['seconds']:.0f} s" if last and last.get("seconds") is not None else "–") if last else "–"
        erreich = ("–" if not chk else (f"{chk['http']}" if chk["http"] else "keine Antwort") + f" · {chk['checked_at'][5:16].replace('T', ' ')}")
        why = html.escape("; ".join(r["reasons"]))
        if r["active"]:
            btn = f'<button class="mini" name="to" value="aus" onclick="return confirm(\'{html.escape(r["id"])} abschalten?\')">abschalten</button>'
        else:
            btn = '<button class="mini" name="to" value="an">einschalten</button>'
        return (f'<tr class="{"off" if not r["active"] else ""}"><td><span class="amp amp-{r["status"]}" title="{why}"></span> {AMPEL[r["status"]]}</td>'
                f'<td><a href="{html.escape(r["url"])}" target="_blank" rel="noopener">{html.escape(r["id"])}</a><div class="host">{html.escape(host)}</div></td>'
                f'<td>{ans}<div class="host">{html.escape(REGION_LABEL.get(r["region"], ""))}</div></td>'
                f'<td class="num">{n}</td><td class="num">{only if only is not None else "–"}</td>'
                f'<td>{_spark(r["history"])}</td><td class="note">{why}</td>'
                f'<td class="host">{letzter}</td><td class="host">{erreich}</td>'
                f'<td><form method="post" action="/api/source-toggle"><input type="hidden" name="id" value="{html.escape(r["id"])}">{btn}</form></td></tr>')

    act = [r for r in res if r["active"]]
    inact = [r for r in res if not r["active"]]
    thead = ("<tr><th>Status</th><th>Quelle</th><th>Ansicht · Region</th><th>Events</th><th>nur hier</th>"
             "<th>Verlauf</th><th>Befund</th><th>Letzter Lauf</th><th>Erreichbar?</th><th></th></tr>")
    msg = q(p, "msg")
    banner = f'<div class="banner">{html.escape(msg)}</div>' if msg else ""
    body = f"""
<div class="sr-body">
{banner}
<p class="sr-lead"><span class="amp amp-rot"></span> {tally['rot']} rot &nbsp; <span class="amp amp-gelb"></span> {tally['gelb']} gelb &nbsp;
<span class="amp amp-offen"></span> {tally['offen']} noch ungemessen &nbsp; <span class="amp amp-gruen"></span> {tally['gruen']} grün &nbsp;
<span class="amp amp-grau"></span> {tally['grau']} abgeschaltet · {n_places} Orte · <a class="chip" href="/orte">zu den Orten</a></p>
<form method="post" action="/api/check" class="checkform"><button class="p-btn">Erreichbarkeit jetzt prüfen</button>
<span class="host"> ruft von jeder aktiven Quelle einmal die Startseite ab, dauert etwa eine halbe Minute</span></form>
<h2>Aktive Quellen</h2>
<table>{thead}{"".join(row(r) for r in act)}</table>
<h2>Abgeschaltet</h2>
<details><summary class="host">{len(inact)} Quellen anzeigen</summary>
<table>{thead}{"".join(row(r) for r in inact)}</table></details>
<p class="sr-lead">Ampel: <b>rot</b> = liefert nichts, Seite nicht erreichbar oder Termine stark eingebrochen (unter 40 % des üblichen);
<b>gelb</b> = auffällig (Rückgang unter 70 %, viele Einträge ohne Datum, viele Abruffehler); <b>grün</b> = unauffällig.
„nur hier" = Termine, die keine andere Quelle kennt. Die Messung füllt sich mit jedem Aktualisieren.</p>
</div>"""
    return page_html("Quellen · Wuselkompass", "quellen", body, BASE_CSS + EXTRA_CSS, p)


def toggle_source(sid: str, to: str) -> str:
    """Schaltet eine Quelle in sources.json an/aus (Formatierung der Datei bleibt erhalten)."""
    cfg = read_cfg()
    for s in cfg["sources"]:
        if s["id"] == sid:
            s["active"] = (to == "an")
            with open(SOURCES, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
                f.write("\n")
            return f"{sid} ist jetzt {'eingeschaltet' if to == 'an' else 'abgeschaltet'} (wirkt ab dem nächsten Aktualisieren)."
    return f"Quelle {sid} nicht gefunden."


def run_checks() -> str:
    cfg = read_cfg()
    rows = health.check_all(cfg)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with store.connect() as conn:
        store.record_checks(conn, now, rows)
    bad = [r for r in rows if r["http"] is None or r["http"] >= 400]
    names = ", ".join(f"{r['source_id']} ({r['http'] or 'keine Antwort'})" for r in bad[:8])
    return f"Prüfung fertig: {len(rows)} Quellen abgerufen, {len(bad)} mit Fehler" + (f": {names}" if bad else ".")


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



def header_html(active: str, status: str = "", p=None) -> str:
    kp = keep_params(p or {})
    def tab(href, label, key, cls=""):
        return f'<a href="{href}{kp if href != "/quellen" else ""}" class="{"on" if active == key else ""} {cls}">{label}</a>'
    return (
        '<div class="sr-head">' + _ILLUS_SVG +
        '<div class="sr-ov"><div style="display:flex;align-items:center;gap:12px;">'
        + _LOGO_SVG +
        '<span class="sr-brand">Wuselkompass</span></div>'
        '<div class="sr-subtitle">Kinder- und Familienprogramm für Leipzig, Halle und Chemnitz</div>'
        '</div></div>'
        f'<div class="sr-tabs">{tab("/", "Entdecken", "entdecken")}{tab("/orte", "Orte", "orte", "q")}'
        f'{tab("/quellen", "Quellen", "quellen", "q")}{status}</div>'
    )


def page_html(title: str, active: str, body: str, css: str, p=None) -> str:
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'{_FONTS}<style>{css}</style></head><body><div class="sr-wrap"><div class="sr-card">'
            f'{header_html(active, status_html(), p)}{body}</div></div></body></html>')


BASE_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#EFE7DC;color:#3A2E28;font-family:'Nunito',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.sr-wrap{max-width:1080px;margin:0 auto;padding:32px 20px 80px}
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
.sr-filter{display:flex;gap:10px;flex-wrap:wrap;padding:18px 32px 6px;align-items:center}
.sr-input{font-family:'Nunito',sans-serif;font-size:14px;color:#3A2E28;border:1px solid #EADFD0;background:#FBF6EF;border-radius:14px;padding:11px 16px;outline:none}
.sr-input::placeholder{color:#A99C8E}
.sr-count{padding:10px 32px 0;font-size:12.5px;font-weight:700;color:#B0A398}
.sr-list{padding:8px 16px 24px}
.sr-row:hover{background:#FBF6EF}
.sr-source a{color:#B15A34}
.sr-source a:hover{color:#8F4526}
@media(max-width:560px){.sr-brand{font-size:32px}.sr-head,.sr-ov{height:210px}.sr-tabs,.sr-filter,.sr-count{padding-left:18px;padding-right:18px}.sr-list{padding:8px 10px 24px}.sr-status{display:none}}
"""

EXTRA_CSS = """
.sr-chk{font-size:13px;color:#6B5F54;display:flex;align-items:center;gap:6px;white-space:nowrap}
.pill{display:inline-block;font-size:11.5px;font-weight:800;padding:1px 8px;border-radius:999px;background:#E9F3E6;color:#2F7D3A;margin-left:6px;vertical-align:1px}
.pill-off{background:#F0E9DF;color:#A99C8E}
.pill-est{background:#FFF4D6;color:#9A7417}
.v-passt{background:#2F7D3A;color:#fff}.v-vielleicht{background:#F3D9A4;color:#7A5410}.v-nein{background:#EADAD4;color:#8E5A4A}
.ai-note{font-size:12.5px;color:#9A8B7D;margin:.6rem 0 .2rem}
.ai-open{background:#FFF4D6;color:#7A5410;border:1px solid #F0DCA6;border-radius:10px;padding:8px 12px}
.v-reason{font-size:12.5px;color:#9A8B7D;margin-top:3px;font-style:italic}
.tag{display:inline-block;font-size:11.5px;font-weight:800;padding:1px 8px;border-radius:999px;border:1px solid;margin-left:4px;vertical-align:1px}
.tag-ok{color:#2F7D3A;border-color:#2F9E44}.tag-mid{color:#9A6B12;border-color:#D9A441}.tag-low{color:#B0413F;border-color:#C2555C}
.rec{margin:14px 32px 4px;border:1px solid #F0DFC8;background:#FFF8EC;border-radius:16px;padding:12px 16px}
.rec-h{font-family:'Baloo 2',sans-serif;font-weight:600;font-size:17px;color:#B15A34}.rec-n{font-family:'Nunito',sans-serif;font-size:12.5px;color:#B0A398;font-weight:700;margin-left:6px}
.rec-row{display:flex;gap:14px;padding:8px 0;border-top:1px dashed #F0DFC8}.rec-row:first-of-type{border-top:0}
.rec-t{width:92px;flex:none;font-weight:800;color:#D9663B;font-size:13.5px}
.rec-title{font-weight:700;color:#2E241D}.rec-sub{font-size:13px;color:#8A7A6B}
.rec-f{font-size:12px;color:#B0A398;margin-top:6px}
.chips{display:flex;gap:8px;flex-wrap:wrap;padding:6px 32px 0}
.chip{display:inline-block;font-size:13px;font-weight:700;text-decoration:none;color:#8A7A6B;border:1px solid #EADFD0;background:#FBF6EF;border-radius:999px;padding:5px 12px}
.chip:hover,.chip-on{color:#fff;background:#D9663B;border-color:#D9663B}
.places{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;padding:12px 32px 28px}
.place{border:1px solid #EADFD0;background:#FFFDFA;border-radius:16px;padding:14px 16px}
.place-h{display:flex;gap:8px;align-items:flex-start;justify-content:space-between}
.place-name{font-family:'Baloo 2',sans-serif;font-weight:600;font-size:18px;color:#2E241D}.place-name a{color:inherit;text-decoration:none}.place-name a:hover{color:#D9663B}
.place-meta{display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center;margin-top:4px;font-size:13px;color:#8A7A6B}
.kind{background:#FCE9D8;color:#B15A34;font-weight:800;font-size:11.5px;padding:1px 8px;border-radius:999px}
.place-note{font-size:13px;color:#6B5F54;margin-top:8px}.place-f{font-size:11.5px;color:#B0A398;margin-top:8px}
.sr-body{padding:8px 32px 32px}
.sr-lead{color:#8A7A6B;font-size:13px;margin:10px 0 4px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(60,40,20,.06);margin:.5rem 0 1.4rem}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid #F0E9DF;font-size:.82rem;vertical-align:top}
th{background:#FBF6EF;color:#8A7A6B;font-size:.7rem;text-transform:uppercase;letter-spacing:.03em;font-weight:800}
td a{color:#B15A34;text-decoration:none;font-weight:700}
.host{color:#B0A398;font-size:.72rem}.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
.note{color:#6B5F54;font-size:.78rem;max-width:230px}
tr.off{opacity:.55}
h2{font-family:'Baloo 2',sans-serif;font-weight:600;font-size:18px;margin:1.4rem 0 .3rem;color:#3A2E28}
.amp{display:inline-block;width:11px;height:11px;border-radius:50%;vertical-align:-1px}
.amp-gruen{background:#2F9E44}.amp-gelb{background:#E0A400}.amp-rot{background:#C2433C}.amp-grau{background:#B0A398}.amp-offen{background:#7A9CC6}
.spark rect{fill:#D9A441}
.mini{font:inherit;font-size:.75rem;border:1px solid #EADFD0;background:#FBF6EF;color:#6B5F54;border-radius:10px;padding:3px 9px;cursor:pointer}.mini:hover{border-color:#D9663B;color:#D9663B}
.p-btn{font:inherit;font-weight:800;border:0;background:#D9663B;color:#fff;border-radius:12px;padding:9px 16px;cursor:pointer}.p-btn:hover{background:#B15A34}
.checkform{margin:10px 0 0}.banner{background:#E9F3E6;border:1px solid #B9D8B2;color:#2F6B38;border-radius:12px;padding:10px 14px;margin:10px 0;font-size:13.5px}
details summary{cursor:pointer;margin:.4rem 0}
@media(max-width:640px){.places{padding:12px 16px}.chips{padding:6px 18px 0}.rec{margin:12px 16px 4px}.sr-body{padding:8px 14px 24px}table{display:block;overflow-x:auto}}
"""

_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
          '<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">')


class Handler(BaseHTTPRequestHandler):
    def _local_only(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        origin = self.headers.get("Origin")
        return host in LOCAL_HOSTS and (not origin or urlparse(origin).hostname in LOCAL_HOSTS)

    def _send(self, body: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, to: str):
        self.send_response(303)
        self.send_header("Location", to)
        self.end_headers()

    def do_GET(self):
        if not self._local_only():
            self.send_error(403); return
        u = urlparse(self.path)
        p = parse_qs(u.query)
        if u.path == "/api/events.json":
            self._send(json.dumps(query_events(p), ensure_ascii=False).encode(), "application/json; charset=utf-8")
        elif u.path == "/orte":
            self._send(render_places(p).encode(), "text/html; charset=utf-8")
        elif u.path == "/quellen":
            self._send(render_sources(p).encode(), "text/html; charset=utf-8")
        elif u.path in ("/", "/index.html"):
            self._send(render(p).encode(), "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def do_POST(self):
        if not self._local_only():
            self.send_error(403); return
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode("utf-8")) if n else {}
        if u.path == "/api/source-toggle":
            msg = toggle_source(q(form, "id"), q(form, "to"))
        elif u.path == "/api/check":
            msg = run_checks()
        else:
            self.send_error(404); return
        self._redirect("/quellen?" + urlencode({"msg": msg}))

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


def prepare_db():
    """Schema/Migration und Orte/Wochenangebote aus data/*.json in die DB spiegeln."""
    store.init_db()
    with store.connect() as conn:
        orte, rec = store.load_curated(ROOT)
        if orte or rec:
            store.sync_places(conn, orte, rec)
        store.sync_ratings(conn, store.load_ratings(ROOT))


if __name__ == "__main__":
    refresh_on_start()
    prepare_db()
    print(f"Webapp läuft auf http://localhost:{PORT}  (nur lokal erreichbar, Strg+C zum Beenden)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
