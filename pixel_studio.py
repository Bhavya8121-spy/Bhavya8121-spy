#!/usr/bin/env python3
"""
Pixel Studio: an animated pixel-art dorm desk for a GitHub profile README.

  * the window follows Central time (day/night) and, opt-in, live weather
  * the CRT terminal replays your latest commit messages
  * the bookshelf holds one book per language, taller = more code
  * below the room: an about card, pixel-sprite project cards, an activity grid

Usage:
  python pixel_studio.py                     # uses `gh auth token` if available
  GH_TOKEN=... python pixel_studio.py        # in GitHub Actions
  WEATHER_LAT=.. WEATHER_LON=.. python pixel_studio.py   # opt-in live weather
Writes ./assets/pixel-*.svg
"""
import datetime as dt
import hashlib
import json
import math
import os
import random
import subprocess
import urllib.request
from html import escape
from pathlib import Path

from build_skin import PROJECTS, USER

HERE = Path(__file__).parent
OUT = HERE / "assets"
P = 4                          # one art pixel = 4 svg px
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#663399", "Swift": "#F05138", "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B", "Java": "#b07219", "C++": "#f34b7d",
}

# ------------------------------------------------------------- pixel font ---
FONT = {
    "A": "010101111101101", "B": "110101110101110", "C": "011100100100011",
    "D": "110101101101110", "E": "111100110100111", "F": "111100110100100",
    "G": "011100101101011", "H": "101101111101101", "I": "111010010010111",
    "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
    "M": "101111111101101", "N": "110101101101101", "O": "010101101101010",
    "P": "110101110100100", "Q": "010101101110011", "R": "110101110101101",
    "S": "011100010001110", "T": "111010010010010", "U": "101101101101111",
    "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111", "0": "111101101101111",
    "1": "010110010010111", "2": "110001010100111", "3": "110001010001110",
    "4": "101101111001001", "5": "111100110001110", "6": "011100111101111",
    "7": "111001010010010", "8": "111101111101111", "9": "111101111001110",
    " ": "000000000000000", "-": "000000111000000", ".": "000000000000010",
    ":": "000010000010000", ">": "100010001010100", "/": "001001010100100",
    "'": "010010000000000", "_": "000000000000111", "#": "101111101111101",
}


def pixel_text(s, x, y, u, color, extra=""):
    """Draw text in the 3x5 font. x, y in svg px; u = px per font pixel."""
    out = []
    for ci, ch in enumerate(s.upper()):
        g = FONT.get(ch, FONT[" "])
        for row in range(5):
            bits = g[row * 3:row * 3 + 3]
            col = 0
            while col < 3:
                if bits[col] == "1":
                    run = 1
                    while col + run < 3 and bits[col + run] == "1":
                        run += 1
                    out.append(f'<rect x="{x + (ci*4 + col)*u}" y="{y + row*u}" width="{run*u}" height="{u}"/>')
                    col += run
                else:
                    col += 1
    return f'<g fill="{color}" {extra}>{"".join(out)}</g>'


def text_w(s, u):
    return (len(s) * 4 - 1) * u


# -------------------------------------------------------------- live data ---
def gh(path, fields=None):
    """Call the GitHub API through the gh CLI (uses GH_TOKEN in Actions, your login locally)."""
    cmd = ["gh", "api", path]
    for k, v in (fields or {}).items():
        cmd += ["-f", f"{k}={v}"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if out.returncode:
        raise RuntimeError(out.stderr.strip()[:200])
    return json.loads(out.stdout)


def weather_now():
    """Opt-in: set WEATHER_LAT and WEATHER_LON to show real weather in the window."""
    lat, lon = os.environ.get("WEATHER_LAT"), os.environ.get("WEATHER_LON")
    if not (lat and lon):
        return None
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&current=weather_code,is_day,temperature_2m&temperature_unit=fahrenheit")
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)["current"]


