#!/usr/bin/env python3
"""
Surf contribution graph generator.

Fetches your real GitHub contribution calendar and writes two animated SVGs
(dark + light). Animation loop:

  1. Your contribution graph is shown.
  2. A pixel-art wave sweeps across and washes every square away.
  3. A surfer assembles, square by square, on the empty beach.
  4. The surfer rides across the graph and every contribution pops back in
     behind them, right where it belongs.

Usage:
  GITHUB_TOKEN=... python generate_surf.py --user Bhavya8121-spy --out dist
  python generate_surf.py --demo --out dist        # fake data, no token needed
"""
import argparse
import datetime as dt
import json
import os
import random
import urllib.request

# ---------------------------------------------------------------- layout ----
CELL = 11            # contribution square size
PITCH = 14           # cell + gap
SUB = 7              # size of the tiny squares used for wave + surfer (PITCH / 2)
PAD_L, PAD_T = 34, 22
PAD_R, PAD_B = 12, 34
WEEKS = 53
LOOP = 22.0          # seconds for one full loop

# timeline (seconds)
T_WAVE_START, T_WAVE_END = 5.0, 9.0
T_ASSEMBLE_START = 9.2      # first surfer square pops in
T_ASSEMBLE_SPREAD = 1.6     # pops are spread over this many seconds
T_RIDE_START, T_RIDE_END = 12.2, 18.2
T_SURFER_GONE = 18.6

# ---------------------------------------------------------------- themes ----
THEMES = {
    "dark": {
        "empty": "#161b22",
        "levels": ["#0b3a5b", "#0f6aa6", "#1aa3c9", "#6be7e9"],  # ocean palette
        "text": "#8b949e",
        "foam": "#ffffff",
    },
    "light": {
        "empty": "#ebedf0",
        "levels": ["#b7e3f5", "#6cc3e8", "#2a9bd0", "#0b6aa0"],
        "text": "#57606a",
        "foam": "#bfe8fb",
    },
}
GREEN = {
    "dark": ["#0e4429", "#006d32", "#26a641", "#39d353"],
    "light": ["#9be9a8", "#40c463", "#30a14e", "#216e39"],
}

# --------------------------------------------------------- pixel-art maps ----
# h hair  s skin  r shorts  y board  o board stripe
# f foam  a light water  b mid water  d deep water
SURFER = [
    ".........hhh..........",
    ".........hss...ss.....",
    ".........sss.ss.......",
    ".......ssssss.........",
    ".....ss..sss..........",
    "...ss....sss..........",
    ".........sss..........",
    "........rrrrr.........",
    ".......ssrrrss........",
    "......ss.....ss.......",
    "fa.yyyyyyyyooyyyyyyyy.",
    "ffaaafaaaaaaaaafaaaaaa",
    ".bbbbbbbbbbbbbbbbbbbbb",
    "..dddddddddddddddddd..",
]
SURFER_COLORS = {
    "h": "#4a2f1f", "s": "#f2b283", "r": "#ff5a5f",
    "y": "#ffd166", "o": "#ef476f",
    "a": "#7fd8ff", "b": "#2a9fe0", "d": "#0b5fa5",
}

WAVE_COLS = 26
WAVE_HEIGHTS = [1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 14, 14, 14, 13, 11, 9, 7, 5, 3]
WAVE_CREST_COL = 18   # column where the wave is tallest (used to time the wipe)


def build_wave(foam_color, rng):
    """Return list of (col, row, color) for the wave pixel-art (14 rows tall)."""
    px = []
    for c, h in enumerate(WAVE_HEIGHTS):
        top = 14 - h
        for r in range(top, 14):
            depth = r - top
            if depth == 0:
                col = foam_color
            elif depth == 1:
                col = "#bff0ff" if rng.random() < 0.6 else "#7fd8ff"
            elif depth <= 3:
                col = "#7fd8ff"
            elif depth <= 6:
                col = "#2a9fe0"
            else:
                col = "#0b5fa5"
            px.append((c, r, col))
    # curling lip + spray in front of the crest
    for c, r in [(20, 0), (21, 1), (22, 3), (23, 5), (24, 7), (25, 9), (21, 2), (23, 4)]:
        px.append((c, r, foam_color))
    for _ in range(14):
        px.append((rng.randint(14, WAVE_COLS - 1), rng.randint(0, 9), foam_color))
    # dedupe (later entries win)
    seen = {}
    for c, r, col in px:
        seen[(c, r)] = col
    return [(c, r, col) for (c, r), col in seen.items()]


