#!/usr/bin/env python3
"""Download the latest Envibus timetables and write data/timetable.json.

Sources
- Regular lines (line 11): Envibus GTFS file, published as open data on
  transport.data.gouv.fr / data.gouv.fr (stable "latest" link below).
- School lines 26S and 27S: the PDF timetable linked from each line's page
  on envibus.fr (they are not in the open data file).

Run locally with files already downloaded:
  python3 scripts/update_timetable.py --gtfs gtfs.zip --pdf26 26S.pdf --pdf27 27S.pdf

Exits with an error (and leaves the old data untouched) if anything looks
wrong, so a failed GitHub Actions run emails the repository owner.
"""
import argparse, csv, datetime as dt, io, json, re, subprocess, sys, tempfile, urllib.request, zipfile
from pathlib import Path

GTFS_URL = "https://www.data.gouv.fr/api/1/datasets/r/344e5a88-e993-4952-a8bf-503048020116"
GTFS_FALLBACK = "https://open-share.agglo-casa.fr/s/34FS2SWg36NEZk4/download"
# transport.data.gouv.fr keeps a copy of every version; its resource page links the latest one.
GTFS_HISTORY_PAGE = "https://transport.data.gouv.fr/resources/79342"
LINE_PAGES = {"26S": "https://www.envibus.fr/le-reseau/ligne/ligne-26s",
              "27S": "https://www.envibus.fr/le-reseau/ligne/ligne-27s"}
OUT = Path(__file__).resolve().parent.parent / "data" / "timetable.json"
UA = {"User-Agent": "home-from-civ timetable updater (github.com/atxcristilica/home-from-civ)"}

GR_NAME = "G.R. VALBONNE SOPHIA-ANTIPOLIS"
CR_NAME = "Opio San Peyre (College du Rouret)"
TRUCS_NAME = "LES TRUCS"

def fetch(url, timeout=60):
    req = urllib.request.Request(url.replace(" ", "%20"), headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def latest_history_zip():
    html = fetch(GTFS_HISTORY_PAGE).decode("utf-8", "replace")
    zips = sorted(set(re.findall(r'https://[\w.-]+/79342/79342\.[\d.]+\.zip', html)))
    if not zips:
        raise SystemExit("No GTFS copy found on transport.data.gouv.fr")
    return zips[-1]

def download_gtfs(sources):
    errors = []
    for get in (lambda: GTFS_URL, lambda: GTFS_FALLBACK, latest_history_zip):
        try:
            url = get()
            raw = fetch(url, timeout=45)
            zipfile.ZipFile(io.BytesIO(raw))  # check it is a real zip
            sources["gtfs"] = url
            return raw
        except Exception as e:
            errors.append(f"{e.__class__.__name__}: {e}")
    raise SystemExit("Could not download the Envibus GTFS file: " + " | ".join(errors))

def hm(t):  # "18:15:00" -> "18:15"
    h, m = t.split(":")[:2]
    return f"{int(h):02d}:{m}"

# ---------- line 11 from GTFS ----------
def read_csv(z, name):
    with z.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))

