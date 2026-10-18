#!/usr/bin/env python3
"""Animated terminal banner for the GitHub profile README.

    python scripts/banner.py

Reads assets/source/portrait.png (background removed, RGBA) and writes
assets/banner-dark.svg and assets/banner-light.svg.

Left panel  : 1-bit dithered portrait whose dots travel into three silhouettes
              (shield = cybersecurity, neural net = AI, </> = code) and back.
Right panel : neofetch-style SYSTEM.INFO rows, edited in ROWS below.
"""

from __future__ import annotations

import html
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/portrait.png"
ASSETS = ROOT / "assets"

HANDLE = "@azddine123"
FOOTER_RIGHT = "UTC+1 · MOROCCO NODE"

ROWS = [
    ("Subject", "Azddine El Hamdaoui"),
    ("Role", "AI & Cybersecurity Engineer"),
    ("Origin", "Béni Mellal · Morocco"),
    ("Education", "ENSA Béni Mellal · 2027"),
    ("Status", "Open to PFE Internship · 2027"),
    ("ToolChain", "VS Code · Git · Docker · Linux"),
    ("Core.Lang", "Python · TypeScript · Java · C"),
    ("Core.AI", "TensorFlow · Scikit-learn · LLM · RAG"),
    ("Core.Security", "SIEM · Sigma · MITRE ATT&CK"),
    ("Core.Backend", "FastAPI · NestJS · Node"),
    ("Core.Mobile", "React Native · Expo"),
    ("Core.Database", "PostgreSQL · MongoDB · ChromaDB"),
    ("Grid.Mail", "azddine02elhamdaoui@gmail.com"),
    ("Grid.LinkedIn", "/in/azddine-elhamdaoui"),
    ("Grid.GitHub", "azddine123"),
]

W, H = 1180, 610
LOOP = 14.2          # seconds for one portrait -> logos -> portrait cycle
INTRO = 3.2          # one-shot scattered fade-in before the loop starts
TRAVELLERS = 900
SEED = 271828
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

THEMES = {
    "dark": dict(bg="#0A101F", panel="#0D1628", panel2="#101B30", line="#25344C",
                 muted="#8291A8", text="#DDE7F5", portrait="#AA9BEF",
                 chrome="#22D3EE", accent="#10B981", shadow="#02050B"),
    "light": dict(bg="#F6F8FA", panel="#FFFFFF", panel2="#EDF3F7", line="#CBD7E1",
                  muted="#64748B", text="#172033", portrait="#4A3D7A",
                  chrome="#0891B2", accent="#10B981", shadow="#AAB7C4"),
}

# Portrait lattice inside VISUAL.MAP (frame interior is x 49..439, y 124..538)
PX, PY, PW, PH = 94, 158, 300, 340


# --------------------------------------------------------------------------- #
# silhouettes
# --------------------------------------------------------------------------- #

def silhouettes() -> dict[str, Image.Image]:
    size = 400
    out: dict[str, Image.Image] = {}

    # Shield with a keyhole: cybersecurity.
    im = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(im)
    top, left, right = 48, 70, 330
    pts = [(200, top), (right, top + 52), (right, 190)]
    for i in range(1, 21):                       # curved lower right edge
        t = i / 20
        pts.append((right - (right - 200) * t ** 1.4, 190 + (352 - 190) * math.sin(t * math.pi / 2)))
    for i in range(20, -1, -1):                  # mirrored lower left edge
        t = i / 20
        pts.append((left + (200 - left) * t ** 1.4, 190 + (352 - 190) * math.sin(t * math.pi / 2)))
    pts += [(left, 190), (left, top + 52)]
    d.polygon(pts, fill=255)
    inner = [(x * 0.80 + 200 * 0.20, y * 0.80 + 200 * 0.20) for x, y in pts]
    d.polygon(inner, fill=0)
    d.ellipse((168, 140, 232, 204), fill=255)    # keyhole head
    d.polygon([(184, 190), (216, 190), (228, 282), (172, 282)], fill=255)
    out["shield"] = im

    # Neural network: three layers of nodes fully connected.
    im = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(im)
    layers = [[110, 200, 290], [80, 160, 240, 320], [140, 260]]
    xs = [70, 200, 330]
    nodes = [[(x, y) for y in col] for x, col in zip(xs, layers)]
    for a, b in zip(nodes, nodes[1:]):
        for p in a:
            for q in b:
                d.line([p, q], fill=255, width=9)
    for col in nodes:
        for x, y in col:
            d.ellipse((x - 30, y - 30, x + 30, y + 30), fill=255)
    out["neural"] = im

    # </> code mark.
    im = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(im)
    d.line([(150, 96), (62, 200), (150, 304)], fill=255, width=42, joint="curve")
    d.line([(250, 96), (338, 200), (250, 304)], fill=255, width=42, joint="curve")
    d.line([(226, 72), (174, 328)], fill=255, width=40)
    out["code"] = im
    return out


