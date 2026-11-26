#!/usr/bin/env python3
"""
"Signal Brief" GitHub profile skin.

Writes a set of animated SVG cards (dark + light) for a recruiter-focused
profile README. Everything is drawn here: no third-party card services, so the
README renders the same way every time and never hits a rate limit.

Usage:
  python build_skin.py                      # writes ./assets/*.svg
  GITHUB_TOKEN=... python build_skin.py     # also refreshes repo/contribution counts live
"""
import base64
import json
import os
import urllib.request
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "assets"
USER = "Bhavya8121-spy"

# ------------------------------------------------------------------ content --
PROFILE = {
    "name": "Bhavya Patel",
    "eyebrow": f"SIGNAL BRIEF · @{USER.lower()}",
    "role": "Software engineer",
    "school": "Computer Science @ Vanderbilt · Class of 2028",
    "seeking": "Seeking a Summer 2027 internship in SWE, data, or AI",
    "status": "Open to internships",
}

STATS = [  # label, value (value may be refreshed live)
    ("public repos", "14"),
    ("shipped projects", "7"),
    ("main language", "Python"),
    ("graduating", "2028"),
]

SIGNAL = [
    ("01", "ROLE FIT", [
        "Backend + LLM systems in Python",
        "Flask, Postgres, vector search",
        "Front ends in TS when needed",
    ]),
    ("02", "PUBLIC PROOF", [
        "AgentShield: agent guardrails",
        "Offline RAG over private PDFs",
        "Live demos, not just repos",
    ]),
    ("03", "MOMENTUM", [
        "Learning LLM evaluation properly",
        "Studying system design",
        "Shipping two browser games",
    ]),
]

PROJECTS = [
    {
        "slug": "agentshield", "name": "AgentShield", "tag": "AI SAFETY",
        "lines": ["A permission checkpoint between an AI agent",
                  "and its actions. Prompt injections can't talk",
                  "their way into deleting data."],
        "stack": "Python · Oracle OCI",
        "url": f"https://github.com/{USER}/agentshield",
    },
    {
        "slug": "ragengine", "name": "RAG Engine", "tag": "OFFLINE AI",
        "lines": ["PDF Q&A with no API keys and no cloud.",
                  "Chunking, embeddings, vector search, and a",
                  "similarity floor that filters weak matches."],
        "stack": "Python · Ollama · ChromaDB",
        "url": f"https://github.com/{USER}/RAGEngine",
    },
    {
        "slug": "logtunnel", "name": "Log Tunnel", "tag": "INFRA",
        "lines": ["App → shipper → Postgres → live dashboard,",
                  "plus a Chaos Monkey panel that fires timeouts",
                  "and dropped connections on demand."],
        "stack": "Python · PostgreSQL · WebSockets · Docker",
        "url": f"https://github.com/{USER}/Log-Tunnel-Chaos-Monkey-Simulator",
    },
    {
        "slug": "transfer", "name": "Transfer Pathway", "tag": "PLANNING",
        "lines": ["Parses messy transcripts into a prerequisite-",
                  "safe four-year plan. A graph scheduler balances",
                  "STEM load across terms."],
        "stack": "Python · Flask · Pandas",
        "url": f"https://github.com/{USER}/Transfer-Pathway",
    },
    {
        "slug": "statement", "name": "Statement Reader", "tag": "FINANCE",
        "lines": ["Turns a raw bank CSV into real merchants,",
                  "categories, and a plain-language read of",
                  "where the money went."],
        "stack": "Python · Streamlit · SQLite · Gemini",
        "url": f"https://github.com/{USER}/Personal_Finance",
    },
    {
        "slug": "meridian", "name": "Meridian Drive", "tag": "FOR FUN",
        "lines": ["Open-world city driving in the browser with",
                  "real physics. Sibling project Relic Isle is a",
                  "survival game on a cursed island."],
        "stack": "JavaScript · three.js · Rapier",
        "url": f"https://bhavya8121-spy.github.io/meridian-drive/",
    },
]

