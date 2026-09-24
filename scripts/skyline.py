#!/usr/bin/env python3
"""Draw an ASCII-character city skyline that lights up with your GitHub
contributions, in a dark-mode and a light-mode SVG so GitHub can pick the
right one for the viewer (same trick behind most "theme-aware" profile
READMEs: two SVGs, swapped with a <picture> element).

Run by .github/workflows/skyline.yml once a day. Locally you can preview
any count without a token:

    python scripts/skyline.py --preview 320
"""
import os
import sys
import json
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "iolis16")
GOAL = int(os.environ.get("GOAL", "500"))  # contributions that fill the whole skyline
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_PREFIX = os.environ.get("OUT_PREFIX", "skyline")  # -> skyline-dark.svg / skyline-light.svg

CHAR_W, CHAR_H = 9, 16
COLS = 72
PADDING = 16

# (width, height) in character cells, left to right
BUILDINGS = [
    (6, 6), (7, 11), (5, 8), (8, 15), (6, 9),
    (7, 12), (5, 7), (6, 10), (6, 8),
]
TALLEST = 3  # index of the building that gets the rooftop light

GROUND_ROW = max(h for _, h in BUILDINGS) + 6  # rows of sky above the tallest building
ROWS = GROUND_ROW + 1
GRID_H = ROWS * CHAR_H
VIEW_W = COLS * CHAR_W + PADDING * 2
VIEW_H = GRID_H + 44 + PADDING * 2

MOON_ART = [" .--.  ", "(     )", " `--'  "]
SUN_ART = [" \\ | / ", "-  O  -", " / | \\ "]