def fetch():
    data = {"commits": [], "langs": {}, "days": [], "repos": 0, "weather": "clear", "is_day": False}
    try:
        repos = [r for r in gh(f"users/{USER}/repos?per_page=100&sort=pushed") if not r["fork"]]
        data["repos"] = len(repos)
        for r in repos:
            for lang, n in gh(r["languages_url"]).items():
                data["langs"][lang] = data["langs"].get(lang, 0) + n
        for r in repos[:5]:
            for c in gh(f"repos/{USER}/{r['name']}/commits?per_page=4"):
                data["commits"].append((c["commit"]["author"]["date"], r["name"],
                                        c["commit"]["message"].split("\n")[0]))
        data["commits"].sort(reverse=True)
    except Exception as e:
        print(f"(repo data unavailable: {e})")
    try:
        q = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
               totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
        cal = gh("graphql", {"query": q, "u": USER})["data"]["user"][
            "contributionsCollection"]["contributionCalendar"]
        data["total"] = cal["totalContributions"]
        data["days"] = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    except Exception as e:
        print(f"(contribution data unavailable: {e})")
    try:
        w = weather_now()
        if w is None:
            hour = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6)).hour  # Central time
            data["is_day"] = 7 <= hour < 18
            return data
        code = w["weather_code"]
        data["is_day"] = bool(w["is_day"])
        data["temp"] = round(w["temperature_2m"])
        data["weather"] = ("storm" if code >= 95 else "snow" if code in range(71, 78) or code in (85, 86)
                           else "rain" if code in range(51, 68) or code in range(80, 83)
                           else "fog" if code in (45, 48) else "cloudy" if code in (2, 3) else "clear")
    except Exception as e:
        print(f"(weather unavailable: {e})")
    return data


# ------------------------------------------------------------------- room ---
def R(x, y, w, h, c, extra=""):
    return f'<rect x="{x*P}" y="{y*P}" width="{w*P}" height="{h*P}" fill="{c}" {extra}/>'