STACK = [
    ("LANGUAGES", ["Python", "TypeScript", "JavaScript", "SQL"]),
    ("BACKEND + DATA", ["Flask", "PostgreSQL", "SQLite", "Pandas", "WebSockets"]),
    ("AI", ["Ollama", "ChromaDB", "Gemini API", "RAG", "Embeddings"]),
    ("TOOLING", ["Docker", "Git", "GitHub Actions", "three.js", "Streamlit"]),
]

# ------------------------------------------------------------------- themes --
THEMES = {
    "dark": dict(bg="#0b0f0d", panel="#0f1512", line="#1f2a24", grid="#141c18",
                 fg="#e8f0eb", mute="#8a9a91", dim="#55645b", accent="#3fe08a",
                 accent2="#7cf2b4", chip="#132019"),
    "light": dict(bg="#f7f9f7", panel="#ffffff", line="#d9e2dc", grid="#eef3ef",
                  fg="#0f1a14", mute="#5b6b62", dim="#8b9a91", accent="#13894d",
                  accent2="#1fae66", chip="#e9f5ee"),
}

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"


def base_style(t):
    return f"""
  <style>
    .sans {{ font-family: {SANS}; }}
    .mono {{ font-family: {MONO}; }}
    .fg {{ fill: {t['fg']}; }} .mute {{ fill: {t['mute']}; }} .dim {{ fill: {t['dim']}; }}
    .acc {{ fill: {t['accent']}; }}
    .rise {{ animation: rise .7s cubic-bezier(.2,.7,.2,1) backwards; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .25; }} }}
    @keyframes scan {{ from {{ transform: translateY(0); }} to {{ transform: translateY(var(--scan, 200px)); }} }}
    @keyframes blink {{ 0%,49% {{ opacity: 1; }} 50%,100% {{ opacity: 0; }} }}
    @keyframes draw {{ from {{ stroke-dashoffset: 840; }} to {{ stroke-dashoffset: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      * {{ animation: none !important; }}
    }}
  </style>"""


def svg(w, h, t, body, label):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">
  <title>{escape(label)}</title>{base_style(t)}
  <defs>
    <pattern id="grid" width="16" height="16" patternUnits="userSpaceOnUse">
      <path d="M16 0H0V16" fill="none" stroke="{t['grid']}" stroke-width="1"/>
    </pattern>
  </defs>
  <rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="14" fill="{t['bg']}" stroke="{t['line']}"/>
  <rect x="1" y="1" width="{w-2}" height="{h-2}" rx="13" fill="url(#grid)" opacity=".7"/>
{body}
</svg>
"""


def corner_ticks(x, y, w, h, t, s=8):
    c = t["accent"]
    return (f'<path d="M{x} {y+s}V{y}H{x+s} M{x+w-s} {y}H{x+w}V{y+s} '
            f'M{x+w} {y+h-s}V{y+h}H{x+w-s} M{x+s} {y+h}H{x}V{y+h-s}" '
            f'fill="none" stroke="{c}" stroke-width="1.5"/>')


# ------------------------------------------------------------------- cards ---
def header(t, avatar_b64):
    W, H = 840, 330
    p = PROFILE
    stats = ""
    sw = (W - 48) / len(STATS)
    for i, (label, val) in enumerate(STATS):
        x = 24 + i * sw
        sep = f'<line x1="{x}" y1="262" x2="{x}" y2="306" stroke="{t["line"]}"/>' if i else ""
        stats += f"""
    <g class="rise" style="animation-delay:{0.9 + i*0.12:.2f}s">{sep}
      <text x="{x + 18}" y="282" class="sans fg" font-size="22" font-weight="700">{escape(val)}</text>
      <text x="{x + 18}" y="300" class="mono mute" font-size="10.5" letter-spacing="1">{escape(label.upper())}</text>
    </g>"""

    body = f"""
  <!-- left column -->
  <g class="rise" style="animation-delay:.05s">
    <text x="40" y="58" class="mono acc" font-size="11" letter-spacing="2">{escape(p['eyebrow'])}</text>
  </g>
  <g class="rise" style="animation-delay:.18s">
    <text x="38" y="112" class="sans fg" font-size="46" font-weight="800" letter-spacing="-1.2">{escape(p['name'])}</text>
  </g>
  <g class="rise" style="animation-delay:.32s">
    <text x="40" y="146" class="sans fg" font-size="19" font-weight="600">{escape(p['role'])}<tspan class="acc" style="animation: blink 1.1s steps(1) infinite">_</tspan></text>
    <text x="40" y="172" class="sans mute" font-size="14.5">{escape(p['school'])}</text>
    <text x="40" y="194" class="sans mute" font-size="14.5">{escape(p['seeking'])}</text>
  </g>
  <g class="rise" style="animation-delay:.5s">
    <rect x="40" y="212" width="176" height="28" rx="14" fill="{t['chip']}" stroke="{t['accent']}" stroke-opacity=".45"/>
    <circle cx="58" cy="226" r="4.5" class="acc" style="animation: pulse 1.6s ease-in-out infinite"/>
    <text x="71" y="230.5" class="mono acc" font-size="11.5" letter-spacing=".6">{escape(p['status'].upper())}</text>
  </g>

  <!-- portrait -->
  <g class="rise" style="animation-delay:.25s">
    <clipPath id="ph"><rect x="618" y="38" width="184" height="184" rx="10"/></clipPath>
    <rect x="618" y="38" width="184" height="184" rx="10" fill="{t['panel']}"/>
    <image x="618" y="38" width="184" height="184" clip-path="url(#ph)" preserveAspectRatio="xMidYMid slice" href="data:image/jpeg;base64,{avatar_b64}"/>
    <g clip-path="url(#ph)">
      <rect x="618" y="30" width="184" height="10" fill="{t['accent']}" opacity=".22"
            style="--scan:194px; animation: scan 3.2s linear infinite"/>
    </g>
    {corner_ticks(610, 30, 200, 200, t)}
    <text x="618" y="244" class="mono dim" font-size="10" letter-spacing="1">ID · {USER.upper()}</text>
  </g>

  <!-- stat strip -->
  <line x1="24" y1="252" x2="{W-24}" y2="252" stroke="{t['line']}"/>
  {stats}
