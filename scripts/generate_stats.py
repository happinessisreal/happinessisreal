#!/usr/bin/env python3
"""Draw the profile's terminal windows from the GitHub GraphQL API.

    GITHUB_TOKEN=... GH_LOGIN=happinessisreal python3 scripts/generate_stats.py
    (locally, without GITHUB_TOKEN, it calls `gh api graphql` instead)

Writes terminal.svg (neofetch), card-*.svg (one per project), activity.svg (git log),
stats.svg, langs.svg and year.svg in the repo root. Standard library only, so the
scheduled workflow has nothing to install.

Determinism matters (the workflow commits only when a file changes):
  * the window is pinned to whole UTC days, never "the past year from right now";
  * repositories are filtered to PUBLIC, so every token sees the same languages;
  * dates are absolute (2026-10-04), never relative ("3 days ago").
"""
import datetime as dt
import json
import math
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svgkit import FAMILY, esc, prebuilt_face  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "data"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
LOGIN = os.environ.get("GH_LOGIN", "happinessisreal")
W = 820          # every window shares GitHub's README column width, so edges line up
CARD_W = 404     # two cards per row
BAR = 32         # title bar height
CW = 13 * 0.6    # JetBrains Mono advance at 13px
# Notebooks count their embedded output images as "code", which swamps real languages.
EXCLUDE_LANGS = {"Jupyter Notebook"}

# Terminals are dark in both themes (like the portrait's panel), so one fixed palette.
CSS = (".bg{fill:#0d1117}.bar{fill:#161b22}.edge{stroke:#30363d}.ink{fill:#e6edf3}.mut{fill:#8b949e}"
       ".fnt{fill:#6e7681}.grn{fill:#3fb950}.amb{fill:#e3b341}.blu{fill:#79c0ff}.trk{fill:#21262d}"
       ".accs{stroke:#e3b341}.soft{fill:#e3b341;opacity:.16}")