def room(d):
    W, H = 210, 110
    day = d["is_day"]
    weather = d["weather"]
    rnd = random.Random(7)
    s = []

    wall, wall2 = ("#3a3f6b", "#353a63") if day else ("#1d2142", "#1a1e3c")
    # wall + wallpaper stripes
    s.append(R(0, 0, W, 92, wall))
    for x in range(0, W, 8):
        s.append(R(x, 0, 4, 92, wall2))
    s.append(R(0, 89, W, 3, "#141730"))
    # floor planks
    s.append(R(0, 92, W, 18, "#4a3226"))
    for i, y in enumerate(range(95, 110, 4)):
        s.append(R(0, y, W, 1, "#3a271e"))
        for x in range((i * 17) % 30, W, 30):
            s.append(R(x, y - 3, 1, 3, "#3a271e"))

    # ---- window with skyline + weather
    sky = {"clear": ("#5aa9e6", "#8fd0ff"), "cloudy": ("#7f93a8", "#a7b6c4"), "fog": ("#9aa6ad", "#bcc5c9"),
           "rain": ("#4d6175", "#6c8094"), "snow": ("#8fa3b5", "#b7c6d3"), "storm": ("#2f3a48", "#46525f")}[weather]
    if not day:
        sky = ("#070b24", "#141a45") if weather == "clear" else ("#10142c", "#1d2340")
    s.append(R(12, 10, 52, 42, "#11132a"))  # frame shadow
    s.append('<clipPath id="win"><rect x="56" y="48" width="192" height="144"/></clipPath>')
    sk = ['<g clip-path="url(#win)">']
    for i in range(6):
        sk.append(R(14, 12 + i * 6, 48, 6, sky[0] if i < 3 else sky[1]))
    if weather == "clear":
        if day:
            sk.append(R(48, 16, 6, 6, "#ffd866") + R(47, 17, 8, 4, "#ffd866") + R(49, 15, 4, 8, "#ffd866"))
        else:
            sk.append(R(48, 15, 5, 5, "#f4f1d0") + R(50, 15, 3, 3, sky[0]))  # crescent
            for _ in range(14):
                sx, sy = rnd.randint(15, 60), rnd.randint(13, 30)
                sk.append(R(sx, sy, 1, 1, "#ffffff",
                            f'class="tw" style="animation-delay:{rnd.random()*3:.2f}s"'))
    if weather in ("cloudy", "rain", "storm", "snow", "fog"):
        for cx, cy, sp in ((10, 15, 26), (34, 20, 34)):
            cloud = R(cx, cy, 12, 3, "#dfe6ee" if day else "#5a6277") + R(cx + 2, cy - 2, 7, 2, "#dfe6ee" if day else "#5a6277")
            sk.append(f'<g style="animation: drift {sp}s linear infinite">{cloud}</g>')
    # skyline
    x = 14
    while x < 62:
        bw, bh = rnd.randint(4, 8), rnd.randint(8, 22)
        bh = min(bh, 34)
        sk.append(R(x, 48 - bh, bw, bh, "#0d1026" if not day else "#3d4a66"))
        for wy in range(48 - bh + 2, 47, 3):
            for wx in range(x + 1, x + bw - 1, 2):
                if rnd.random() < (0.45 if not day else 0.15):
                    sk.append(R(wx, wy, 1, 1, "#ffd77a",
                                f'class="tw" style="animation-delay:{rnd.random()*6:.2f}s;animation-duration:{3+rnd.random()*5:.1f}s"'))
        x += bw + 1
    if weather in ("rain", "storm"):
        for _ in range(26):
            rx, ry = rnd.randint(14, 61), rnd.randint(-10, 44)
            sk.append(R(rx, ry, 0.5, 2, "#a8c8ff",
                        f'opacity=".8" style="animation: fall {0.6+rnd.random()*0.4:.2f}s linear infinite; animation-delay:-{rnd.random():.2f}s"'))
        if weather == "storm":
            sk.append(R(14, 12, 48, 36, "#ffffff", 'opacity="0" style="animation: flash 7s infinite"'))
    if weather == "snow":
        for _ in range(22):
            rx, ry = rnd.randint(14, 61), rnd.randint(-10, 44)
            sk.append(R(rx, ry, 1, 1, "#ffffff",
                        f'style="animation: fall {3+rnd.random()*2:.2f}s linear infinite; animation-delay:-{rnd.random()*3:.2f}s"'))
    if weather == "fog":
        sk.append(R(14, 30, 48, 18, "#d8dde0", 'opacity=".45"'))
    sk.append("</g>")
    s.extend(sk)
    # frame + mullions + sill
    for fx, fy, fw, fh in ((12, 10, 52, 2), (12, 10, 2, 40), (62, 10, 2, 40), (37, 12, 2, 36), (14, 29, 48, 2)):
        s.append(R(fx, fy, fw, fh, "#c9b79c"))
    s.append(R(10, 48, 56, 3, "#a8916f") + R(10, 51, 56, 1, "#7a6648"))
    # cactus on the sill
    s.append(R(54, 43, 6, 5, "#b5653d") + R(55, 38, 3, 5, "#4caf50") + R(53, 39, 1, 2, "#4caf50") +
             R(52, 39, 1, 1, "#4caf50") + R(59, 40, 1, 2, "#4caf50") + R(58, 41, 1, 1, "#4caf50"))

    # ---- Vanderbilt pennant
    s.append(f'<polygon points="{68*P},{28*P} {68*P},{40*P} {90*P},{34*P}" fill="#111111"/>')
    s.append(R(67, 27, 1, 14, "#8a7a5c"))
    s.append(pixel_text("VU", 70 * P, 32 * P, 4, "#cfae70"))

    # ---- neon name sign
    name = "BHAVYA PATEL"
    tw = text_w(name, P)
    sx = (117 * P) - tw // 2
    s.append(R(sx / P - 3, 3, tw / P + 6, 13, "#0f1022", 'rx="4"'))
    s.append(f'<g filter="url(#glow)" class="neon">{pixel_text(name, sx, 7*P, P, "#ff6ad5")}</g>')

    # ---- sticky notes
    s.append(R(146, 26, 9, 9, "#ffe57a") + R(147, 28, 6, 1, "#c9a93a") + R(147, 30, 4, 1, "#c9a93a"))
    s.append(R(150, 37, 9, 9, "#7ee0c3") + R(151, 39, 6, 1, "#3f9e83") + R(151, 41, 5, 1, "#3f9e83"))
    s.append(R(150, 26, 1, 1, "#e05555") + R(154, 37, 1, 1, "#e05555"))  # pins

    # ---- clock
    cx, cy = 189, 14
    for dy, half in ((-6, 3), (-5, 5), (-4, 6), (-3, 6), (-2, 7), (-1, 7), (0, 7), (1, 7), (2, 7), (3, 6), (4, 6), (5, 5), (6, 3)):
        s.append(R(cx - half, cy + dy, half * 2 + 1, 1, "#e9e4d4"))
    s.append(R(cx, cy - 6, 1, 1, "#444") + R(cx + 6, cy, 1, 1, "#444") + R(cx, cy + 6, 1, 1, "#444") + R(cx - 7, cy, 1, 1, "#444"))
    now = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6)
    hdeg, mdeg = (now.hour % 12) * 30 + now.minute * 0.5, now.minute * 6
    ccx, ccy = cx * P + 2, cy * P + 2
    s.append(f'<rect x="{ccx-1.5}" y="{ccy-14}" width="3" height="14" fill="#222" transform="rotate({hdeg} {ccx} {ccy})"/>')
    s.append(f'<rect x="{ccx-1}" y="{ccy-21}" width="2" height="21" fill="#222" transform="rotate({mdeg} {ccx} {ccy})">'
             f'<animateTransform attributeName="transform" type="rotate" from="{mdeg} {ccx} {ccy}" to="{mdeg+360} {ccx} {ccy}" dur="60s" repeatCount="indefinite"/></rect>')

    # ---- bookshelf: one book per language
    langs = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:12] or [("Python", 1)]
    total = sum(n for _, n in langs)
    for shelf_y in (36, 58):
        s.append(R(166, shelf_y, 40, 2, "#7a5338") + R(168, shelf_y + 2, 2, 2, "#5a3c28") + R(202, shelf_y + 2, 2, 2, "#5a3c28"))
    bx, sy_ = 168, 36
    for lang, n in langs:
        h = 7 + round(9 * math.sqrt(n / total))
        w = 4
        if bx + w > 205:
            bx, sy_ = 168, 58
        col = LANG_COLORS.get(lang, "#8b949e")
        s.append(f'<g><title>{escape(lang)}</title>{R(bx, sy_ - h, w, h, col)}{R(bx, sy_ - h + 2, w, 1, "#00000044")}{R(bx+1, sy_ - h, 1, h, "#ffffff22")}</g>')
        bx += w + 1
    # trophy on the lower shelf corner
    s.append(R(199, 52, 4, 3, "#ffcf4a") + R(200, 55, 2, 2, "#ffcf4a") + R(199, 57, 4, 1, "#b8892a"))

    # ---- desk
    s.append(R(68, 66, 96, 3, "#8a5d3f") + R(68, 69, 96, 1, "#5c3d29"))
    s.append(R(71, 70, 3, 22, "#6b4a35") + R(158, 70, 3, 22, "#6b4a35"))
    s.append(R(138, 70, 20, 12, "#7a543b") + R(146, 75, 4, 1, "#c9a26b"))

    # ---- CRT monitor
    s.append(R(92, 24, 50, 37, "#cfc8b8") + R(92, 24, 50, 1, "#e5dfd1") + R(141, 24, 1, 37, "#a59d8b"))
    s.append(R(95, 27, 44, 28, "#08140d"))
    s.append(R(96, 57, 2, 1, "#3fe08a", 'class="led"'))
    s.append(R(110, 61, 14, 3, "#b3ac9b") + R(104, 63, 26, 3, "#a59d8b"))
    # keyboard
    s.append(R(98, 64, 30, 2, "#3b3f4e") + "".join(R(99 + i * 2, 64, 1, 1, "#6c7184") for i in range(14)))

    # terminal text (svg px coordinates, clipped to the screen)
    lines = ["$ git log --oneline"]
    for _, repo, msg in d["commits"][:14]:
        tag = {"Bhavya8121-spy": "profile", "personal-portfolio": "portfolio"}.get(repo, repo)
        lines.append(f"{tag[:10]}> {msg}"[:31])
    if len(lines) == 1:
        lines += ["personal-portfolio: ship it", "agentshield: add replay"]
    lh = 10
    term = []
    for i, ln in enumerate(lines + lines):
        col = "#7cf2b4" if ln.startswith("$") else "#3fe08a"
        term.append(f'<text x="{96*P+3}" y="{27*P + 12 + i*lh}" fill="{col}" font-family="{MONO}" font-size="8.2">{escape(ln)}</text>')
    s.append(f'<clipPath id="scr"><rect x="{95*P}" y="{27*P}" width="{44*P}" height="{28*P}"/></clipPath>')
    s.append(f'<g clip-path="url(#scr)"><g style="animation: scroll {len(lines)*1.4:.1f}s steps({len(lines)}) infinite; --h:-{len(lines)*lh}px">{"".join(term)}</g>'
             f'{R(95, 27, 44, 28, "url(#scanlines)")}{R(95, 27, 44, 28, "#3fe08a", "opacity=\".05\"")}</g>')

    # ---- desk lamp + glow
    s.append(f'<polygon points="{78*P},{48*P} {68*P},{66*P} {92*P},{66*P}" fill="url(#lampfade)" class="glow"/>')
    s.append(R(74, 64, 8, 2, "#2c2f3a") + R(77, 47, 2, 17, "#2c2f3a") + R(73, 44, 10, 4, "#e05555") + R(75, 48, 6, 1, "#ffe9a8"))

    # ---- rubber duck (the debugger)
    duck = (R(84, 62, 6, 4, "#ffd23f") + R(86, 59, 4, 3, "#ffd23f") + R(90, 60, 2, 1, "#ff8c1a") +
            R(88, 60, 1, 1, "#1b1b1b") + R(84, 61, 1, 1, "#ffd23f"))
    s.append(f'<g class="bob">{duck}</g>')

    # ---- mug + steam
    s.append(R(146, 60, 6, 6, "#e05555") + R(152, 61, 2, 3, "#e05555") + R(147, 60, 4, 1, "#5a3826"))
    for i, sxp in enumerate((147, 149, 148)):
        s.append(R(sxp, 57, 1, 2, "#ffffff", f'class="steam" style="animation-delay:{i*0.7:.1f}s"'))

    # ---- floor props: rug, dumbbell, plant
    s.append(R(84, 97, 66, 8, "#7a2e3b") + R(86, 98, 62, 6, "#923a49") + R(88, 100, 58, 2, "#cfae70"))
    s.append(R(172, 99, 20, 2, "#555a66") + R(170, 97, 3, 6, "#22252d") + R(191, 97, 3, 6, "#22252d") +
             R(168, 98, 2, 4, "#22252d") + R(194, 98, 2, 4, "#22252d"))
    plant = (R(24, 78, 3, 12, "#3f8f45") + R(19, 76, 6, 3, "#4caf50") + R(27, 73, 6, 3, "#4caf50") +
             R(21, 70, 5, 3, "#5cc463") + R(26, 67, 4, 4, "#4caf50"))
    s.append(f'<g class="sway">{plant}</g>')
    s.append(R(19, 86, 13, 6, "#b5653d") + R(18, 85, 15, 2, "#c97a4d"))

    # night tint everywhere except the lamp pool

    stamp = f"{'DAY' if day else 'NIGHT'} · NASHVILLE · {weather.upper()}" + (f" {d['temp']}F" if "temp" in d else "")
    s.append(pixel_text(stamp, 4 * P, 104 * P + 2, 2, "#d8c9a8", 'opacity=".75"'))

    style = f"""<style>
    .tw {{ animation: tw 4s ease-in-out infinite; }}
    @keyframes tw {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .15; }} }}
    @keyframes drift {{ from {{ transform: translateX(-60px); }} to {{ transform: translateX(240px); }} }}
    @keyframes fall {{ from {{ transform: translateY(-40px); }} to {{ transform: translateY(160px); }} }}
    @keyframes flash {{ 0%,92%,96%,100% {{ opacity: 0; }} 93%,95% {{ opacity: .55; }} }}
    .neon {{ animation: neon 5s infinite; }}
    @keyframes neon {{ 0%,18%,22%,62%,64%,100% {{ opacity: 1; }} 20%,63% {{ opacity: .35; }} }}
    @keyframes scroll {{ to {{ transform: translateY(var(--h)); }} }}
    .led {{ animation: tw 1.4s steps(1) infinite; }}
    .glow {{ opacity: .85; animation: glow 3s ease-in-out infinite; }}
    @keyframes glow {{ 50% {{ opacity: 1; }} }}
    .bob {{ animation: bob 1.8s ease-in-out infinite; }}
    @keyframes bob {{ 50% {{ transform: translateY(-3px); }} }}
    .steam {{ animation: steam 2.1s linear infinite; }}
    @keyframes steam {{ 0% {{ opacity: 0; transform: translateY(0); }} 30% {{ opacity: .8; }} 100% {{ opacity: 0; transform: translateY(-22px); }} }}
    .sway {{ transform-box: fill-box; transform-origin: 50% 100%; animation: sway 4s ease-in-out infinite; }}
    @keyframes sway {{ 0%,100% {{ transform: rotate(-2deg); }} 50% {{ transform: rotate(2deg); }} }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>"""
    defs = """<defs>
    <filter id="glow" x="-20%" y="-60%" width="140%" height="220%">
      <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="lampfade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd77a" stop-opacity=".45"/><stop offset="1" stop-color="#ffd77a" stop-opacity=".05"/></linearGradient>
    <pattern id="scanlines" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".35"/></pattern>
  </defs>"""
    label = ("Animated pixel-art dorm desk. A neon sign reads Bhavya Patel; the window shows Nashville's current "
             f"weather ({weather}); a CRT terminal scrolls recent commits; the shelf holds one book per language.")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W*P}" height="{H*P}" viewBox="0 0 {W*P} {H*P}" '
            f'shape-rendering="crispEdges" role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
            f'{style}{defs}<clipPath id="frame"><rect width="{W*P}" height="{H*P}" rx="12"/></clipPath>'
            f'<g clip-path="url(#frame)">{"".join(s)}</g></svg>\n')