"""
    return svg(W, H, t, body, f"{p['name']}, {p['role']}. {p['school']}. {p['seeking']}.")


def section_title(t, text, num):
    W, H = 840, 54
    body = f"""
  <g class="rise">
    <text x="28" y="34" class="mono acc" font-size="12" letter-spacing="2">{num}</text>
    <text x="62" y="35" class="sans fg" font-size="20" font-weight="700" letter-spacing="-.3">{escape(text)}</text>
    <line x1="{80 + len(text)*10.5:.0f}" y1="29" x2="{W-28}" y2="29" stroke="{t['line']}"
          stroke-dasharray="{W}" style="animation: draw 1.2s .2s ease-out backwards"/>
  </g>"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(text)}">
  <title>{escape(text)}</title>{base_style(t)}
{body}
</svg>
"""


def signal(t):
    W, H = 840, 200
    cw = (W - 48 - 24) / 3
    cols = ""
    for i, (n, title, bullets) in enumerate(SIGNAL):
        x = 24 + i * (cw + 12)
        items = "".join(
            f'<text x="{x+22}" y="{96 + j*26}" class="sans fg" font-size="13.5">'
            f'<tspan class="acc">›</tspan>  {escape(b)}</text>'
            for j, b in enumerate(bullets))
        cols += f"""
  <g class="rise" style="animation-delay:{0.1 + i*0.15:.2f}s">
    <rect x="{x}" y="24" width="{cw:.1f}" height="152" rx="10" fill="{t['panel']}" stroke="{t['line']}"/>
    <text x="{x+22}" y="56" class="mono dim" font-size="11">{n}</text>
    <text x="{x+46}" y="56" class="mono acc" font-size="11.5" letter-spacing="1.6">{title}</text>
    <line x1="{x+22}" y1="70" x2="{x+cw-22:.1f}" y2="70" stroke="{t['line']}"/>
    {items}
  </g>"""
    return svg(W, H, t, cols, "What teams can evaluate quickly: role fit, public proof, momentum.")


def project(t, p, idx):
    W, H = 412, 196
    lines = "".join(
        f'<text x="24" y="{98 + j*20}" class="sans mute" font-size="13">{escape(l)}</text>'
        for j, l in enumerate(p["lines"]))
    tagw = len(p["tag"]) * 7.2 + 20
    body = f"""
  <g class="rise" style="animation-delay:{0.05 + (idx % 2)*0.12:.2f}s">
    <text x="24" y="38" class="mono dim" font-size="11">{idx+1:02d}</text>
    <rect x="{W-24-tagw:.1f}" y="22" width="{tagw:.1f}" height="22" rx="11" fill="{t['chip']}"/>
    <text x="{W-24-tagw/2:.1f}" y="37" text-anchor="middle" class="mono acc" font-size="10.5" letter-spacing="1">{escape(p['tag'])}</text>
    <text x="24" y="70" class="sans fg" font-size="21" font-weight="700" letter-spacing="-.3">{escape(p['name'])}</text>
    {lines}
    <line x1="24" y1="160" x2="{W-24}" y2="160" stroke="{t['line']}"/>
    <text x="24" y="181" class="mono acc" font-size="11">{escape(p['stack'])}</text>
    <text x="{W-24}" y="181" text-anchor="end" class="mono mute" font-size="11">open ↗</text>
  </g>"""
    return svg(W, H, t, body, f"{p['name']}: {' '.join(p['lines'])} Built with {p['stack']}.")


def stack(t):
    W = 840
    row_h = 46
    H = 30 + row_h * len(STACK) + 10
    rows = ""
    for i, (group, items) in enumerate(STACK):
        y = 30 + i * row_h
        x = 190
        chips = ""
        for k, it in enumerate(items):
            w = len(it) * 7.6 + 26
            chips += f"""
      <g class="rise" style="animation-delay:{0.1 + i*0.12 + k*0.05:.2f}s">
        <rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="28" rx="7" fill="{t['panel']}" stroke="{t['line']}"/>
        <text x="{x + w/2:.1f}" y="{y+18.5}" text-anchor="middle" class="sans fg" font-size="13">{escape(it)}</text>
      </g>"""
            x += w + 8
        rows += f"""
    <text x="28" y="{y+18.5}" class="mono acc" font-size="11" letter-spacing="1.6">{group}</text>{chips}"""
    return svg(W, H, t, rows, "Technical toolkit: " + "; ".join(f"{g}: {', '.join(i)}" for g, i in STACK))


def contact(t):
    W, H = 840, 150
    body = f"""
  <g class="rise">
    <text x="420" y="62" text-anchor="middle" class="sans fg" font-size="26" font-weight="800" letter-spacing="-.6">Let’s talk about the next build.</text>
    <text x="420" y="92" text-anchor="middle" class="sans mute" font-size="14.5">Internships, projects, or half-formed ideas. Links are just below.</text>
  </g>
  <g class="rise" style="animation-delay:.3s">
    <circle cx="352" cy="120" r="4" class="acc" style="animation: pulse 1.6s ease-in-out infinite"/>
    <text x="364" y="124" class="mono acc" font-size="11" letter-spacing="1.4">REPLIES WITHIN A DAY</text>
  </g>"""
    return svg(W, H, t, body, "Let's talk about the next build.")


# --------------------------------------------------------------- live data ---
def refresh_stats():
    token = os.environ.get("GITHUB_TOKEN")
    try:
        req = urllib.request.Request(f"https://api.github.com/users/{USER}")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        STATS[0] = ("public repos", str(data["public_repos"]))
    except Exception as e:  # offline is fine; keep the defaults
        print(f"(stats not refreshed: {e})")


def main():
    refresh_stats()
    OUT.mkdir(exist_ok=True)
    avatar = base64.b64encode((HERE / "avatar.jpg").read_bytes()).decode()
    titles = [("01", "What teams can evaluate quickly"), ("02", "Selected work"),
              ("03", "Technical toolkit"), ("04", "Activity")]
    for name, t in THEMES.items():
        files = {
            "header": header(t, avatar),
            "signal": signal(t),
            "stack": stack(t),
            "contact": contact(t),
        }
        for i, p in enumerate(PROJECTS):
            files[f"project-{p['slug']}"] = project(t, p, i)
        for num, text in titles:
            files[f"title-{num}"] = section_title(t, text, num)
        for k, v in files.items():
            (OUT / f"{k}-{name}.svg").write_text(v, encoding="utf-8")
    print(f"wrote {len(list(OUT.glob('*.svg')))} SVGs to {OUT}")


if __name__ == "__main__":
    main()