FONTS = prebuilt_face(400) + prebuilt_face(600)


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
  repositories(first:100,privacy:PUBLIC,ownerAffiliations:OWNER,isFork:false,orderBy:{field:PUSHED_AT,direction:DESC}){
    totalCount nodes{name pushedAt primaryLanguage{name}
      languages(first:20,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}
      defaultBranchRef{target{... on Commit{history(first:6){nodes{
        oid messageHeadline committedDate author{user{login}}}}}}}}}}}"""


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


def languages(repos) -> Counter:
    by_bytes = Counter()
    for r in repos:
        for e in r["languages"]["edges"]:
            if e["node"]["name"] not in EXCLUDE_LANGS:
                by_bytes[e["node"]["name"]] += e["size"]
    return by_bytes


def recent_commits(repos, limit=6):
    commits = []
    for r in repos:
        if r["name"] == LOGIN:  # the profile repo itself isn't project work
            continue
        target = (r.get("defaultBranchRef") or {}).get("target") or {}
        for c in (target.get("history") or {}).get("nodes", []):
            user = (c.get("author") or {}).get("user") or {}
            if user.get("login") == LOGIN:  # only your own commits (skips the bot's refreshes)
                commits.append((c["committedDate"], r["name"], c["oid"][:7], c["messageHeadline"]))
    return sorted(commits, reverse=True)[:limit]


# ------------------------------------------------------------------ drawing helpers

def text(x, y, s, cls="ink", size=13, weight=400, anchor="start"):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    w = f' font-weight="{weight}"' if weight != 400 else ""
    return f'<text x="{x:g}" y="{y:g}" class="{cls}" font-size="{size}"{w}{a} xml:space="preserve">{esc(str(s))}</text>'


def fade(body: str, begin: float, dur: float = 0.4) -> str:
    return (f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" '
            f'dur="{dur:.2f}s" fill="freeze"/>{body}</g>')


def typed(x, y, cmd, begin, uid, size=13):
    """A prompt line that types itself, with a cursor riding the edge. Returns (svg, end_time)."""
    full = (len(cmd) + 2) * size * 0.6
    start_w = 2 * size * 0.6
    dur = max(0.25, 0.035 * len(cmd))
    svg = (f'<clipPath id="{uid}"><rect x="{x}" y="{y - size}" height="{size + 6}" width="{start_w:.1f}">'
           f'<animate attributeName="width" from="{start_w:.1f}" to="{full:.1f}" begin="{begin:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>'
           f'<g clip-path="url(#{uid})">{text(x, y, "❯", "grn", size, 600)}{text(x + start_w, y, cmd, "ink", size)}</g>'
           f'<rect y="{y - size + 2}" width="{size * 0.6:.1f}" height="{size + 1}" class="ink" opacity="0">'
           f'<animate attributeName="x" from="{x + start_w:.1f}" to="{x + full:.1f}" begin="{begin:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
           f'<set attributeName="opacity" to="0.7" begin="{begin:.2f}s"/><set attributeName="opacity" to="0" begin="{begin + dur + 0.15:.2f}s"/></rect>')
    return svg, begin + dur + 0.15


def window(width, height, title, body):
    dots = "".join(f'<circle cx="{18 + i * 18}" cy="16" r="5.5" fill="{c}"/>'
                   for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]))
    return (f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="12" class="bg edge" stroke-width="1"/>'
            f'<path d="M.5 12.5A12 12 0 0 1 12.5 .5H{width - 12.5}A12 12 0 0 1 {width - .5} 12.5V{BAR}H.5Z" class="bar"/>'
            f'<line x1=".5" y1="{BAR}" x2="{width - .5}" y2="{BAR}" class="edge" stroke-width="1"/>{dots}'
            + text(width / 2, 20.5, title, "mut", 12, anchor="middle")
            + f'<g transform="translate(0 {BAR})">{body}</g>')


def ascii_art(x, y, art, size, begin, step, prefix):
    """Coloured ASCII block (lines + per-cell colour index + palette), fading in row by row."""
    lh = size * 1.12
    css = "".join(f".{prefix}{i}{{fill:{h}}}" for i, h in enumerate(art["palette"]))
    out = f"<style>{css}</style>"
    for r, (line, crow) in enumerate(zip(art["lines"], art["colors"])):
        if not line.strip():
            continue
        layers = ""
        for c in sorted(set(crow)):
            layer = "".join(ch if crow[j] == c else " " for j, ch in enumerate(line)).rstrip()
            if layer.strip():
                layers += (f'<text x="{x:g}" y="{y + r * lh + size:.1f}" class="{prefix}{c}" font-size="{size:.2f}" '
                           f'xml:space="preserve">{esc(layer)}</text>')
        out += fade(layers, begin + r * step, 0.25)
    return out, len(art["lines"]) * lh, len(art["lines"][0]) * size * 0.6


def write(name, width, height, body):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" viewBox="0 0 {width:g} {height:g}" '
           f'fill="none" font-family="{esc(FAMILY)}"><style>{FONTS}{CSS}</style>{body}</svg>\n')
    (ROOT / name).write_text(svg, encoding="utf-8")


def wrap(s: str, width: int) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    return lines + ([cur] if cur else [])


def fmt_range(a, b) -> str:
    if not a:
        return "no active run"
    return a.strftime("%b %-d, %Y") if a == b else f"{a.strftime('%b %-d')} → {b.strftime('%b %-d, %Y')}"


def portrait_palette() -> list[str]:
    """The portrait's own colours (its k-means clusters), for neofetch's colour blocks."""
    return re.findall(r"\.k\d+\{fill:(#[0-9a-f]{6})\}", (ROOT / "ascii.svg").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ windows

def draw_terminal(profile, year, current, longest, langs, today):
    repos = profile["repositories"]
    created = dt.date.fromisoformat(profile["createdAt"][:10])
    now_file = ROOT / "now.txt"
    now = (now_file.read_text(encoding="utf-8").strip().splitlines() or [""])[0] if now_file.exists() else ""
    if not now:
        latest = next((r["name"] for r in repos["nodes"] if r["name"] != LOGIN), "")
        now = f"shipping {latest}"
    fields = [
        ("host", f"github.com/{LOGIN}"),
        ("uptime", f"{(today - created).days // 365} years"),
        ("repos", f"{repos['totalCount']} public"),
        ("langs", " · ".join(n.lower() for n, _ in langs.most_common(4))),
        ("commits", f"{sum(year.values())} this year · {sum(1 for n in year.values() if n)} active days"),
        ("streak", f"{current[0]} day{'s' * (current[0] != 1)} · best {longest[0]}"),
        ("now", now),
    ]
    mini = json.loads((DATA / "mini.json").read_text(encoding="utf-8"))
    body, t = typed(20, 30, "neofetch", 0.2, "pt")
    art, art_h, art_w = ascii_art(20, 46, mini, 9.4, t, 0.025, "m")
    x = 20 + art_w + 34
    info = (text(x, 62, LOGIN, "grn", 14, 600) + text(x + len(LOGIN) * 8.4, 62, "@", "ink", 14)
            + text(x + (len(LOGIN) + 1) * 8.4, 62, "github", "grn", 14, 600)
            + text(x, 80, "-" * (len(LOGIN) + 7), "fnt", 13))
    for i, (k, v) in enumerate(fields):
        y = 104 + i * 21
        info += fade(text(x, y, k, "amb", 13, 600) + text(x + 9 * CW, y, v, "ink", 13), t + 0.15 + i * 0.07, 0.3)
    sw_y = 104 + len(fields) * 21 - 4
    swatches = "".join(f'<rect x="{x + i * 26}" y="{sw_y}" width="22" height="12" rx="2" fill="{h}"/>'
                       for i, h in enumerate(portrait_palette()))
    body += art + info + fade(swatches, t + 0.8, 0.4)
    height = BAR + max(46 + art_h, sw_y + 12) + 20
    write("terminal.svg", W, height, window(W, height, f"{LOGIN} — zsh", body))


def draw_cards(profile):
    logos = json.loads((DATA / "logos.json").read_text(encoding="utf-8"))
    meta = {r["name"]: r for r in profile["repositories"]["nodes"]}
    for p in json.loads((DATA / "projects.json").read_text(encoding="utf-8")):
        r = meta.get(p["repo"], {})
        name = p.get("name", p["repo"])
        lang = next((e["node"]["name"] for e in (r.get("languages") or {}).get("edges", [])
                     if e["node"]["name"] not in EXCLUDE_LANGS), "").lower()
        pushed = (r.get("pushedAt") or "")[:10]
        logo = logos[p["logo"]]
        rows = len(logo["lines"])
        size = min(9.6, 160 / (rows * 1.12))  # tall logos shrink to fit the same box
        art, art_h, _ = ascii_art(16, (176 - rows * size * 1.12) / 2, logo, size, 0.15, 0.02, "l")
        tx = 172
        body = art + text(tx, 34, f"{name}/", "blu", 15, 600)
        body += text(tx, 54, " · ".join(s for s in (lang, f"pushed {pushed}" if pushed else "") if s), "mut", 11.5)
        for j, line in enumerate(wrap(p["blurb"], 30)[:6]):
            body += text(tx, 80 + j * 17.5, line, "ink", 12)
        height = BAR + 184
        write(f"card-{name}.svg", CARD_W, height, window(CARD_W, height, f"~/projects/{name}", fade(body, 0.05, 0.3)))


def draw_activity(repos):
    commits = recent_commits(repos)
    body, t = typed(20, 30, f"git log --all --author={LOGIN} --oneline -{len(commits)}", 0.2, "pa")
    for i, (when, repo, sha, msg) in enumerate(commits):
        y = 60 + i * 23
        room = 76 - len(repo)
        msg = msg if len(msg) <= room else msg[: room - 1].rstrip() + "…"
        line = (text(20, y, sha, "amb", 13) + text(20 + 8 * CW, y, repo, "blu", 13)
                + text(20 + (9 + len(repo)) * CW, y, msg, "ink", 13) + text(W - 20, y, when[:10], "fnt", 12, anchor="end"))
        body += fade(line, t + 0.1 + i * 0.08, 0.3)
    height = BAR + 60 + len(commits) * 23 + 4
    write("activity.svg", W, height, window(W, height, "~ — git log", body))


def draw_stats(year, start, current, longest):
    total = sum(year.values())
    active = sum(1 for n in year.values() if n)
    best_day, best = max(year.items(), key=lambda kv: (kv[1], kv[0])) if year else (start, 0)
    weeks = defaultdict(int)
    for d, n in year.items():
        weeks[(d - start).days // 7] += n
    series = [weeks[i] for i in range(max(weeks) + 1)] if weeks else [0]
    x0, x1, top, base, peak = 20, W - 20, 150, 204, max(series) or 1
    xs = [x0 + i * (x1 - x0) / (len(series) - 1 or 1) for i in range(len(series))]
    ys = [base - (v / peak) * (base - top) for v in series]
    line = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in zip(xs, ys))
    length = sum(math.dist(p, q) for p, q in zip(zip(xs, ys), list(zip(xs, ys))[1:])) + 1
    body, t = typed(20, 30, "gh contributions --last-year", 0.2, "ps")
    body += fade(text(20, 98, f"{total:,}", "ink", 48, 600) + text(20, 122, "contributions in the last year", "mut", 12), t + 0.05)
    body += fade(text(x1, 70, active, "ink", 18, 600, "end") + text(x1, 86, "active days", "mut", 11, anchor="end")
                 + text(x1, 114, best, "ink", 18, 600, "end")
                 + text(x1, 130, f"best day · {best_day.strftime('%b %-d')}", "mut", 11, anchor="end"), t + 0.2)
    body += (f'<line x1="{x0}" y1="{base}" x2="{x1}" y2="{base}" class="edge" stroke-width="1"/>'
             + fade(f'<path d="{line}L{x1} {base}L{x0} {base}Z" class="soft"/>', t + 1.0, 0.5)
             + f'<path d="{line}" class="accs" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" '
               f'stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}">'
               f'<animate attributeName="stroke-dashoffset" from="{length:.0f}" to="0" begin="{t + 0.3:.2f}s" dur="1.2s" fill="freeze"/></path>'
             + text(x0, 222, f"weekly · {start.strftime('%b %Y')}", "fnt", 10.5) + text(x1, 222, "this week", "fnt", 10.5, anchor="end"))

    def streak(x, label, s, begin):
        n, a, b = s
        return fade(text(x, 256, label, "mut", 11.5) + text(x, 286, n, "ink", 26, 600)
                    + text(x + len(str(n)) * 15.6 + 8, 286, "day" if n == 1 else "days", "mut", 13)
                    + text(x, 306, fmt_range(a, b), "fnt", 11.5), begin)
    ratio = 0 if not longest[0] else min(current[0] / longest[0], 1)
    body += (streak(20, "current streak", current, t + 0.4) + streak(420, "longest streak", longest, t + 0.5)
             + f'<rect x="{x0}" y="320" width="{x1 - x0}" height="3" rx="1.5" class="trk"/>'
               f'<rect x="{x0}" y="320" width="0" height="3" rx="1.5" class="amb">'
               f'<animate attributeName="width" from="0" to="{(x1 - x0) * ratio:.1f}" begin="{t + 0.7:.2f}s" dur="0.8s" fill="freeze"/></rect>')
    write("stats.svg", W, BAR + 340, window(W, BAR + 340, "~ — contributions", body))


def draw_langs(langs, year):
    top = langs.most_common(6)
    total = sum(langs.values()) or 1
    body, t = typed(20, 30, "gh repo languages --by bytes", 0.2, "pl")
    left = text(20, 58, "languages · public repos", "mut", 11.5)
    for i, (name, v) in enumerate(top):
        y = 84 + i * 30
        left += (text(20, y, name, "ink", 13) + text(380, y, f"{v / total * 100:.1f}%", "mut", 12, anchor="end")
                 + f'<rect x="20" y="{y + 7}" width="360" height="4" rx="2" class="trk"/>'
                 + f'<rect x="20" y="{y + 7}" width="0" height="4" rx="2" class="amb">'
                   f'<animate attributeName="width" from="0" to="{360 * v / top[0][1]:.1f}" begin="{t + 0.2 + i * 0.07:.2f}s" dur="0.6s" fill="freeze"/></rect>')
    # weekday rhythm: when the work lands (replaces the flat "by repo" column)
    by_day = [0] * 7
    for d, n in year.items():
        by_day[d.weekday()] += n
    peak = max(by_day) or 1
    right = text(440, 58, "rhythm · contributions by weekday", "mut", 11.5)
    for i, (label, v) in enumerate(zip(["mon", "tue", "wed", "thu", "fri", "sat", "sun"], by_day)):
        cx = 456 + i * 50
        h = 6 + 130 * v / peak
        right += (f'<rect x="{cx - 14}" y="{230 - h:.1f}" width="28" height="{h:.1f}" rx="3" class="{"amb" if v == peak else "trk"}"/>'
                  + text(cx, 248, label, "mut", 11, anchor="middle") + text(cx, 224 - h, v, "ink", 11, anchor="middle"))
    body += fade(left, t + 0.1) + fade(right, t + 0.3)
    write("langs.svg", W, BAR + 262, window(W, BAR + 262, "~ — languages", body))


def draw_year(year, start, end):
    """One character per day, weeks as columns (Sunday at the top), ramp quiet → loud."""
    first_sunday = start - dt.timedelta(days=(start.weekday() + 1) % 7)
    cols = (end - first_sunday).days // 7 + 1
    x0, pitch, top = 20, (W - 40) / cols, 74
    nonzero = sorted(n for n in year.values() if n)
    q = [nonzero[int(len(nonzero) * f)] for f in (0.25, 0.5, 0.75)] if nonzero else [1, 2, 3]

    def char(n):
        return "·" if n <= 0 else ":" if n <= q[0] else "+" if n <= q[1] else "#" if n <= q[2] else "@"

    quiet, loud, months = "", "", ""
    for row in range(7):
        for col in range(cols):
            d = first_sunday + dt.timedelta(days=col * 7 + row)
            if not (start <= d <= end):
                continue
            c = char(year.get(d, 0))
            cell = f'<text x="{x0 + col * pitch + pitch / 2:.1f}" y="{top + row * 16}" font-size="13" text-anchor="middle">{esc(c)}</text>'
            if c == "·":
                quiet += cell
            else:
                loud += cell
    for col in range(1, cols):
        d = first_sunday + dt.timedelta(days=col * 7)
        if d.day <= 7 and x0 + col * pitch + 18 <= W - 20:
            months += text(x0 + col * pitch, 54, d.strftime("%b").lower(), "fnt", 10.5)
    body, t = typed(20, 30, "git calendar --last-year", 0.2, "py")
    sweep = (f'<clipPath id="sw"><rect x="0" y="40" height="130" width="0">'
             f'<animate attributeName="width" from="0" to="{W}" begin="{t:.2f}s" dur="1.4s" fill="freeze"/></rect></clipPath>')
    body += (months + sweep + f'<g clip-path="url(#sw)"><g class="fnt">{quiet}</g><g class="amb">{loud}</g></g>'
             + text(20, 192, f"{sum(1 for n in year.values() if n)} active days of {len(year)}", "fnt", 11)
             + text(W - 20, 192, "quiet · : + # @ loud", "fnt", 11, anchor="end"))
    write("year.svg", W, BAR + 206, window(W, BAR + 206, "~ — calendar", body))


# ------------------------------------------------------------------ main

def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=364)
    year = calendar(start, today)

    profile = gql(PROFILE, {"login": LOGIN})
    created = dt.date.fromisoformat(profile["createdAt"][:10])
    history = dict(year)
    window_end = start - dt.timedelta(days=1)
    while window_end >= created:  # whole history in one-year windows, for the longest streak
        window_start = max(created, window_end - dt.timedelta(days=364))
        history.update(calendar(window_start, window_end))
        window_end = window_start - dt.timedelta(days=1)

    current, longest = streaks(history, today)
    repos = profile["repositories"]["nodes"]
    langs = languages(repos)
    draw_terminal(profile, year, current, longest, langs, today)
    draw_cards(profile)
    draw_activity(repos)
    draw_stats(year, start, current, longest)
    draw_langs(langs, year)
    draw_year(year, start, today)
    print(f"{LOGIN}: {sum(year.values())} contributions, streak {current[0]} (longest {longest[0]})")


if __name__ == "__main__":
    main()
