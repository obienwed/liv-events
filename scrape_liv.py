#!/usr/bin/env python3
"""Scrapes the LIV Las Vegas nightclub lineup into events.json.
Runs daily via GitHub Actions. Edit GENRES / FEATURED below to tune tags."""
import json, re, sys, unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://www.livnightclub.com/las-vegas/"
VENUE = "liv las vegas"          # nightclub only, skips LIV Beach
OUT = "events.json"
LA = ZoneInfo("America/Los_Angeles")

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
}
FEATURED = {"domdolla", "tiesto", "adriatique", "samfeldt", "metroboomin"}

MONTHS = {m: i for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}
CARD = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s*"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s*(\d{1,2})\s+"
    r"(.+?)\s*(LIV Las Vegas|LIV Beach)\s*\|\s*(\d{1,2}):(\d{2})\s*([ap]m)", re.I)

def classify(name):
    base = norm(name.split(":")[0])
    if "latin" in name.lower() or base.startswith("vive"):
        return "open", "Latin / reggaeton"
    for k, v in GENRES.items():
        if base.startswith(k):
            return v
    return "edm", "Electronic"

def parse(html, today):
    soup = BeautifulSoup(html, "html.parser")
    seen, events = set(), []
    for a in soup.find_all("a", href=re.compile(r"/event/EVE-")):
        m_id = re.search(r"/event/(EVE-[A-Z0-9]+)", a["href"])
        m = CARD.search(a.get_text(" ", strip=True))
        if not m_id or not m or m_id.group(1) in seen:
            continue
        mon, day, name, venue, hh, mm, ap = m.groups()
        if venue.lower() != VENUE:
            continue
        seen.add(m_id.group(1))
        d = date(today.year, MONTHS[mon.lower()[:3]], int(day))
        if d < today - timedelta(days=60):          # Jan listed in Oct = next year
            d = date(today.year + 1, d.month, d.day)
        if d < today - timedelta(days=1):
            continue
        h = int(hh) % 12 + (12 if ap.lower() == "pm" else 0)
        name = re.sub(r"\s+[–—-]\s+", ": ", name.strip())
        name = name.replace(" w ", " w/ ")
        g, t = classify(name)
        ev = {"d": d.isoformat(), "n": name, "g": g, "t": t,
              "time": f"{h:02d}:{mm}", "url": urljoin(URL, a["href"])}
        img = a.find("img")
        if img:
            src = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
            if not src and img.get("srcset"):
                src = img["srcset"].split(",")[0].split()[0]
            if src and not src.startswith("data:"):
                ev["img"] = urljoin(URL, src)
        if norm(name.split(":")[0]) in FEATURED or "new year" in name.lower():
            ev["f"] = 1
        events.append(ev)
    events.sort(key=lambda e: e["d"])
    return events

def main():
    r = requests.get(URL, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"})
    r.raise_for_status()
    events = parse(r.text, datetime.now(LA).date())
    if len(events) < 3:
        sys.exit(f"Only found {len(events)} events; keeping the old events.json.")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": URL, "events": events}, f, ensure_ascii=False, indent=1)
    print(f"Wrote {len(events)} events.")

if __name__ == "__main__":
    main()
