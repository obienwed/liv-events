#!/usr/bin/env python3
"""Scrapes the LIV Las Vegas nightclub AND LIV Beach lineups into
events.json and beach-events.json. Runs daily via GitHub Actions on your Mac.
Edit GENRES / FEATURED below to tune tags.
Tries several ways to read the page (LIV blocks cloud servers):
direct as Chrome, plain direct, then free relay services."""
import json, re, sys, unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, quote
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://www.livnightclub.com/las-vegas/"
EVENTS_URL = URL + "events/"
# venue name on the LIV site -> output file
OUTPUTS = {"liv las vegas": "events.json", "liv beach": "beach-events.json"}
LA = ZoneInfo("America/Los_Angeles")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

def norm(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.lower())

# artist -> (filter group, genre tag). Keys are matched with norm().
GENRES = {
    "metroboomin": ("hiphop", "Hip-hop"), "50cent": ("hiphop", "Hip-hop"),
    "specialguest": ("open", "Open format"),
    "cloonee": ("edm", "Tech house"), "elibrown": ("edm", "Tech house"), "westend": ("edm", "Tech house"),
    "matroda": ("edm", "Bass house"), "gordo": ("edm", "Bass house"), "knock2": ("edm", "Bass house"),
    "linska": ("edm", "House"), "maxstyler": ("edm", "House"), "domdolla": ("edm", "House"),
    "kettama": ("edm", "House"), "nicvans": ("edm", "House"), "joshbaker": ("edm", "House"),
    "discolines": ("edm", "House"), "sidepiece": ("edm", "House"), "dombresky": ("edm", "House"),
    "cassian": ("edm", "Melodic house"), "prospa": ("edm", "House / breaks"),
    "beltran": ("edm", "Techno"), "adriatique": ("edm", "Techno"),
    "laytongiordani": ("edm", "Techno / house"), "dod": ("edm", "Bass / dubstep"),
    "crankdat": ("edm", "Dubstep / bass"), "tiesto": ("edm", "EDM"), "samfeldt": ("edm", "Future house"),
    "devault": ("edm", "House"), "riordan": ("edm", "Tech house"), "bensterling": ("edm", "Tech house"),
    "johnsummit": ("edm", "House"), "davidguetta": ("edm", "EDM"), "kromi": ("edm", "Tech house"),
    "shipwrek": ("edm", "Bass house"), "shamirkelly": ("open", "Open format"), "sommerray": ("open", "Open format"),
}
FEATURED = {"domdolla", "tiesto", "adriatique", "samfeldt", "metroboomin"}

MONTHS = {m: i for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}
CARD = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s*"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s*(\d{1,2})\s*"
    r"(.+?)\s*(LIV Las Vegas|LIV Beach)\s*\|\s*(\d{1,2}):(\d{2})\s*([ap]m)", re.I)

def artist(name):
    return re.sub(r"(?i)^liv beach at night:\s*", "", name)

def classify(name):
    base = norm(artist(name).split(":")[0])
    if "latin" in name.lower() or base.startswith("vive"):
        return "open", "Latin / reggaeton"
    for k, v in GENRES.items():
        if base.startswith(k):
            return v
    return "edm", "Electronic"

def build(cards, today, venue_want):
    """cards: list of (event_id, card_text, href, img_url)"""
    seen, events = set(), []
    for eid, text, href, img in cards:
        found = list(CARD.finditer(text))
        if not found or eid in seen:
            continue
        mon, day, name, venue, hh, mm, ap = found[-1].groups()
        if venue.lower() != venue_want:
            continue
        seen.add(eid)
        d = date(today.year, MONTHS[mon.lower()[:3]], int(day))
        if d < today - timedelta(days=60):          # Jan listed in Oct = next year
            d = date(today.year + 1, d.month, d.day)
        if d < today - timedelta(days=1):
            continue
        h = int(hh) % 12 + (12 if ap.lower() == "pm" else 0)
        name = re.sub(r"\s+[–—-]\s+", ": ", name.strip())
        name = re.sub(r"\s+w\s+", " w/ ", name)
        g, t = classify(name)
        ev = {"d": d.isoformat(), "n": name, "g": g, "t": t,
              "time": f"{h:02d}:{mm}", "url": urljoin(URL, href)}
        if img and not img.startswith("data:"):
            ev["img"] = urljoin(URL, img)
        if norm(artist(name).split(":")[0]) in FEATURED or "new year" in name.lower():
            ev["f"] = 1
        events.append(ev)
    events.sort(key=lambda e: e["d"])
    return events