def line11_from_gtfs(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    routes = {r["route_id"]: r["route_short_name"].strip() for r in read_csv(z, "routes.txt")}
    stops = {s["stop_id"]: s["stop_name"].strip() for s in read_csv(z, "stops.txt")}
    trips = {t["trip_id"]: t for t in read_csv(z, "trips.txt") if routes.get(t["route_id"]) == "11"}
    cal = read_csv(z, "calendar.txt")
    try:
        caldates = read_csv(z, "calendar_dates.txt")
    except KeyError:
        caldates = []
    # Pick the next 7 days that are inside the file's validity, Monday..Friday.
    today = dt.date.today()
    end = max(c["end_date"] for c in cal)
    days = {}
    d = today
    while len(days) < 5 and d.strftime("%Y%m%d") <= end:
        if d.weekday() < 5 and d.weekday() not in days:
            days[d.weekday()] = d
        d += dt.timedelta(days=1)
    if len(days) < 5:
        raise SystemExit(f"GTFS file only runs until {end}: it looks out of date.")
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    def active(date):
        ds = date.strftime("%Y%m%d")
        s = {c["service_id"] for c in cal if c[wd[date.weekday()]] == "1" and c["start_date"] <= ds <= c["end_date"]}
        for x in caldates:
            if x["date"] == ds:
                (s.add if x["exception_type"] == "1" else s.discard)(x["service_id"])
        return s
    times = {}
    with z.open("stop_times.txt") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
            if r["trip_id"] in trips:
                times.setdefault(r["trip_id"], []).append((int(r["stop_sequence"]), stops.get(r["stop_id"], ""), r["departure_time"], r["arrival_time"]))
    result, morning = {}, {}
    for i, date in sorted(days.items()):
        svc = active(date)
        rows, am = set(), set()
        for tid, st in times.items():
            if trips[tid]["service_id"] not in svc:
                continue
            st.sort()
            gr = [x for x in st if x[1] == GR_NAME]
            cr = [x for x in st if x[1] == CR_NAME]
            tr = [x for x in st if x[1] == TRUCS_NAME]
            if gr and cr and gr[0][0] < cr[0][0]:
                rows.add((hm(gr[0][2]), hm(cr[0][3]), hm(tr[0][3]) if tr else hm(cr[0][3])))
            if gr and cr and cr[0][0] < gr[-1][0]:
                am.add((hm(cr[0][2]), hm(gr[-1][3])))
        result[str(i)] = [list(x) for x in sorted(rows)]
        morning[str(i)] = [list(x) for x in sorted(am)]
    return result, morning, end

# ---------- school lines from the PDFs ----------
def pdf_link(line):
    html = fetch(LINE_PAGES[line]).decode("utf-8", "replace")
    links = re.findall(r'href="([^"]+\.pdf)"', html, flags=re.I)
    links = [l for l in links if re.search(r"fiche", l, re.I) and line.lower() in l.lower().replace(" ", "")]
    if not links:
        raise SystemExit(f"No timetable PDF link found for {line} on {LINE_PAGES[line]}")
    url = links[0]
    if url.startswith("/"):
        url = "https://www.envibus.fr" + url
    return url

def pdf_text(raw):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(raw); f.flush()
        return subprocess.run(["pdftotext", "-raw", f.name, "-"], capture_output=True, text=True, check=True).stdout

def rows_after(lines, start):
    rows = []
    for l in lines[start + 1:]:
        m = re.match(r"^(.*?)\s+((?:\d{2}:\d{2}\s*)+)$", l.strip())
        if not m:
            if rows:
                break
            continue
        rows.append((m.group(1).strip(), re.findall(r"\d{2}:\d{2}", m.group(2))))
    return rows

def school_morning(line, text):
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if "Aller" in l)
    except StopIteration:
        raise SystemExit(f"{line}: no 'Aller' section in the PDF")
    rows = rows_after(lines, start)
    if len(rows) < 3:
        raise SystemExit(f"{line}: could not read the morning timetable")
    n = len(rows[0][1])
    find = lambda name: next((t for s_, t in rows if name.lower() in s_.lower() and len(t) == n), None)
    moulins, rouret = find("Moulins"), find("Place du Rouret")
    civ, gr = find("Bermond"), find("Gare Routi")
    out = []
    for k in range(n):
        if moulins:
            dep = moulins[k]
        elif rouret:
            h, mm = map(int, rouret[k].split(":")); t = h * 60 + mm - 5
            dep = f"≈{t // 60:02d}:{t % 60:02d}"
        else:
            raise SystemExit(f"{line}: no Moulins or Place du Rouret morning times")
        if civ:
            out.append({"line": line, "from": "Moulins", "dep": dep, "to": "Place Bermond (CIV)", "arr": civ[k], "walk": 0, "days": [0, 1, 2, 3, 4]})
        elif gr:
            out.append({"line": line, "from": "Moulins", "dep": dep, "to": "Gare routière", "arr": gr[k], "walk": 5, "days": [0, 1, 2, 3, 4]})
        else:
            raise SystemExit(f"{line}: no CIV or gare routière morning times")
    return out

