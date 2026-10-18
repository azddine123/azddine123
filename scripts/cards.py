#!/usr/bin/env python3
"""Stats card + most-used-languages card as SVGs (dark + light). Stdlib only.

    python scripts/cards.py --user azddine123 --out assets

Self-hosted on purpose: shared public stat services (github-readme-stats & co.)
go down or hit quota and take the README section with them.

Data:
  * profile + repos + languages ... GitHub REST API (GITHUB_TOKEN optional;
    a personal token belonging to the user also counts private repos)
  * contributions + streaks ....... the public contribution calendar
  * --snapshot data.json .......... offline mode, same keys as fetch() returns
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path

FONT = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", title="#aa9bef", text="#c9d1d9",
                 muted="#8b949e", value="#e6edf3", link="#58a6ff"),
    "light": dict(bg="#ffffff", border="#d0d7de", title="#1a7f37", text="#1f2328",
                  muted="#57606a", value="#1f2328", link="#0969da"),
}
LANG_COLOR = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5", "Java": "#b07219",
    "C": "#555555", "C++": "#f34b7d", "HTML": "#e34c26", "CSS": "#563d7c", "PLpgSQL": "#336790",
    "TeX": "#3D6117", "Dockerfile": "#384d54", "Jupyter Notebook": "#DA5B0B", "Shell": "#89e051",
    "Solidity": "#AA6746", "R": "#198CE7", "Go": "#00ADD8", "Rust": "#dea584", "PHP": "#4F5D95",
    "Kotlin": "#A97BFF", "Dart": "#00B4AB", "SCSS": "#c6538c", "Vue": "#41b883",
}
UA = {"User-Agent": "profile-cards"}


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #

def get(url: str, token: str | None, raw=False):
    req = urllib.request.Request(url, headers=dict(UA))
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode()
    return body if raw else json.loads(body)


def contributions(user: str) -> tuple[int, int, int]:
    """(total last year, current streak, longest streak) from the public calendar."""
    page = get(f"https://github.com/users/{user}/contributions", None, raw=True)
    ids = {}
    for tag in re.findall(r"<td[^>]*data-date=[^>]*>", page):
        d, i = re.search(r'data-date="([^"]+)"', tag), re.search(r'\bid="([^"]+)"', tag)
        if d and i:
            ids[i.group(1)] = d.group(1)
    dates = {v: k for k, v in ids.items()}
    counts: dict[str, int] = {d: 0 for d in dates}
    for cid, label in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        m = re.match(r"\s*(\d+|No) contribution", label)
        if cid in ids and m:
            counts[ids[cid]] = 0 if m.group(1) == "No" else int(m.group(1))
    days = sorted(counts.items())
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    for i in range(len(days) - 1, -1, -1):
        if days[i][1]:
            current += 1
        elif i != len(days) - 1:      # an empty today does not break the streak
            break
    return sum(counts.values()), current, longest


def fetch(user: str, token: str | None) -> dict:
    api = "https://api.github.com"
    profile = get(f"{api}/users/{user}", token)
    mine = False
    if token:
        try:
            mine = get(f"{api}/user", token).get("login", "").lower() == user.lower()
        except Exception:
            mine = False
    url = (f"{api}/user/repos?affiliation=owner&per_page=100" if mine
           else f"{api}/users/{user}/repos?type=owner&per_page=100")
    repos = [r for r in get(url, token) if not r["fork"]]
    langs: dict[str, int] = {}
    for r in repos:
        for k, v in get(r["languages_url"], token).items():
            langs[k] = langs.get(k, 0) + v
    try:
        total, cur, longest = contributions(user)
    except Exception:
        total = cur = longest = None
    return {
        "user": user,
        "stars": sum(r["stargazers_count"] for r in repos),
        "public_repos": profile["public_repos"],
        "followers": profile["followers"],
        "contributions": total, "current_streak": cur, "longest_streak": longest,
        "languages": langs,
    }


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #

def frame(w, h, c, body, label) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" '
            f'height="{h}" role="img" aria-label="{esc(label)}" font-family="{FONT}">'
            f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="{c["bg"]}" '
            f'stroke="{c["border"]}"/>{body}</svg>')


def stats_card(d: dict, theme: str) -> str:
    c = THEMES[theme]
    tiles = [("Total stars", d["stars"]), ("Public repos", d["public_repos"]),
             ("Followers", d["followers"])]
    if d.get("contributions") is not None:
        tiles += [("Contributions (1y)", d["contributions"]),
                  ("Current streak", d["current_streak"]),
                  ("Longest streak", d["longest_streak"])]
    pad, W, rh, cols = 22, 480, 46, 3
    rows = (len(tiles) + cols - 1) // cols
    H = pad + 52 + (rows - 1) * rh + 17 + pad
    tw = (W - 2 * pad) / cols
    out = [f'<text x="{pad}" y="{pad + 14}" font-size="15" font-weight="700" fill="{c["title"]}">'
           f'{esc(d["user"])}</text>',
           f'<text x="{W - pad}" y="{pad + 14}" font-size="11" text-anchor="end" '
           f'fill="{c["muted"]}">at a glance</text>',
           f'<line x1="{pad}" y1="{pad + 26}" x2="{W - pad}" y2="{pad + 26}" stroke="{c["border"]}"/>']
    for i, (label, value) in enumerate(tiles):
        x, y = pad + (i % cols) * tw, pad + 52 + (i // cols) * rh
        out.append(f'<text x="{x:.0f}" y="{y}" font-size="23" font-weight="700" '
                   f'fill="{c["value"]}">{value:,}</text>')
        out.append(f'<text x="{x:.0f}" y="{y + 17}" font-size="10.5" fill="{c["muted"]}">'
                   f'{esc(label)}</text>')
    return frame(W, H, c, "".join(out), f'{d["user"]} GitHub statistics')


def human(n: int) -> str:
    for unit, k in (("MB", 1e6), ("kB", 1e3)):
        if n >= k:
            return f"{n / k:.3g} {unit}"
    return f"{n} B"


def languages_card(d: dict, theme: str, limit=8) -> str:
    c = THEMES[theme]
    langs = sorted(d["languages"].items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in langs) or 1
    top = langs[:limit]
    W, pad = 480, 20
    rows = (len(top) + 1) // 2
    H = 78 + rows * 18 + 14
    out = [f'<text x="{W / 2}" y="30" text-anchor="middle" font-size="14" fill="{c["link"]}">'
           'Most used languages</text>',
           f'<clipPath id="bar"><rect x="{pad}" y="44" width="{W - 2 * pad}" height="8" rx="4"/></clipPath>',
           '<g clip-path="url(#bar)">']
    x = pad
    for name, v in top:
        w = (W - 2 * pad) * v / total
        out.append(f'<rect x="{x:.2f}" y="44" width="{w + .5:.2f}" height="8" '
                   f'fill="{LANG_COLOR.get(name, c["muted"])}"/>')
        x += w
    out.append(f'<rect x="{x:.2f}" y="44" width="{W - pad - x + 1:.2f}" height="8" fill="{c["border"]}"/></g>')
    colw = (W - 2 * pad) / 2
    for i, (name, v) in enumerate(top):
        cx = pad + (i % 2) * colw
        y = 80 + (i // 2) * 18
        out += [
            f'<circle cx="{cx + 5:.0f}" cy="{y - 4}" r="4.5" fill="{LANG_COLOR.get(name, c["muted"])}"/>',
            f'<text x="{cx + 16:.0f}" y="{y}" font-size="12.5" fill="{c["text"]}">{esc(name)}</text>',
            f'<text x="{cx + colw - 70:.0f}" y="{y}" font-size="10.5" text-anchor="end" '
            f'fill="{c["muted"]}">{human(v)}</text>',
            f'<text x="{cx + colw - 14:.0f}" y="{y}" font-size="10.5" text-anchor="end" '
            f'fill="{c["muted"]}">{100 * v / total:.2f}%</text>',
        ]
    return frame(W, H, c, "".join(out), "most used languages")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", type=Path, default=Path("assets"))
    ap.add_argument("--snapshot", type=Path, help="render from a saved JSON instead of the API")
    a = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    data = (json.loads(a.snapshot.read_text(encoding="utf-8")) if a.snapshot
            else fetch(a.user, token))
    a.out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (a.out / f"card-stats-{theme}.svg").write_text(stats_card(data, theme), encoding="utf-8")
        (a.out / f"languages-{theme}.svg").write_text(languages_card(data, theme), encoding="utf-8")
    print(json.dumps({k: v for k, v in data.items() if k != "languages"}))


if __name__ == "__main__":
    main()