PALETTES = {
    "dark": dict(
        card="#0B0E22", sky_top="#161B33", sky_bottom="#2E2255",
        wall="#3A4170", window_off="#4B5386", window_on="#FFC773",
        ink="#C9CEEC", ground="#12152C", beacon="#FF6B6B", accent="#FFD08A",
    ),
    "light": dict(
        card="#F6F8FC", sky_top="#EAF2FF", sky_bottom="#D7E6FB",
        wall="#AAB6D8", window_off="#C7D2EE", window_on="#DB7F2E",
        ink="#3B4270", ground="#C7D2EE", beacon="#C94A34", accent="#DB7F2E",
    ),
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { totalContributions }
    }
  }
}"""


def fetch_total() -> int:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GitHub API error: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


class Grid:
    def __init__(self):
        self.cells = [[{"ch": " ", "color": None, "cls": None} for _ in range(COLS)] for _ in range(ROWS)]

    def set(self, r, c, ch, color, cls=None):
        if 0 <= r < ROWS and 0 <= c < COLS:
            self.cells[r][c] = {"ch": ch, "color": color, "cls": cls}

    def row_svg(self, r):
        runs, cur = [], None
        for cell in self.cells[r]:
            key = (cell["color"], cell["cls"])
            if cur and cur[0] == key:
                cur = (key, cur[1] + cell["ch"])
            else:
                if cur:
                    runs.append(cur)
                cur = (key, cell["ch"])
        if cur:
            runs.append(cur)
        if all(color is None for (color, cls), _ in runs):
            return ""
        parts = []
        for (color, cls), text in runs:
            t = escape(text)
            if color is None:
                parts.append(t)
            else:
                cls_attr = f' class="{cls}"' if cls else ""
                parts.append(f'<tspan{cls_attr} fill="{color}">{t}</tspan>')
        y = r * CHAR_H + CHAR_H * 0.8
        return f'<text x="0" y="{y:.1f}" xml:space="preserve" textLength="{COLS * CHAR_W}" lengthAdjust="spacingAndGlyphs">{"".join(parts)}</text>'


def fill_building(grid, idx, col_start, width, height, seg_frac, pal):
    window_rel_rows = [rr for rr in range(height) if rr % 2 == 0]
    total_wr = len(window_rel_rows)
    lit_wr = round(seg_frac * total_wr)
    for rr in range(height):
        r = GROUND_ROW - 1 - rr
        is_window_row = rr % 2 == 0
        for cc in range(width):
            c = col_start + cc
            border = cc == 0 or cc == width - 1
            is_window_col = (cc % 2 == 1) and not border
            if is_window_row and is_window_col:
                wr_index = window_rel_rows.index(rr)
                lit = wr_index < lit_wr and ((idx * 31 + rr * 7 + cc * 13) % 5 != 0)
                if lit:
                    grid.set(r, c, "█", pal["window_on"], "glow")
                else:
                    grid.set(r, c, "▒", pal["window_off"])
            else:
                grid.set(r, c, "▓", pal["wall"])


def build_svg(count: int, mode: str) -> str:
    pal = PALETTES[mode]
    frac = min(count / GOAL, 1.0) if GOAL > 0 else 1.0
    pct = round(count / GOAL * 100) if GOAL > 0 else 100
    complete = count >= GOAL

    grid = Grid()

    # ground
    for c in range(COLS):
        grid.set(GROUND_ROW, c, "█", pal["ground"])

    # sky decor
    art, art_color = (MOON_ART, pal["ink"]) if mode == "dark" else (SUN_ART, pal["accent"])
    for r, line in enumerate(art):
        for c, ch in enumerate(line):
            if ch != " ":
                grid.set(r, 60 + c, ch, art_color)
    if mode == "dark":
        for i, (r, c) in enumerate([
            (0, 8), (1, 20), (0, 32), (2, 44), (1, 50),
            (3, 14), (2, 26), (4, 38), (0, 4), (3, 55),
        ]):
            grid.set(r, c, "." if i % 3 else "*", pal["ink"], f"star st{i % 4}")

    # buildings
    col = 4
    for i, (w, h) in enumerate(BUILDINGS):
        seg_frac = min(max(frac * len(BUILDINGS) - i, 0.0), 1.0)
        fill_building(grid, i, col, w, h, seg_frac, pal)
        if i == TALLEST:
            top_row = GROUND_ROW - h
            beacon_col = col + w // 2
            grid.set(top_row - 1, beacon_col, "◆", pal["beacon"], "beacon blink" if complete else "beacon")
            if complete:
                grid.set(top_row - 3, beacon_col + 2, "✦", pal["accent"], "sparkle")
        col += w + 1

    rows_svg = "".join(grid.row_svg(r) for r in range(ROWS))
    caption = "skyline complete! ✨" if complete else f"{pct}% lit by a {GOAL:,}-contribution skyline"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}" width="{VIEW_W}" height="{VIEW_H}" role="img" aria-label="ASCII city skyline {pct}% lit: {count} GitHub contributions this year">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{pal['sky_top']}" />
      <stop offset="100%" stop-color="{pal['sky_bottom']}" />
    </linearGradient>
    <clipPath id="card-clip"><rect width="{VIEW_W}" height="{VIEW_H}" rx="14" /></clipPath>
  </defs>
  <style>
    text {{ font-family: 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: {CHAR_H - 2}px; }}
    .star {{ animation: twinkle 3s ease-in-out infinite; }}
    .st1 {{ animation-delay: .6s; }} .st2 {{ animation-delay: 1.2s; }} .st3 {{ animation-delay: 1.8s; }}
    @keyframes twinkle {{ 0%,100% {{ opacity: .3; }} 50% {{ opacity: 1; }} }}
    .glow {{ animation: flicker 6s ease-in-out infinite; }}
    @keyframes flicker {{ 0%,94%,100% {{ opacity: 1; }} 96% {{ opacity: .5; }} }}
    .beacon.blink {{ animation: blink 1.4s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity: .15; }} }}
    .sparkle {{ animation: pulse 1.8s ease-in-out infinite; }}
    @keyframes pulse {{ 0%,100% {{ opacity: .4; }} 50% {{ opacity: 1; }} }}
    .cap {{ fill: {pal['ink']}; text-anchor: middle; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>

  <rect width="{VIEW_W}" height="{VIEW_H}" rx="14" fill="{pal['card']}" />
  <g clip-path="url(#card-clip)">
    <g transform="translate({PADDING},{PADDING})">
      <rect x="0" y="0" width="{COLS * CHAR_W}" height="{GRID_H}" fill="url(#sky)" />
      {rows_svg}
    </g>
  </g>

  <text class="cap" x="{VIEW_W / 2:.0f}" y="{PADDING + GRID_H + 22}" font-size="16" font-weight="700">{count:,} contributions this year</text>
  <text class="cap" x="{VIEW_W / 2:.0f}" y="{PADDING + GRID_H + 38}" font-size="12">{caption}</text>
</svg>
"""


def render_both(count: int, prefix: str):
    for mode in ("dark", "light"):
        path = f"{prefix}-{mode}.svg"
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_svg(count, mode))
        print(f"{USER}: {count} contributions -> {path}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--preview":
        total = int(sys.argv[2])
        render_both(total, os.environ.get("OUT_PREFIX", "preview"))
    else:
        if not TOKEN:
            sys.exit("Set GITHUB_TOKEN (or use --preview N)")
        total = fetch_total()
        render_both(total, OUT_PREFIX)
