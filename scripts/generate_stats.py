#!/usr/bin/env python3
"""Draw the profile's stat graphics and section headings from the GitHub GraphQL API.

    GITHUB_TOKEN=... GH_LOGIN=happinessisreal python3 scripts/generate_stats.py
    (locally, without GITHUB_TOKEN, it calls `gh api graphql` instead)

Writes stats.svg, streak.svg, langs.svg, year.svg and hd-*.svg in the repo root.
Standard library only, so the scheduled workflow has nothing to install.

Determinism matters (the workflow commits only when a file changes):
  * the window is pinned to whole UTC days, never "the past year from right now";
  * repositories are filtered to PUBLIC, so every token sees the same languages.
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svgkit import esc, prebuilt_face, svg_doc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W = 620
TOKEN = os.environ.get("GITHUB_TOKEN", "")
LOGIN = os.environ.get("GH_LOGIN", "happinessisreal")
FONTS = prebuilt_face(400) + prebuilt_face(600)
HEADINGS = ["about", "projects", "stack", "stats", "about this page"]
# Notebooks count their embedded output images as "code", which swamps real languages.
EXCLUDE_LANGS = {"Jupyter Notebook"}


# ------------------------------------------------------------------ data

def gql(query: str, variables: dict) -> dict:
    if TOKEN:
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-stats"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.load(r)
    else:  # local runs: let the GitHub CLI handle auth
        import subprocess
        args = ["gh", "api", "graphql", "-f", f"query={query}"] + [x for k, v in variables.items() for x in ("-f", f"{k}={v}")]
        out = json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)
    if out.get("errors"):
        raise SystemExit(f"GraphQL error: {out['errors']}")
    return out["data"]["user"]


CALENDAR = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
  contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""

PROFILE = """query($login:String!){user(login:$login){createdAt
  repositories(first:100,privacy:PUBLIC,ownerAffiliations:OWNER,isFork:false){nodes{
    primaryLanguage{name} languages(first:20,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"""


def calendar(start: dt.date, end: dt.date) -> dict[dt.date, int]:
    user = gql(CALENDAR, {"login": LOGIN, "from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"})
    days = {}
    for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
        for d in week["contributionDays"]:
            day = dt.date.fromisoformat(d["date"])
            if start <= day <= end:
                days[day] = d["contributionCount"]
    return days


def streaks(days: dict[dt.date, int], today: dt.date):
    """(current, longest) as (length, first_day, last_day)."""
    longest, run_start, prev = (0, None, None), None, None
    for day in sorted(d for d, n in days.items() if n > 0):
        run_start = day if prev is None or (day - prev).days != 1 else run_start
        length = (day - run_start).days + 1
        if length > longest[0]:
            longest = (length, run_start, day)
        prev = day
    end = today if days.get(today, 0) > 0 else today - dt.timedelta(days=1)
    start = end
    while days.get(start, 0) > 0:
        start -= dt.timedelta(days=1)
    length = (end - start).days
    current = (length, start + dt.timedelta(days=1), end) if length else (0, None, None)
    return current, longest


# ------------------------------------------------------------------ drawing helpers

def fade(body: str, begin: float, dur: float = 0.45) -> str:
    return (f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" '
            f'dur="{dur:.2f}s" fill="freeze"/>{body}</g>')


def text(x, y, s, cls="ink", size=12, weight=400, anchor="start"):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    w = f' font-weight="{weight}"' if weight != 400 else ""
    return f'<text x="{x:g}" y="{y:g}" class="{cls}" font-size="{size}"{w}{a}>{esc(str(s))}</text>'


def fmt_day(d: dt.date) -> str:
    return d.strftime("%b %-d, %Y")


def fmt_range(a, b) -> str:
    if not a:
        return "no active run"
    return fmt_day(a) if a == b else f"{a.strftime('%b %-d')} → {b.strftime('%b %-d, %Y')}"


def write(name: str, height: float, body: str, fonts: str = FONTS):
    (ROOT / name).write_text(svg_doc(W, height, body, fonts), encoding="utf-8")


# ------------------------------------------------------------------ graphics

def draw_stats(year: dict[dt.date, int], start: dt.date):
    total = sum(year.values())
    active = sum(1 for n in year.values() if n)
    best_day, best = max(year.items(), key=lambda kv: (kv[1], kv[0])) if year else (start, 0)
    weeks = defaultdict(int)
    for d, n in year.items():
        weeks[(d - start).days // 7] += n
    series = [weeks[i] for i in range(max(weeks) + 1)] if weeks else [0]
    top, base, peak = 112, 156, max(series) or 1
    xs = [i * W / (len(series) - 1 or 1) for i in range(len(series))]
    ys = [base - (v / peak) * (base - top) for v in series]
    line = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in zip(xs, ys))
    length = sum(math.dist(p, q) for p, q in zip(zip(xs, ys), list(zip(xs, ys))[1:])) + 1
    body = (
        fade(text(0, 54, f"{total:,}", "ink", 52, 600) + text(0, 78, "contributions in the last year", "mut", 12), 0.10)
        + fade(text(W, 30, f"{active}", "ink", 19, 600, "end") + text(W, 47, "active days", "mut", 11, anchor="end"), 0.30)
        + fade(text(W, 72, f"{best}", "ink", 19, 600, "end")
               + text(W, 89, f"best day · {best_day.strftime('%b %-d')}", "mut", 11, anchor="end"), 0.42)
        + f'<line x1="0" y1="{base}" x2="{W}" y2="{base}" class="rule" stroke-width="1"/>'
        + fade(f'<path d="{line}L{W} {base}L0 {base}Z" class="soft"/>', 1.2, 0.6)
        + f'<path d="{line}" class="accs" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" '
          f'stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}">'
          f'<animate attributeName="stroke-dashoffset" from="{length:.0f}" to="0" begin="0.5s" dur="1.3s" fill="freeze"/></path>'
        + fade(f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3.2" class="acc"/>', 1.75, 0.3)
        + text(0, 172, f"weekly · {start.strftime('%b %Y')}", "fnt", 10)
        + text(W, 172, "this week", "fnt", 10, anchor="end")
    )
    write("stats.svg", 178, body)


def draw_streak(current, longest):
    def block(x, label, s, begin):
        n, a, b = s
        return fade(
            text(x, 16, label, "mut", 11)
            + text(x, 58, n, "ink", 38, 600)
            + text(x + len(str(n)) * 38 * 0.6 + 8, 58, "day" if n == 1 else "days", "mut", 14)
            + text(x, 80, fmt_range(a, b), "fnt", 11),
            begin,
        )
    ratio = 0 if not longest[0] else min(current[0] / longest[0], 1)
    bar = (f'<rect x="0" y="96" width="{W}" height="3" rx="1.5" class="trk"/>'
           f'<rect x="0" y="96" width="0" height="3" rx="1.5" class="acc">'
           f'<animate attributeName="width" from="0" to="{W * ratio:.1f}" begin="0.6s" dur="0.9s" fill="freeze"/></rect>')
    body = block(0, "current streak", current, 0.1) + block(330, "longest streak", longest, 0.25) + bar
    write("streak.svg", 104, body)


def draw_langs(repos: list[dict]):
    by_bytes, by_repo = Counter(), Counter()
    for r in repos:
        for e in r["languages"]["edges"]:
            if e["node"]["name"] not in EXCLUDE_LANGS:
                by_bytes[e["node"]["name"]] += e["size"]
        if r["primaryLanguage"] and r["primaryLanguage"]["name"] not in EXCLUDE_LANGS:
            by_repo[r["primaryLanguage"]["name"]] += 1
    total = sum(by_bytes.values()) or 1
    top_bytes = by_bytes.most_common(6)
    top_repo = by_repo.most_common(6)
    rows = max(len(top_bytes), len(top_repo), 1)

    def column(x, title, items, fmt, maxv, begin):
        out = text(x, 14, title, "mut", 11)
        for i, (name, v) in enumerate(items):
            y = 40 + i * 30
            frac = v / maxv if maxv else 0
            out += (text(x, y, name, "ink", 12) + text(x + 290, y, fmt(v), "mut", 12, anchor="end")
                    + f'<rect x="{x}" y="{y + 7}" width="290" height="3" rx="1.5" class="trk"/>'
                    + f'<rect x="{x}" y="{y + 7}" width="0" height="3" rx="1.5" class="acc">'
                      f'<animate attributeName="width" from="0" to="{290 * frac:.1f}" begin="{begin + i * 0.08:.2f}s" dur="0.6s" fill="freeze"/></rect>')
        return fade(out, begin, 0.3)

    body = (column(0, "by bytes", top_bytes, lambda v: f"{v / total * 100:.1f}%", top_bytes[0][1] if top_bytes else 1, 0.1)
            + column(330, "by repo", top_repo, lambda v: f"{v} repo{'s' * (v != 1)}", top_repo[0][1] if top_repo else 1, 0.3))
    write("langs.svg", 30 + rows * 30, body)


def draw_year(year: dict[dt.date, int], start: dt.date, end: dt.date):
    """One character per day, weeks as columns (Sunday at the top), ramp quiet → loud."""
    first_sunday = start - dt.timedelta(days=(start.weekday() + 1) % 7)
    cols = (end - first_sunday).days // 7 + 1
    pitch, size, top = W / cols, 13, 34
    nonzero = sorted(n for n in year.values() if n)
    q = [nonzero[int(len(nonzero) * f)] for f in (0.25, 0.5, 0.75)] if nonzero else [1, 2, 3]

    def char(n):
        if n <= 0:
            return "·"
        return ":" if n <= q[0] else "+" if n <= q[1] else "#" if n <= q[2] else "@"

    quiet, loud = "", ""
    for row in range(7):
        for col in range(cols):
            d = first_sunday + dt.timedelta(days=col * 7 + row)
            if not (start <= d <= end):
                continue
            c = char(year.get(d, 0))
            x, y = col * pitch + pitch / 2, top + row * 15
            t = f'<text x="{x:.1f}" y="{y}" font-size="{size}" text-anchor="middle">{esc(c)}</text>'
            if c == "·":
                quiet += t
            else:
                loud += t
    months = ""
    for col in range(cols):
        d = first_sunday + dt.timedelta(days=col * 7)
        if d.day <= 7 and col > 0 and col * pitch + 3 * 6 <= W:  # skip a label that would be clipped
            months += text(col * pitch, 12, d.strftime("%b").lower(), "fnt", 10)
    sweep = (f'<clipPath id="sw"><rect x="0" y="0" height="140" width="0">'
             f'<animate attributeName="width" from="0" to="{W}" begin="0.2s" dur="1.6s" fill="freeze"/></rect></clipPath>')
    legend = (text(W, 150, "quiet · : + # @ loud", "fnt", 10, anchor="end")
              + text(0, 150, f"{sum(1 for n in year.values() if n)} active days of {len(year)}", "fnt", 10))
    body = months + sweep + f'<g clip-path="url(#sw)"><g class="fnt">{quiet}</g><g class="acc">{loud}</g></g>' + legend
    write("year.svg", 156, body)


def draw_headings():
    for label in HEADINGS:
        width = len(label) * 16 * 0.6
        body = (text(0, 18, label, "ink", 16, 600)
                + f'<line x1="{width + 14:.1f}" y1="12.5" x2="{W}" y2="12.5" class="rule" stroke-width="1"/>')
        write(f"hd-{label.replace(' ', '-')}.svg", 26, body, prebuilt_face(600))


# ------------------------------------------------------------------ main

def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=364)
    year = calendar(start, today)

    profile = gql(PROFILE, {"login": LOGIN})
    created = dt.datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00")).date()
    history = dict(year)
    window_end = start - dt.timedelta(days=1)
    while window_end >= created:  # whole history in one-year windows, for the longest streak
        window_start = max(created, window_end - dt.timedelta(days=364))
        history.update(calendar(window_start, window_end))
        window_end = window_start - dt.timedelta(days=1)

    current, longest = streaks(history, today)
    draw_stats(year, start)
    draw_streak(current, longest)
    draw_langs(profile["repositories"]["nodes"])
    draw_year(year, start, today)
    draw_headings()
    print(f"{LOGIN}: {sum(year.values())} contributions, streak {current[0]} (longest {longest[0]})")


if __name__ == "__main__":
    main()