def cards_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=re.compile(r"/event/EVE-")):
        m = re.search(r"/event/(EVE-[A-Z0-9]+)", a["href"])
        if not m:
            continue
        img_url = ""
        img = a.find("img")
        if img:
            img_url = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
            if not img_url and img.get("srcset"):
                img_url = img["srcset"].split(",")[0].split()[0]
        out.append((m.group(1), a.get_text(" ", strip=True), a["href"], img_url))
    return out

IMG_MD = re.compile(r"!\[[^\[\]]*\]\(\s*([^)\s]+)[^)]*\)")
LINK_MD = re.compile(r"\[([^\[\]]*)\]\(\s*([^)\s]+)[^)]*\)")
BARE_EVENT = re.compile(r"(?<![<\w/])(https?://\S*?/event/EVE-[A-Za-z0-9]+[^\s<>)\]]*)")
EVENT_URL = re.compile(r"<(\S*?/event/(EVE-[A-Za-z0-9]+)[^>]*)>")
IMG_TOKEN = re.compile(r"IMG<([^>]+)>")

def cards_from_text(raw):
    """Works on markdown or plain text from any relay, whatever the layout."""
    t = IMG_MD.sub(lambda m: f" IMG<{m.group(1)}> ", raw)
    for _ in range(5):                                   # unwrap nested [text](url)
        t2 = LINK_MD.sub(lambda m: f" {m.group(1)} <{m.group(2)}> ", t)
        if t2 == t:
            break
        t = t2
    t = BARE_EVENT.sub(lambda m: f"<{m.group(1)}>", t)
    t = re.sub(r"[*_#]", " ", t)
    t = re.sub(r"\s+", " ", t)
    out, prev_end = [], 0
    for m in CARD.finditer(t):
        u = EVENT_URL.search(t, m.end())
        if u and u.start() - m.end() <= 400:
            imgs = IMG_TOKEN.findall(t[prev_end:m.start()])
            out.append((u.group(2).upper(), m.group(0), u.group(1), imgs[-1] if imgs else ""))
        prev_end = m.end()
    return out

def cards_any(body):
    if "<a " in body and "/event/EVE-" in body:
        cards = cards_from_html(body)
        if cards:
            return cards
    return cards_from_text(body)

def fetch(url, chrome=False, headers=None, timeout=60):
    if chrome:
        from curl_cffi import requests as creq
        r = creq.get(url, impersonate="chrome", timeout=timeout)
    else:
        h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
        h.update(headers or {})
        r = requests.get(url, timeout=timeout, headers=h)
    r.raise_for_status()
    return r.text

JINA = {"X-Return-Format": "markdown", "X-No-Cache": "true"}
SOURCES = [
    ("direct (Chrome)",      lambda: fetch(URL, chrome=True)),
    ("direct (plain)",       lambda: fetch(URL)),
    ("relay jina",           lambda: fetch("https://r.jina.ai/" + URL, headers=JINA, timeout=120)),
    ("relay jina (events)",  lambda: fetch("https://r.jina.ai/" + EVENTS_URL, headers=JINA, timeout=120)),
    ("relay jina (browser)", lambda: fetch("https://r.jina.ai/" + URL, headers=dict(JINA, **{"X-Engine": "browser"}), timeout=120)),
    ("relay allorigins",     lambda: fetch("https://api.allorigins.win/raw?url=" + quote(URL, safe=""), timeout=90)),
    ("relay codetabs",       lambda: fetch("https://api.codetabs.com/v1/proxy/?quest=" + URL, timeout=90)),
]

def main():
    today = datetime.now(LA).date()
    for label, fn in SOURCES:
        try:
            body = fn()
            cards = cards_any(body)
            results = {v: build(cards, today, v) for v in OUTPUTS}
            counts = ", ".join(f"{v}: {len(e)}" for v, e in results.items())
            print(f"{label}: got {len(body)} chars -> {counts}")
            if len(results["liv las vegas"]) >= 3:          # proves the page was read correctly
                for v, events in results.items():
                    with open(OUTPUTS[v], "w", encoding="utf-8") as f:
                        json.dump({"source": URL, "venue": v, "events": events}, f, ensure_ascii=False, indent=1)
                    print(f"Wrote {len(events)} events to {OUTPUTS[v]} via {label}.")
                return
            print("   preview:", re.sub(r"\s+", " ", body[:500]))
        except Exception as e:
            print(f"{label} failed: {str(e)[:200]}")
    sys.exit("All methods failed; keeping the old files.")

if __name__ == "__main__":
    main()