# ------------------------------------------------------------------ data ----
GQL = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionLevel contributionCount } }
      }
    }
  }
}
"""
LEVEL_MAP = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
             "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch_calendar(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": GQL, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "surf-contributions"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["date"], d["weekday"], LEVEL_MAP[d["contributionLevel"]], d["contributionCount"])
              for d in w["contributionDays"]] for w in cal["weeks"]]
    return weeks, cal["totalContributions"]


def demo_calendar():
    rng = random.Random(7)
    end = dt.date.today()
    start = end - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    weeks, total, d = [], 0, start
    while d <= end:
        week = []
        for wd in range(7):
            if d <= end:
                n = 0 if rng.random() < 0.45 else rng.randint(1, 12)
                lvl = 0 if n == 0 else min(4, 1 + n // 4)
                week.append((d.isoformat(), wd, lvl, n))
                total += n
            d += dt.timedelta(days=1)
        weeks.append(week)
    return weeks, total


# ------------------------------------------------------------------- svg ----
def pct(t):
    return round(100.0 * t / LOOP, 3)


def build_svg(weeks, total, theme_name, palette):
    theme = dict(THEMES[theme_name])
    if palette == "green":
        theme["levels"] = GREEN[theme_name]
    rng = random.Random(42)

    n_weeks = len(weeks)
    grid_w = n_weeks * PITCH
    width = PAD_L + grid_w + PAD_R
    height = PAD_T + 7 * PITCH + PAD_B
    wave_w = WAVE_COLS * SUB
    surfer_w = len(SURFER[0]) * SUB
    wave_travel = width + wave_w
    css, body = [], []

    # ---- per-column keyframes: wash out when the wave crest passes, pop back
    #      in when the surfer passes
    surfer_x0 = PAD_L + 6
    surfer_center0 = surfer_x0 + surfer_w * 0.5
    surfer_x1 = width + 10
    ride_travel = surfer_x1 - surfer_x0
    t_cols = []
    for w in range(n_weeks):
        x = PAD_L + w * PITCH + CELL / 2
        u = (x + wave_w - WAVE_CREST_COL * SUB) / wave_travel
        t_out = T_WAVE_START + (T_WAVE_END - T_WAVE_START) * min(max(u, 0), 1)
        # cell reappears when the surfer's centre has passed it
        s = (x - surfer_center0) / ride_travel
        if s < 0:
            t_in = T_RIDE_START + 0.04 * w
        else:
            t_in = T_RIDE_START + (T_RIDE_END - T_RIDE_START) * min(s, 1) + 0.15
        t_cols.append((t_out, max(t_in, t_out + 0.6)))

    for w, (t_out, t_in) in enumerate(t_cols):
        css.append(
            f"@keyframes c{w}{{0%,{pct(t_out - .01)}%{{opacity:1;transform:scale(1)}}"
            f"{pct(t_out + .25)}%,{pct(t_in - .01)}%{{opacity:0;transform:scale(.2)}}"
            f"{pct(t_in + .35)}%,100%{{opacity:1;transform:scale(1)}}}}"
        )
        css.append(f".c{w}{{animation:c{w} {LOOP}s linear infinite}}")

    css.append(
        ".cell{transform-box:fill-box;transform-origin:center}"
        f".px{{transform-box:fill-box;transform-origin:center}}"
    )

    # ---- wave sweep
    css.append(
        f"@keyframes wave{{0%,{pct(T_WAVE_START)}%{{transform:translateX({-wave_w - 8}px)}}"
        f"{pct(T_WAVE_END)}%,100%{{transform:translateX({width + 8}px)}}}}"
        f".wave{{animation:wave {LOOP}s linear infinite}}"
        "@keyframes foam{0%,100%{opacity:1}50%{opacity:.55}}"
        ".foam{animation:foam .5s ease-in-out infinite}"
    )

    # ---- surfer: show window, ride, bob, per-pixel assemble
    css.append(
        f"@keyframes show{{0%,{pct(T_ASSEMBLE_START - .05)}%{{opacity:0}}"
        f"{pct(T_ASSEMBLE_START)}%,{pct(T_SURFER_GONE)}%{{opacity:1}}"
        f"{pct(T_SURFER_GONE + .01)}%,100%{{opacity:0}}}}"
        f".show{{animation:show {LOOP}s linear infinite}}"
        f"@keyframes ride{{0%,{pct(T_RIDE_START)}%{{transform:translateX({surfer_x0}px)}}"
        f"{pct(T_RIDE_END)}%,100%{{transform:translateX({surfer_x1}px)}}}}"
        f".ride{{animation:ride {LOOP}s cubic-bezier(.45,0,.55,1) infinite}}"
        "@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}"
        ".bob{animation:bob .9s ease-in-out infinite}"
        f"@keyframes pop{{0%{{transform:scale(0);opacity:0}}"
        f"1.2%{{transform:scale(1.35);opacity:1}}2%,100%{{transform:scale(1);opacity:1}}}}"
        f".pop{{animation:pop {LOOP}s linear infinite backwards}}"
    )

    # ---- contribution cells
    body.append(f'<g id="cells" transform="translate({PAD_L},{PAD_T})">')
    for w, week in enumerate(weeks):
        for date, wd, lvl, count in week:
            fill = theme["empty"] if lvl == 0 else theme["levels"][lvl - 1]
            delay = round(wd * 0.04, 2)
            body.append(
                f'<rect class="cell c{w}" x="{w * PITCH}" y="{wd * PITCH}" width="{CELL}" '
                f'height="{CELL}" rx="2" fill="{fill}" style="animation-delay:{delay}s">'
                f"<title>{count} contributions on {date}</title></rect>"
            )
    body.append("</g>")

    # ---- month + weekday labels
    labels, last_month = [], None
    for w, week in enumerate(weeks):
        d = dt.date.fromisoformat(week[0][0])
        if d.month != last_month and (w == 0 or d.day <= 14) and w < n_weeks - 2:
            labels.append(f'<text x="{PAD_L + w * PITCH}" y="{PAD_T - 8}">{d.strftime("%b")}</text>')
        last_month = d.month
    for wd, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        labels.append(f'<text x="{PAD_L - 8}" y="{PAD_T + wd * PITCH + 9}" text-anchor="end">{name}</text>')
    body.append(f'<g class="lbl">{"".join(labels)}</g>')

    # ---- wave (tiny squares)
    wave_y = PAD_T
    wave_px = []
    for c, r, col in build_wave(theme["foam"], rng):
        cls = ' class="foam"' if col == theme["foam"] and rng.random() < 0.4 else ""
        style = f' style="animation-delay:{round(rng.random() * .5, 2)}s"' if cls else ""
        wave_px.append(
            f'<rect{cls} x="{c * SUB}" y="{r * SUB}" width="{SUB - 1}" height="{SUB - 1}" '
            f'rx="1" fill="{col}"{style}/>'
        )
    body.append(
        f'<g transform="translate(0,{wave_y})"><g class="wave" style="transform:translateX({-wave_w - 8}px)">'
        f'{"".join(wave_px)}</g></g>'
    )

    # ---- surfer (tiny squares, popped in at random times while assembling)
    surf_px = []
    for r, row in enumerate(SURFER):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            col = theme["foam"] if ch == "f" else SURFER_COLORS[ch]
            # assemble from the bottom up with some randomness
            order = (len(SURFER) - r) / len(SURFER)
            delay = T_ASSEMBLE_START + T_ASSEMBLE_SPREAD * min(1, order * .7 + rng.random() * .3)
            surf_px.append(
                f'<rect class="px pop" x="{c * SUB}" y="{r * SUB}" width="{SUB - 1}" height="{SUB - 1}" '
                f'rx="1" fill="{col}" style="animation-delay:{delay:.2f}s"/>'
            )
    body.append(
        f'<g transform="translate(0,{PAD_T})"><g class="show" style="opacity:0">'
        f'<g class="ride" style="transform:translateX({surfer_x0}px)"><g class="bob">'
        f'{"".join(surf_px)}</g></g></g></g>'
    )

    # ---- footer: total + legend
    legend_x = PAD_L + grid_w - 5 * PITCH - 70
    leg = [f'<text x="{legend_x}" y="{height - 10}" text-anchor="end">Less</text>']
    for i, c in enumerate([theme["empty"]] + theme["levels"]):
        leg.append(f'<rect x="{legend_x + 6 + i * PITCH}" y="{height - 20}" width="{CELL}" height="{CELL}" rx="2" fill="{c}"/>')
    leg.append(f'<text x="{legend_x + 6 + 5 * PITCH + CELL + 6}" y="{height - 10}">More</text>')
    body.append(
        f'<g class="lbl"><text x="{PAD_L}" y="{height - 10}">{total} contributions in the last year</text>'
        f'{"".join(leg)}</g>'
    )

    style = (
        f'.lbl text{{font:10px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;fill:{theme["text"]}}}'
        + "".join(css)
        # respect reduced-motion: just show the static graph
        + "@media (prefers-reduced-motion:reduce){*{animation:none!important}.wave,.show{display:none}}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="Animated contribution graph: a wave clears it, then a surfer rides across and restores it">'
        f"<style>{style}</style>{''.join(body)}</svg>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_USER"))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--palette", choices=["ocean", "green"], default="ocean")
    ap.add_argument("--demo", action="store_true", help="use fake data (no token needed)")
    a = ap.parse_args()

    if a.demo:
        weeks, total = demo_calendar()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not (a.user and token):
            raise SystemExit("Set --user and GITHUB_TOKEN (or use --demo).")
        weeks, total = fetch_calendar(a.user, token)

    os.makedirs(a.out, exist_ok=True)
    for theme in ("dark", "light"):
        path = os.path.join(a.out, f"surf-{theme}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_svg(weeks, total, theme, a.palette))
        print("wrote", path, f"({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    main()
