#!/usr/bin/env python3
"""Radar (spider) chart as a standalone SVG, dark + light. Stdlib only.

    python scripts/radar.py --data assets/skills.json  -o assets/radar
    python scripts/radar.py --data assets/langmix.json -o assets/radar-langs --values

Data file shape: {"title": "...", "axes": [{"label": "Python", "value": 88}, ...]}
Values are 0-100. Edit the JSON and the workflow redraws the chart.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FONT = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
THEMES = {
    "dark": dict(grid="#30363d", spoke="#21262d", label="#c9d1d9", value="#8b949e",
                 title="#e6edf3", fill="#aa9bef", stroke="#3fb950", vertex="#7ee787"),
    "light": dict(grid="#d0d7de", spoke="#e6eaef", label="#1f2328", value="#57606a",
                  title="#1f2328", fill="#2da44e", stroke="#1a7f37", vertex="#116329"),
}
LABEL, VALUE, TITLE = 13, 11, 15


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def polygon(r: float, n: int) -> list[tuple[float, float]]:
    return [(r * math.cos(-math.pi / 2 + i * math.tau / n),
             r * math.sin(-math.pi / 2 + i * math.tau / n)) for i in range(n)]


def approx_w(s: str, size: float) -> float:
    return len(s) * size * 0.62


def render(title: str, axes: list[tuple[str, float]], theme: str, size=440, rings=4,
           values=False) -> str:
    c = THEMES[theme]
    n = len(axes)
    r = size / 2 - 8
    vals = [max(0.0, min(100.0, v)) for _, v in axes]
    outer = polygon(r, n)

    # place labels first so the canvas grows around them instead of clipping
    labels = []
    for i, (name, _) in enumerate(axes):
        a = -math.pi / 2 + i * math.tau / n
        cx, cy = math.cos(a), math.sin(a)
        anchor = "middle" if abs(cx) < 0.25 else ("start" if cx > 0 else "end")
        dy = 4 if abs(cy) < 0.25 else (14 if cy > 0 else -5)
        labels.append(((r + 20) * cx, (r + 20) * cy + dy, anchor, name, vals[i]))

    x0, x1, y0, y1 = -r, r, -r, r
    for lx, ly, anchor, name, v in labels:
        w = max(approx_w(name, LABEL), approx_w(f"{v:g}", VALUE) if values else 0)
        left = lx if anchor == "start" else (lx - w if anchor == "end" else lx - w / 2)
        x0, x1 = min(x0, left), max(x1, left + w)
        y0, y1 = min(y0, ly - LABEL), max(y1, ly + 4 + (VALUE + 4 if values else 0))

    pad = 10
    th = TITLE + 14 if title else 0
    W, H = round(x1 - x0 + 2 * pad), round(y1 - y0 + 2 * pad + th)
    ox, oy = -x0 + pad, -y0 + pad + th
    need = round(approx_w(title, TITLE) + 2 * pad) if title else 0
    if need > W:
        ox += (need - W) / 2
        W = need

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
           f'height="{H}" role="img" aria-label="{esc(title)}" font-family="{FONT}">']
    if title:
        out.append(f'<text x="{W / 2:.1f}" y="{pad + TITLE}" text-anchor="middle" '
                   f'font-size="{TITLE}" font-weight="700" fill="{c["title"]}">{esc(title)}</text>')
    out.append(f'<g transform="translate({ox:.1f},{oy:.1f})">')
    for k in range(rings, 0, -1):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in polygon(r * k / rings, n))
        out.append(f'<polygon points="{pts}" fill="none" stroke="{c["grid"]}" '
                   f'opacity="{0.35 + 0.5 * k / rings:.2f}"/>')
    for x, y in outer:
        out.append(f'<line x1="0" y1="0" x2="{x:.1f}" y2="{y:.1f}" stroke="{c["spoke"]}"/>')
    shape = [(x * v / 100, y * v / 100) for (x, y), v in zip(outer, vals)]
    out.append('<g><animateTransform attributeName="transform" type="scale" values="0.04;1" '
               'dur="1.1s" calcMode="spline" keyTimes="0;1" keySplines="0.22 1 0.36 1" fill="freeze"/>')
    out.append(f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in shape)}" '
               f'fill="{c["fill"]}" fill-opacity="0.22" stroke="{c["stroke"]}" '
               'stroke-width="2.5" stroke-linejoin="round"/>')
    for x, y in shape:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{c["vertex"]}" '
                   f'stroke="{c["stroke"]}" stroke-width="1.2"/>')
    out.append("</g>")
    for lx, ly, anchor, name, v in labels:
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="{LABEL}" '
                   f'font-weight="600" fill="{c["label"]}">{esc(name)}</text>')
        if values:
            out.append(f'<text x="{lx:.1f}" y="{ly + VALUE + 4:.1f}" text-anchor="{anchor}" '
                       f'font-size="{VALUE}" fill="{c["value"]}">{v:g}</text>')
    out.append("</g></svg>")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("-o", "--out", type=Path, required=True, help="output path without extension")
    ap.add_argument("--values", action="store_true", help="print the number under each label")
    a = ap.parse_args()
    d = json.loads(a.data.read_text(encoding="utf-8"))
    axes = [(x["label"], float(x["value"])) for x in d["axes"]]
    for theme in THEMES:
        dest = a.out.with_name(f"{a.out.name}-{theme}.svg")
        dest.write_text(render(d.get("title", ""), axes, theme, values=a.values), encoding="utf-8")
        print("wrote", dest)


if __name__ == "__main__":
    main()
