#!/usr/bin/env python3
"""
Builds an animated ASCII version of a GitHub avatar plus live profile stats
as a single self-contained SVG (no JavaScript, works inside a README <img>).

Usage:  python ascii_profile.py <github_username> <out.svg> [--avatar local.png]
Env:    GITHUB_TOKEN (optional, raises the API rate limit)
"""
import argparse, io, os, sys, json, datetime, html
import requests
from PIL import Image, ImageOps, ImageEnhance

COLS = 72                      # ASCII width in characters
CELL_W, CELL_H = 5.4, 9.0      # monospace cell size at font-size 9
RAMP = " .,:;i1tfLCG08@"       # dark -> bright
W, H = 920, 470


def gh(path, token):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"https://api.github.com{path}", headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def load_avatar(user, token, local):
    if local:
        return Image.open(local).convert("RGB"), {}
    info = gh(f"/users/{user}", token)
    img = requests.get(info["avatar_url"] + "&s=400", timeout=20).content
    return Image.open(io.BytesIO(img)).convert("RGB"), info


def to_ascii(img):
    rows = round(COLS * CELL_W / CELL_H * 1.0 * (img.height / img.width) / (CELL_W / CELL_H) * (CELL_W / CELL_H))
    rows = int(COLS * (CELL_W / CELL_H) * (img.height / img.width))
    img = ImageOps.autocontrast(img.convert("L"), cutoff=2)
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = img.resize((COLS, rows), Image.LANCZOS)
    px = img.load()
    lines = []
    cx, cy = (COLS - 1) / 2, (rows - 1) / 2
    for y in range(rows):
        row = []
        for x in range(COLS):
            # circular crop, using real (aspect-corrected) distance
            dx = (x - cx) / (COLS / 2)
            dy = (y - cy) / (rows / 2)
            if dx * dx + dy * dy > 1.0:
                row.append(" ")
                continue
            v = px[x, y] / 255
            row.append(RAMP[min(len(RAMP) - 1, int(v * len(RAMP)))])
        lines.append("".join(row))
    return lines


def ago(iso):
    try:
        t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        s = int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds())
        for n, u in ((86400, "d"), (3600, "h"), (60, "m")):
            if s >= n:
                return f"{s // n}{u} ago"
        return "just now"
    except Exception:
        return "n/a"


def live_stats(user, token, info):
    s = {"name": info.get("name") or user, "followers": "-", "following": "-",
         "repos": "-", "stars": "-", "last": "n/a", "event": "n/a"}
    try:
        if not info:
            info = gh(f"/users/{user}", token)
        s.update(name=info.get("name") or user, followers=info["followers"],
                 following=info["following"], repos=info["public_repos"])
        repos = gh(f"/users/{user}/repos?per_page=100&type=owner", token)
        s["stars"] = sum(r["stargazers_count"] for r in repos)
        ev = gh(f"/users/{user}/events/public?per_page=1", token)
        if ev:
            s["last"] = ago(ev[0]["created_at"])
            s["event"] = ev[0]["type"].replace("Event", "")
    except Exception as e:  # never fail the build because of an API hiccup
        print("stats warning:", e, file=sys.stderr)
    return s


def build_svg(user, art, st):
    esc = html.escape
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ax, ay = 36, 74                                   # art origin
    aw, ah = COLS * CELL_W, len(art) * CELL_H

    art_rows = "".join(
        f'<tspan x="{ax}" y="{ay + i * CELL_H:.1f}">{esc(r)}</tspan>' for i, r in enumerate(art)
    )

    px_, py_ = 470, 100
    lines = [
        ("$ whoami", "#7a8ba3"),
        (f"> {st['name']}  (@{user})", "#ffffff"),
        ("$ cat mission.txt", "#7a8ba3"),
        ("> Let's make Web3 prominent", "#24c6dc"),
        ("$ ./learning --now", "#7a8ba3"),
        ("> zero-knowledge + advanced crypto", "#b57bff"),
        ("$ gh stats --live", "#7a8ba3"),
        (f"> followers   {st['followers']}", "#3ddc97"),
        (f"> following   {st['following']}", "#3ddc97"),
        (f"> repos       {st['repos']}", "#3ddc97"),
        (f"> stars       {st['stars']}", "#3ddc97"),
        (f"> last event  {st['event']} · {st['last']}", "#ffd166"),
    ]
    LH, CW, DUR = 24, 8.4, 14
    typed, clips = [], []
    for i, (txt, col) in enumerate(lines):
        y = py_ + i * LH
        w = len(txt) * CW + 6
        b = i * 0.7
        clips.append(
            f'<clipPath id="c{i}"><rect x="{px_}" y="{y - 16}" width="0" height="22">'
            f'<animate attributeName="width" values="0;0;{w:.0f};{w:.0f};0" '
            f'keyTimes="0;{b / DUR:.3f};{(b + 0.6) / DUR:.3f};0.93;1" dur="{DUR}s" repeatCount="indefinite"/>'
            f'</rect></clipPath>'
        )
        typed.append(f'<text x="{px_}" y="{y}" fill="{col}" clip-path="url(#c{i})">{esc(txt)}</text>')
    cur_y = py_ + len(lines) * LH

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     font-family="'Fira Code','JetBrains Mono',Consolas,'DejaVu Sans Mono',monospace">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b0820"/><stop offset=".55" stop-color="#1a1650"/><stop offset="1" stop-color="#08283a"/>
    </linearGradient>
    <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <text id="art" font-size="9" xml:space="preserve">{art_rows}</text>
    <clipPath id="sweep"><rect x="{ax - 4}" y="{ay - 10}" width="{aw + 8:.0f}" height="46">
      <animate attributeName="y" values="{ay - 56};{ay + ah:.0f};{ay - 56}" keyTimes="0;.5;1" dur="5s" repeatCount="indefinite"/>
    </rect></clipPath>
    {''.join(clips)}
  </defs>

  <rect width="{W}" height="{H}" rx="22" fill="url(#bg)"/>
  <rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="21" fill="none" stroke="#24c6dc" stroke-opacity=".35" stroke-width="1.5"/>

  <!-- window dots + title -->
  <circle cx="30" cy="28" r="6" fill="#ff5f57"/><circle cx="52" cy="28" r="6" fill="#febc2e"/><circle cx="74" cy="28" r="6" fill="#28c840"/>
  <text x="{W / 2}" y="33" text-anchor="middle" fill="#9fb3c8" font-size="13">{esc(user)}@web3 ~ live-profile</text>

  <!-- ASCII avatar: dim base layer, bright layer revealed by a sweeping scanline -->
  <use href="#art" fill="#1f7f94" opacity=".9">
    <animate attributeName="opacity" values=".75;1;.75" dur="3s" repeatCount="indefinite"/>
  </use>
  <g clip-path="url(#sweep)" filter="url(#glow)"><use href="#art" fill="#c9fbff"/></g>

  <!-- terminal panel -->
  <g font-size="14">{''.join(typed)}</g>
  <text x="{px_}" y="{cur_y + 6}" fill="#24c6dc" font-size="14">▌
    <animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite"/>
  </text>

  <!-- footer -->
  <text x="{W - 30}" y="{H - 22}" text-anchor="end" fill="#6b7f99" font-size="11">last synced {now} · auto-updates every few minutes</text>
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("user"); ap.add_argument("out")
    ap.add_argument("--avatar")
    a = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    img, info = load_avatar(a.user, token, a.avatar)
    art = to_ascii(img)
    st = live_stats(a.user, token, info)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(build_svg(a.user, art, st))
    print("wrote", a.out, f"({len(art)} rows)")


if __name__ == "__main__":
    main()