def sample_silhouette(im: Image.Image, rng: np.random.Generator, n: int) -> np.ndarray:
    a = np.asarray(im)
    ys, xs = np.where(a > 127)
    pick = rng.choice(len(xs), n, replace=len(xs) < n)
    # 270x270 square centred inside VISUAL.MAP
    return np.column_stack((109 + xs[pick] * 0.675, 196 + ys[pick] * 0.675)).astype(np.float32)


# --------------------------------------------------------------------------- #
# portrait
# --------------------------------------------------------------------------- #

def dither(gray: np.ndarray) -> np.ndarray:
    """Serpentine Floyd-Steinberg error diffusion. True = lit."""
    g = gray.astype(np.float32) / 255.0
    h, w = g.shape
    out = np.zeros((h, w), dtype=bool)
    for y in range(h):
        ltr = y % 2 == 0
        step = 1 if ltr else -1
        for x in (range(w) if ltr else range(w - 1, -1, -1)):
            old = g[y, x]
            new = 1.0 if old >= 0.5 else 0.0
            out[y, x] = new > 0
            e = old - new
            nx = x + step
            if 0 <= nx < w:
                g[y, nx] += e * 7 / 16
            if y + 1 < h:
                px = x - step
                if 0 <= px < w:
                    g[y + 1, px] += e * 3 / 16
                g[y + 1, x] += e * 5 / 16
                if 0 <= nx < w:
                    g[y + 1, nx] += e * 1 / 16
    return out


def portrait_points(theme: str, rng: np.random.Generator) -> np.ndarray:
    src = Image.open(SOURCE).convert("RGBA")
    # Head + shoulders crop at the 300:340 frame ratio.
    crop = src.crop((80, 97, 700, 800)).resize((PW, PH), Image.Resampling.LANCZOS)
    alpha = np.asarray(crop.getchannel("A"), dtype=np.float32) / 255.0
    if theme == "dark":
        lum = np.asarray(ImageOps.grayscale(crop.convert("RGB")), dtype=np.float32)
        prep = Image.fromarray(np.uint8(np.clip(lum * alpha, 0, 255)), "L")
        prep = ImageOps.equalize(prep, mask=Image.fromarray(np.uint8((alpha > 0.08) * 255), "L"))
    else:
        white = Image.new("RGBA", crop.size, "white")
        white.alpha_composite(crop)
        prep = ImageOps.autocontrast(ImageOps.grayscale(white.convert("RGB")), cutoff=1)
    prep = ImageEnhance.Contrast(prep).enhance(1.35)
    prep = prep.filter(ImageFilter.UnsharpMask(radius=2, percent=175, threshold=1))
    bits = dither(np.asarray(prep))
    active = bits if theme == "dark" else ~bits
    active &= alpha > 0.08
    ys, xs = np.where(active)
    pts = np.column_stack((PX + xs, PY + ys)).astype(np.float32)
    if len(pts) > 18000:
        pts = pts[rng.choice(len(pts), 18000, replace=False)]
    return pts


# --------------------------------------------------------------------------- #
# svg helpers
# --------------------------------------------------------------------------- #