# ------------------------------------------------------------------ cards ---
BG, PANEL, LINE, FG, MUTE, ACC = "#0d1117", "#131a24", "#263041", "#e6edf3", "#8b98a9", "#3fe08a"


def card(w, h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{escape(label)}"><title>{escape(label)}</title>'
            f'<style>@keyframes blink{{50%{{opacity:0}}}} .cur{{animation:blink 1s steps(1) infinite}}'
            f'@keyframes pop{{from{{opacity:0}}}} .pop{{animation:pop .4s backwards}}'
            f'@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}</style>'
            f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="10" fill="{PANEL}" stroke="{LINE}"/>'
            f'<g shape-rendering="crispEdges">{body}</g></svg>\n')


def heading(txt, x, y):
    return pixel_text("> " + txt, x, y, 3, ACC) + f'<rect class="cur" x="{x + text_w("> " + txt, 3) + 6}" y="{y}" width="9" height="15" fill="{ACC}"/>'


def about(d):
    W, H = 840, 200
    px = json.loads((HERE / "avatar_pixels.json").read_text())
    u = 5
    ax, ay = 24, 56
    av = [f'<rect x="{ax-6}" y="{ay-6}" width="{len(px)*u+12}" height="{len(px)*u+12}" fill="#0b0f14" stroke="{ACC}" stroke-width="2"/>']
    for y, row in enumerate(px):
        for x, c in enumerate(row):
            av.append(f'<rect x="{ax+x*u}" y="{ay+y*u}" width="{u}" height="{u}" fill="{c}"/>')
    tx = ax + len(px) * u + 30
    stats = [("CONTRIBS", str(d.get("total", "-"))), ("REPOS", str(d["repos"] or "-")),
             ("LANGUAGES", str(len(d["langs"]) or "-")), ("BEST STREAK", f"{streaks(d)[1]}D")]
    st = ""
    for i, (lab, val) in enumerate(stats):
        x = tx + i * 135
        st += pixel_text(val, x, 136, 5, FG) + f'<text x="{x}" y="176" fill="{MUTE}" font-family="{MONO}" font-size="10.5" letter-spacing="1.2">{lab}</text>'
    body = (heading("ABOUT", 24, 22) + "".join(av) +
            f'<text x="{tx}" y="76" fill="{FG}" font-family="{MONO}" font-size="24" font-weight="700">Bhavya Patel</text>'
            f'<text x="{tx}" y="100" fill="{MUTE}" font-family="{SANS}" font-size="14">CS @ Vanderbilt, class of 2028. Python, LLM pipelines, Flask, Postgres.</text>'
            f'<text x="{tx}" y="120" fill="{ACC}" font-family="{MONO}" font-size="12.5">● open to Summer 2027 SWE / data / AI internships</text>' + st)
    return card(W, H, body, "About Bhavya Patel: CS at Vanderbilt, class of 2028, open to Summer 2027 internships.")