def school_from_pdf(line, text):
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if "Retour" in l)
    except StopIteration:
        raise SystemExit(f"{line}: no 'Retour' section in the PDF")
    rows = []
    for l in lines[start + 1:]:
        m = re.match(r"^(.*?)\s+((?:\d{2}:\d{2}\s*)+)$", l.strip())
        if not m:
            if rows:
                break
            continue
        rows.append((m.group(1).strip(), re.findall(r"\d{2}:\d{2}", m.group(2))))
    if len(rows) < 3:
        raise SystemExit(f"{line}: could not read the return timetable")
    first, deps = rows[0]
    n = len(deps)
    def find(name):
        for s, t in rows:
            if name.lower() in s.lower() and len(t) == n:
                return t
        return None
    from_name = "Place Bermond (CIV)" if "bermond" in first.lower() else "Gare routière"
    board = 5 if "bermond" in first.lower() else 10
    gr = find("Gare Routi")
    cistes = find("Cistes")
    rouret = find("Place du Rouret")
    out = []
    for k in range(n):
        if cistes:
            arr = cistes[k]
        elif rouret:
            h, mm = map(int, rouret[k].split(":")); t = h * 60 + mm + 4
            arr = f"≈{t // 60:02d}:{t % 60:02d}"
        else:
            raise SystemExit(f"{line}: no Cistes or Place du Rouret times")
        dep = deps[k]
        # Midday runs only on Wednesdays; there is no service on Wednesday afternoons.
        days = [2] if dep < "14:00" else [0, 1, 3, 4]
        out.append({"line": line, "from": from_name, "dep": dep, "to": "Cistes", "arr": arr, "days": days, "board": board})
        # 26S also stops at the gare routière a few minutes later: offer it too.
        if from_name.startswith("Place") and gr:
            pass
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gtfs"); ap.add_argument("--pdf26"); ap.add_argument("--pdf27")
    a = ap.parse_args()
    sources = {}
    raw = Path(a.gtfs).read_bytes() if a.gtfs else None
    if raw is None:
        raw = download_gtfs(sources)
    line11, line11_am, gtfs_end = line11_from_gtfs(raw)
    school, school_am = [], []
    for line, local in (("26S", a.pdf26), ("27S", a.pdf27)):
        if local:
            pdf = Path(local).read_bytes(); sources[line] = local
        else:
            url = pdf_link(line); pdf = fetch(url); sources[line] = url
        txt = pdf_text(pdf)
        school += school_from_pdf(line, txt)
        school_am += school_morning(line, txt)
    school.sort(key=lambda s: (s["dep"], s["line"]))

    # Sanity checks: refuse to publish data that would break the plan.
    for d, rows in line11.items():
        if len(rows) < 8:
            raise SystemExit(f"Line 11: only {len(rows)} trips on weekday {d}; the file may be wrong.")
    if not any("18:00" <= r[0] <= "18:30" for r in line11["1"]):
        print("WARNING: no line 11 departure between 18:00 and 18:30 on Tuesdays.", file=sys.stderr)
    if not any(s["days"] == [2] for s in school) or not any(s["days"] != [2] for s in school):
        raise SystemExit("School lines: expected both Wednesday-midday and afternoon runs.")

    for d, rows in line11_am.items():
        if len(rows) < 8:
            raise SystemExit(f"Line 11 (morning direction): only {len(rows)} trips on weekday {d}.")
    if not school_am:
        raise SystemExit("School lines: no morning runs found.")
    school_am.sort(key=lambda s: (s["dep"].lstrip("≈"), s["line"]))
    data = {"sources": sources, "gtfsValidUntil": gtfs_end, "line11": line11, "line11Morning": line11_am,
            "school": school, "schoolMorning": school_am}
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    comparable = lambda x: {k: v for k, v in x.items() if k not in ("updated",)}
    if comparable(old) == comparable(data):
        print("No change.")
        return
    data["updated"] = dt.date.today().isoformat()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print("Timetable updated.")

if __name__ == "__main__":
    main()