def f(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def runs(points: np.ndarray) -> str:
    """Merge horizontally adjacent 1px dots into 'M x y h n' runs."""
    if not len(points):
        return ""
    cells = sorted({(int(x), int(y)) for x, y in np.rint(points).astype(int)},
                   key=lambda p: (p[1], p[0]))
    parts, i = [], 0
    while i < len(cells):
        x0, y = cells[i]
        x1 = x0
        i += 1
        while i < len(cells) and cells[i][1] == y and cells[i][0] <= x1 + 1:
            x1 = cells[i][0]
            i += 1
        parts.append(f"M{x0} {y}h{x1 - x0 + 1}")
    return "".join(parts)


def match(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    r, c = linear_sum_assignment(cdist(src, dst, "sqeuclidean"))
    out = np.empty_like(dst)
    out[r] = dst[c]
    return out


def mono_w(s: str, size: float) -> float:
    return len(s) * size * 0.605


def text(x, y, s, fill, size=13, anchor=None, weight=None, extra=""):
    a = f' text-anchor="{anchor}"' if anchor else ""
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{f(x)}" y="{f(y)}"{a} fill="{fill}" font-family="{MONO}" '
            f'font-size="{size}"{w}{extra}>{html.escape(s)}</text>')


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #

def render(theme: str, portrait: np.ndarray, logos: dict[str, np.ndarray],
           rng: np.random.Generator) -> str:
    t = THEMES[theme]
    n = min(TRAVELLERS, len(portrait))
    start = portrait[rng.choice(len(portrait), n, replace=False)]
    shield = match(start, logos["shield"][:n])
    neural = match(shield, logos["neural"][:n])
    code = match(neural, logos["code"][:n])

    marks = [0, 3.0, 4.3, 6.3, 7.6, 9.6, 10.9, 12.9, 14.2]
    kt = ";".join(f(v / LOOP) for v in marks)
    frames = [start, start, shield, shield, neural, neural, code, code, start]

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">',
        "<title id=\"t\">Azddine El Hamdaoui · profile.sh --live</title>",
        '<desc id="d">Animated terminal profile: dithered portrait morphing into a '
        "shield, a neural network and a code mark, next to a system info panel.</desc>",
        "<defs>",
        f'<filter id="sh" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" '
        f'dy="12" stdDeviation="16" flood-color="{t["shadow"]}" flood-opacity=".28"/></filter>',
        f'<filter id="gl" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur '
        f'stdDeviation="3" result="b"/><feFlood flood-color="{t["chrome"]}" flood-opacity=".35"/>'
        '<feComposite in2="b" operator="in"/><feMerge><feMergeNode/>'
        '<feMergeNode in="SourceGraphic"/></feMerge></filter>',
        '<clipPath id="vc"><rect x="49" y="124" width="390" height="414" rx="3"/></clipPath>',
        "</defs>",
        f'<rect width="{W}" height="{H}" rx="18" fill="{t["bg"]}"/>',
        f'<rect x="13" y="13" width="1154" height="584" rx="13" fill="{t["panel"]}" '
        f'stroke="{t["line"]}" filter="url(#sh)"/>',
        f'<path d="M13 62H1167" stroke="{t["line"]}"/>',
        '<circle cx="38" cy="38" r="6" fill="#FF5F57"/><circle cx="59" cy="38" r="6" '
        'fill="#FEBC2E"/><circle cx="80" cy="38" r="6" fill="#28C840"/>',
        text(590, 43, "profile.sh --live", t["muted"], 13, "middle", extra=' letter-spacing=".4"'),
        # VISUAL.MAP frame
        f'<rect x="35" y="88" width="418" height="472" rx="6" fill="{t["panel2"]}" stroke="{t["line"]}"/>',
        f'<path d="M35 124H453" stroke="{t["line"]}"/>',
        text(49, 111, "VISUAL.MAP", t["chrome"], 13, weight=700, extra=' letter-spacing="1.2"'),
        text(438, 111, "300×340 / 1-BIT", t["muted"], 11, "end"),
        f'<path d="M49 141h12M49 141v12M439 141h-12M439 141v12M49 539h12M49 539v-12'
        f'M439 539h-12M439 539v-12" fill="none" stroke="{t["chrome"]}" opacity=".55"/>',
        '<g clip-path="url(#vc)" shape-rendering="crispEdges"><g>',
    ]

    # Dense portrait: 94 bands that drift toward the shield, fade out, return.
    target = shield.mean(axis=0)
    band = rng.integers(0, 94, size=len(portrait))
    jitter = rng.normal(0, 4, size=(94, 2))
    for b in range(94):
        pts = portrait[band == b]
        if not len(pts):
            continue
        dx, dy = (target - pts.mean(axis=0)) * 0.18 + jitter[b]
        p.append(
            f'<path d="{runs(pts)}" fill="none" stroke="{t["portrait"]}" stroke-width="1" opacity=".94">'
            f'<animateTransform attributeName="transform" type="translate" begin="{INTRO}s" '
            f'dur="{LOOP}s" repeatCount="indefinite" calcMode="linear" keyTimes="{kt}" '
            f'values="0 0;0 0;{f(dx)} {f(dy)};{f(dx)} {f(dy)};0 0;0 0;0 0;0 0;0 0"/>'
            f'<animate attributeName="opacity" begin="{INTRO}s" dur="{LOOP}s" repeatCount="indefinite" '
            f'keyTimes="{kt}" values=".94;.94;0;0;0;0;0;0;.94"/></path>'
        )

    # Travellers: tiny squares that carry the morph between silhouettes.
    for i in range(n):
        vals = ";".join(f"{f(fr[i, 0])} {f(fr[i, 1])}" for fr in frames)
        p.append(
            f'<path d="M-.65-.65h1.3v1.3h-1.3z" fill="{t["portrait"]}">'
            f'<animateTransform attributeName="transform" type="translate" begin="{INTRO}s" '
            f'dur="{LOOP}s" repeatCount="indefinite" calcMode="linear" keyTimes="{kt}" values="{vals}"/>'
            f'<animate attributeName="opacity" begin="{INTRO}s" dur="{LOOP}s" repeatCount="indefinite" '
            f'calcMode="linear" keyTimes="{kt}" values="0;0;1;1;1;1;1;1;0"/></path>'
        )
    p.append("</g>")

    # One-shot intro: 60 random groups fade in, then hand over to the loop.
    grp = rng.integers(0, 60, size=len(portrait))
    begins = np.empty(60)
    begins[rng.permutation(60)] = np.linspace(0.05, 1.2, 60)
    for g in range(60):
        pts = portrait[grp == g]
        if not len(pts):
            continue
        p.append(
            f'<path d="{runs(pts)}" fill="none" stroke="{t["portrait"]}" stroke-width="1" opacity="0">'
            f'<animate attributeName="opacity" begin="{f(begins[g])}s" dur=".8s" values="0;1" fill="freeze"/>'
            '<animate attributeName="opacity" begin="3.08s" dur=".12s" values="1;0" fill="freeze"/></path>'
        )
    p.append("</g>")
    p.append(text(58, 551, f"PTS {len(portrait):05d} · FS/SERPENTINE", t["muted"], 10))

    # SYSTEM.INFO panel
    p += [
        f'<rect x="474" y="88" width="672" height="472" rx="6" fill="{t["panel2"]}" stroke="{t["line"]}"/>',
        f'<path d="M474 124H1146" stroke="{t["line"]}"/>',
        text(490, 111, "SYSTEM.INFO", t["chrome"], 13, weight=700, extra=' letter-spacing="1.2"'),
        '<g filter="url(#gl)"><circle cx="915" cy="106" r="4" fill="#FF4D5A">'
        '<animate attributeName="opacity" values="1;.3;1" dur="1.6s" repeatCount="indefinite"/></circle></g>',
        text(927, 111, "LIVE", "#FF4D5A", 12, weight=700),
        f'<rect x="982" y="94" width="146" height="24" rx="12" fill="{t["chrome"]}" '
        f'fill-opacity=".16" stroke="{t["chrome"]}"/>',
        text(1055, 111, HANDLE, t["chrome"], 14, "middle", 700),
    ]
    right, y = 1127.0, 153.0
    for label, value in ROWS:
        vw, lw = mono_w(value, 14), mono_w(label, 14)
        lead = "".join(f"M{f(x)} {f(y - 4)}h1" for x in np.arange(491 + lw + 12, right - vw - 12, 5.0))
        p += [
            text(491, y, label, t["muted"], 14),
            f'<path d="{lead}" fill="none" stroke="{t["line"]}" shape-rendering="crispEdges"/>',
            text(right, y, value, t["text"], 14, "end",
                 extra=f' textLength="{f(vw)}" lengthAdjust="spacingAndGlyphs"'),
        ]
        y += 23
    p += [
        f'<path d="M490 530H1130" stroke="{t["line"]}"/>',
        text(491, 548, "● ALL SYSTEMS NOMINAL", t["accent"], 11),
        text(1128, 548, FOOTER_RIGHT, t["muted"], 11, "end"),
        "</svg>",
    ]
    return "".join(p)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"missing {SOURCE}")
    shapes = silhouettes()
    for i, theme in enumerate(THEMES):
        rng = np.random.default_rng(SEED + i)
        portrait = portrait_points(theme, rng)
        logos = {k: sample_silhouette(v, rng, TRAVELLERS) for k, v in shapes.items()}
        svg = render(theme, portrait, logos, rng)
        out = ASSETS / f"banner-{theme}.svg"
        out.write_text(svg, encoding="utf-8")
        print(f"{out.relative_to(ROOT)}  {out.stat().st_size / 1024:.0f} KiB  {len(portrait)} dots")


if __name__ == "__main__":
    main()