def sprite(name, color, x, y, u=6):
    h = hashlib.sha256(name.encode()).digest()
    out = [f'<rect x="{x-4}" y="{y-4}" width="{9*u+8}" height="{9*u+8}" fill="{color}22" stroke="{color}" stroke-opacity=".5"/>']
    for r in range(9):
        for c in range(5):
            if (h[(r * 5 + c) % 32] >> ((r + c) % 8)) & 1:
                shade = color if (h[(r + c) % 32] & 3) else "#ffffff"
                for cc in {c, 8 - c}:
                    out.append(f'<rect x="{x+cc*u}" y="{y+r*u}" width="{u}" height="{u}" fill="{shade}"/>')
    return "".join(out)


def project(p, i):
    W, H = 412, 136
    lang = p["stack"].split(" · ")[0]
    col = LANG_COLORS.get(lang, ACC)
    lines = "".join(f'<text x="98" y="{62 + j*17}" fill="{MUTE}" font-family="{SANS}" font-size="11.5">{escape(l)}</text>'
                    for j, l in enumerate(p["lines"]))
    body = (f'<g class="pop" style="animation-delay:{(i%2)*.15:.2f}s">' + sprite(p["name"], col, 24, 28) +
            f'<text x="98" y="38" fill="{FG}" font-family="{MONO}" font-size="14.5" font-weight="700">{escape(p["slug"] if False else p["name"].lower().replace(" ", "-"))}</text>'
            + lines +
            f'<rect x="98" y="{H-30}" width="8" height="8" fill="{col}"/>'
            f'<text x="112" y="{H-22}" fill="{FG}" font-family="{MONO}" font-size="10.5">{escape(p["stack"])}</text>'
            + pixel_text(p["tag"], W - 20 - text_w(p["tag"], 2), 26, 2, ACC) + "</g>")
    return card(W, H, body, f"{p['name']}: {' '.join(p['lines'])}")


def streaks(d):
    best = cur = 0
    for _, n in d["days"]:
        cur = cur + 1 if n else 0
        best = max(best, cur)
    # current streak: allow today to be empty
    days = d["days"][:]
    if days and days[-1][1] == 0:
        days = days[:-1]
    current = 0
    for _, n in reversed(days):
        if not n:
            break
        current += 1
    return current, best


def activity(d):
    W, H = 840, 190
    days = d["days"][-7 * 34:]
    ramp = ["#161d27", "#0e4429", "#006d32", "#26a641", "#39d353"]
    mx = max([n for _, n in days] or [1]) or 1
    cells = []
    for i, (_, n) in enumerate(days):
        wk, dy = divmod(i, 7)
        lvl = 0 if n == 0 else 1 + min(3, int(3.999 * n / mx))
        delay = f' class="pop" style="animation-delay:{wk*0.03:.2f}s"' if n else ""
        cells.append(f'<rect x="{24 + wk*14}" y="{56 + dy*14}" width="11" height="11" fill="{ramp[lvl]}"{delay}/>')
    cur, best = streaks(d)
    rx = 24 + 34 * 14 + 40
    side = ""
    for j, (lab, val) in enumerate((("CURRENT STREAK", f"{cur}D"), ("BEST STREAK", f"{best}D"), ("THIS YEAR", str(d.get("total", "-"))))):
        y = 56 + j * 40
        side += f'<text x="{rx}" y="{y+6}" fill="{MUTE}" font-family="{MONO}" font-size="10" letter-spacing="1.2">{lab}</text>' + pixel_text(val, rx, y + 14, 3, FG)
    body = heading("ACTIVITY", 24, 22) + "".join(cells) + side
    return card(W, H, body, f"Contribution activity: {d.get('total', 'unknown')} contributions this year, best streak {best} days.")


def main():
    OUT.mkdir(exist_ok=True)
    d = fetch()
    print(f"commits={len(d['commits'])} langs={len(d['langs'])} days={len(d['days'])} weather={d['weather']} day={d['is_day']}")
    (OUT / "pixel-room.svg").write_text(room(d), encoding="utf-8")
    (OUT / "pixel-about.svg").write_text(about(d), encoding="utf-8")
    (OUT / "pixel-activity.svg").write_text(activity(d), encoding="utf-8")
    for i, p in enumerate(PROJECTS):
        (OUT / f"pixel-project-{p['slug']}.svg").write_text(project(p, i), encoding="utf-8")
    langs = sorted(d["langs"].items(), key=lambda kv: -kv[1])
    (OUT / "pixel-langs.txt").write_text(", ".join(l for l, _ in langs), encoding="utf-8")
    print("wrote pixel-*.svg")


if __name__ == "__main__":
    main()
