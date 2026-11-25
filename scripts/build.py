"""
Pure Python 3 generator for Swar Shinde's GitHub Profile README and SVG cards.
Zero third-party dependencies required: runs locally or via GitHub Actions.
If any external API is unreachable, gracefully falls back to scripts/state.json.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html import escape

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPTS_DIR)
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
ICONS_DIR = os.path.join(SCRIPTS_DIR, "icons")
PROFILE_PATH = os.path.join(SCRIPTS_DIR, "profile.json")
STATE_PATH = os.path.join(SCRIPTS_DIR, "state.json")

FONT_DISPLAY = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONT_MONO = "ui-monospace, 'SFMono-Regular', Menlo, Monaco, Consolas, monospace"

THEMES = {
    "dark": {
        "bg": "#0A0A0B",
        "card": "#121215",
        "border": "#26262A",
        "shadow": "#000000",
        "text": "#ECE9E2",
        "muted": "#A1A1AA",
        "dot": "#3F3F46",
        "pop": "#FF4D00",
        "on_pop": "#0A0A0B",
        "go": "#3BD671",
        "on_go": "#052E16",
        "screen": "#09090B",
        "tones": {
            "blue": "#1B2E4B",
            "amber": "#4A2C10",
            "purple": "#322454",
            "red": "#4D1B22",
            "teal": "#12383E",
            "green": "#163B27",
        },
        "chip_text": "#ECE9E2",
        "heat": ["#18181D", "#591D02", "#9E3304", "#D64000", "#FF4D00"],
        "badge": {
            "yt": "#4D1B22",
            "x": "#27272A",
            "li": "#1B2E4B",
            "site": "#121215",
        },
    },
    "light": {
        "bg": "#ECE9E2",
        "card": "#FFFFFF",
        "border": "#0A0A0B",
        "shadow": "#0A0A0B",
        "text": "#0A0A0B",
        "muted": "#52525B",
        "dot": "#A1A1AA",
        "pop": "#FF4D00",
        "on_pop": "#0A0A0B",
        "go": "#2FBF71",
        "on_go": "#052E16",
        "screen": "#121215",
        "tones": {
            "blue": "#DBEAFE",
            "amber": "#FFEDD5",
            "purple": "#EDE9FE",
            "red": "#FFE4E6",
            "teal": "#CCFBF1",
            "green": "#DCFCE7",
        },
        "chip_text": "#0A0A0B",
        "heat": ["#E4E0D5", "#FFCCA8", "#FF995C", "#FF6E24", "#FF4D00"],
        "badge": {
            "yt": "#FFE4E6",
            "x": "#F4F4F5",
            "li": "#DBEAFE",
            "site": "#FFFFFF",
        },
    },
}


def load_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf8") as f:
        return json.load(f)


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def http_get(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SwarProfileBot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def file_b64_uri(path: str, mime: str = "image/jpeg") -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def compute_streaks(days: list[dict], today: date) -> tuple[dict, dict]:
    """Compute current streak (including yesterday fallback if today has 0) and longest streak."""
    by_date = {d["date"]: int(d.get("count", 0)) for d in days}
    if not by_date:
        return {"days": 0, "start": None}, {"days": 0, "start": None, "end": None}

    sorted_dates = sorted(by_date.keys())
    # Longest streak across all history
    best_days, best_start, best_end = 0, None, None
    run_days, run_start = 0, None
    prev_dt = None
    for ds in sorted_dates:
        dt = date.fromisoformat(ds)
        cnt = by_date[ds]
        if cnt > 0 and (prev_dt is None or (dt - prev_dt).days == 1):
            if run_days == 0:
                run_start = ds
            run_days += 1
            if run_days >= best_days:
                best_days = run_days
                best_start = run_start
                best_end = ds
        elif cnt > 0:
            run_days = 1
            run_start = ds
            if run_days >= best_days:
                best_days = run_days
                best_start = run_start
                best_end = ds
        else:
            run_days = 0
            run_start = None
        prev_dt = dt

    # Current streak ending today or yesterday
    cur_days = 0
    cur_start = None
    cursor = today
    if by_date.get(cursor.isoformat(), 0) == 0:
        cursor = today - timedelta(days=1)
    while by_date.get(cursor.isoformat(), 0) > 0:
        cur_days += 1
        cur_start = cursor.isoformat()
        cursor -= timedelta(days=1)

    return (
        {"days": cur_days, "start": cur_start},
        {"days": best_days, "start": best_start, "end": best_end},
    )


def fetch_github_data(username: str, today: date, fallback: dict) -> dict:
    contrib = fallback.get("contrib", {})
    repos_info = fallback.get("repos", {"public_repos": 12, "stars": 3})

    try:
        raw = json.loads(http_get(f"https://github-contributions-api.jogruber.de/v4/{username}").decode("utf8"))
        days = raw.get("contributions", [])
        if days:
            year_totals = {str(k): int(v) for k, v in raw.get("total", {}).items() if str(k).isdigit()}
            cutoff_365 = (today - timedelta(days=364)).isoformat()
            last_year = sum(int(d.get("count", 0)) for d in days if cutoff_365 <= d["date"] <= today.isoformat())
            all_time = sum(year_totals.values()) if year_totals else sum(int(d.get("count", 0)) for d in days)
            since_year = min(year_totals.keys()) if year_totals else str(today.year)
            cur_streak, best_streak = compute_streaks(days, today)
            contrib = {
                "days": days,
                "years": year_totals,
                "last_year": last_year,
                "this_year": year_totals.get(str(today.year), 0),
                "all_time": all_time,
                "since_year": since_year,
                "current_streak": cur_streak,
                "longest_streak": best_streak,
            }
    except Exception as e:
        print(f"Note: using cached GitHub contributions ({e})")

    try:
        user_raw = json.loads(http_get(f"https://api.github.com/users/{username}").decode("utf8"))
        repos_raw = json.loads(http_get(f"https://api.github.com/users/{username}/repos?per_page=100&type=owner").decode("utf8"))
        public_repos = int(user_raw.get("public_repos", repos_info.get("public_repos", 12)))
        stars = sum(int(r.get("stargazers_count", 0)) for r in repos_raw if isinstance(r, dict))
        repos_info = {"public_repos": public_repos, "stars": stars}
    except Exception as e:
        print(f"Note: using cached GitHub repos ({e})")

    return {"contrib": contrib, "repos": repos_info}


def fetch_youtube_videos(channel_id: str, fallback_videos: list[dict], cached_videos: list[dict]) -> list[dict]:
    cached_by_id = {v["id"]: v for v in cached_videos if v.get("id")}
    videos = []
    try:
        xml_bytes = http_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
        root = ET.fromstring(xml_bytes)
        ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        seen = set()
        for entry in root.findall("a:entry", ns):
            vid_el = entry.find("yt:videoId", ns)
            title_el = entry.find("a:title", ns)
            pub_el = entry.find("a:published", ns)
            if vid_el is None or title_el is None:
                continue
            vid = (vid_el.text or "").strip()
            if not vid or vid in seen:
                continue
            seen.add(vid)
            title = (title_el.text or "").strip()
            pub = (pub_el.text or "")[:10] if pub_el is not None else ""
            videos.append({"id": vid, "title": title, "date": pub})
            if len(videos) >= 3:
                break
    except Exception as e:
        print(f"Note: using cached YouTube feed ({e})")
        videos = cached_videos or fallback_videos

    if not videos:
        videos = fallback_videos

    enriched = []
    for v in videos[:3]:
        vid = v["id"]
        thumb = cached_by_id.get(vid, {}).get("thumb_b64", "")
        try:
            jpg = http_get(f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg")
            thumb = "data:image/jpeg;base64," + base64.b64encode(jpg).decode("ascii")
        except Exception as e:
            print(f"Note: using cached thumbnail for {vid} ({e})")
        enriched.append({**v, "thumb_b64": thumb})
    return enriched


def fmt_num(n: int) -> str:
    return f"{n:,}"


def fmt_date_short(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = date.fromisoformat(iso[:10])
        return dt.strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return iso


def fmt_day_month(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = date.fromisoformat(iso[:10])
        return dt.strftime("%d %b").lstrip("0")
    except ValueError:
        return iso


def svg_wrap(width: int, height: int, aria: str, theme: str, body: str, defs_extra: str = "") -> str:
    th = THEMES[theme]
    safe_aria = escape(aria, quote=True)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{safe_aria}">'
        f"<title>{escape(aria)}</title>"
        f"<defs>"
        f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
        f'<circle cx="11" cy="11" r="1.2" fill="{th["dot"]}" opacity="0.28"/>'
        f"</pattern>"
        f"{defs_extra}"
        f"</defs>"
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="18" '
        f'fill="{th["bg"]}" stroke="{th["border"]}" stroke-width="2"/>'
        f'<rect x="2" y="2" width="{width - 4}" height="{height - 4}" rx="17" fill="url(#dots)"/>'
        f"{body}"
        f"</svg>"
    )


def sticker_rect(x: float, y: float, w: float, h: float, rx: int, fill: str, th: dict, offset: int = 4) -> str:
    return (
        f'<rect x="{x + offset}" y="{y + offset}" width="{w}" height="{h}" rx="{rx}" fill="{th["shadow"]}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{th["border"]}" stroke-width="2"/>'
    )


def pill_width(text: str, font_size: int = 14, pad_x: int = 24) -> int:
    return max(74, int(len(text) * font_size * 0.57 + pad_x))


def wrap_lines(text: str, max_chars: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words:
        joined = " ".join(lines)
        if len(joined) < len(text) - 2 and not lines[-1].endswith("…"):
            lines[-1] = lines[-1][: max(1, max_chars - 1)].rstrip() + "…"
    return lines


def draw_hero(theme: str, P: dict, phone: bool = False) -> str:
    th = THEMES[theme]
    avatar_uri = file_b64_uri(os.path.join(ICONS_DIR, "avatar.jpg"))
    pills = P["heroPills"]

    if not phone:
        w, h = 880, 244
        defs = '<clipPath id="avClip"><rect x="34" y="40" width="96" height="96" rx="18"/></clipPath>'
        avatar = (
            f'<rect x="38" y="44" width="96" height="96" rx="18" fill="{th["pop"]}"/>'
            f'<image x="34" y="40" width="96" height="96" href="{avatar_uri}" clip-path="url(#avClip)" preserveAspectRatio="xMidYMid slice"/>'
            f'<rect x="34" y="40" width="96" height="96" rx="18" fill="none" stroke="{th["border"]}" stroke-width="2.2"/>'
        )
        # Tilted domain pill
        dom = P["siteDomain"]
        dw = max(124, len(dom) * 10 + 26)
        dx = w - dw - 28
        domain_pill = (
            f'<g transform="rotate(4 {dx + dw / 2:.1f} 54)">'
            + sticker_rect(dx, 32, dw, 42, 10, th["pop"], th, 4)
            + f'<text x="{dx + dw / 2:.1f}" y="59" font-family="{FONT_DISPLAY}" font-weight="800" font-size="18" '
            f'fill="{th["on_pop"]}" text-anchor="middle">{escape(dom)}</text></g>'
        )
        # Bottom pills
        px = 156
        pills_svg = []
        for p in pills:
            pw = pill_width(p["text"], 14, 26)
            fill = th["tones"].get(p["tone"], th["card"])
            pills_svg.append(
                sticker_rect(px, 168, pw, 32, 9, fill, th, 3)
                + f'<text x="{px + pw / 2:.1f}" y="189" font-family="{FONT_DISPLAY}" font-weight="700" font-size="13.5" '
                f'fill="{th["chip_text"]}" text-anchor="middle">{escape(p["text"])}</text>'
            )
            px += pw + 12

        body = (
            avatar
            + f'<text x="156" y="96" font-family="{FONT_DISPLAY}" font-weight="900" font-size="52" fill="{th["text"]}" letter-spacing="-0.02em">{escape(P["heroHeadline"])}</text>'
            + f'<text x="156" y="138" font-family="{FONT_DISPLAY}" font-weight="500" font-size="18" fill="{th["muted"]}">{escape(P["heroSubtitle"])}</text>'
            + "".join(pills_svg)
            + domain_pill
        )
        return svg_wrap(w, h, f'{P["heroHeadline"]}. {P["heroSubtitle"]}', theme, body, defs)

    # Phone variant
    w, h = 400, 290
    defs = '<clipPath id="avClipP"><rect x="24" y="24" width="64" height="64" rx="14"/></clipPath>'
    avatar = (
        f'<rect x="27" y="27" width="64" height="64" rx="14" fill="{th["pop"]}"/>'
        f'<image x="24" y="24" width="64" height="64" href="{avatar_uri}" clip-path="url(#avClipP)" preserveAspectRatio="xMidYMid slice"/>'
        f'<rect x="24" y="24" width="64" height="64" rx="14" fill="none" stroke="{th["border"]}" stroke-width="2"/>'
    )
    dom = P["siteDomain"]
    dw = max(112, len(dom) * 8 + 20)
    domain_pill = (
        sticker_rect(w - dw - 24, 26, dw, 32, 8, th["pop"], th, 3)
        + f'<text x="{w - dw / 2 - 24:.1f}" y="47" font-family="{FONT_DISPLAY}" font-weight="800" font-size="13.5" '
        f'fill="{th["on_pop"]}" text-anchor="middle">{escape(dom)}</text>'
    )
    sub_lines = wrap_lines(P["heroSubtitle"], 42, 2)
    sub_svg = "".join(
        f'<text x="24" y="{148 + i * 21}" font-family="{FONT_DISPLAY}" font-weight="500" font-size="15" fill="{th["muted"]}">{escape(line)}</text>'
        for i, line in enumerate(sub_lines)
    )
    pills_svg = []
    px, py = 24, 200
    for p in pills:
        pw = pill_width(p["text"], 13, 22)
        if px + pw > w - 24:
            px = 24
            py += 38
        fill = th["tones"].get(p["tone"], th["card"])
        pills_svg.append(
            sticker_rect(px, py, pw, 30, 8, fill, th, 3)
            + f'<text x="{px + pw / 2:.1f}" y="{py + 20}" font-family="{FONT_DISPLAY}" font-weight="700" font-size="12.5" '
            f'fill="{th["chip_text"]}" text-anchor="middle">{escape(p["text"])}</text>'
        )
        px += pw + 10

    body = (
        avatar
        + domain_pill
        + f'<text x="24" y="122" font-family="{FONT_DISPLAY}" font-weight="900" font-size="34" fill="{th["text"]}">{escape(P["heroHeadline"])}</text>'
        + sub_svg
        + "".join(pills_svg)
    )
    return svg_wrap(w, h, f'{P["heroHeadline"]}. {P["heroSubtitle"]}', theme, body, defs)


def draw_badge(theme: str, label: str, handle: str, key: str) -> str:
    th = THEMES[theme]
    if key in ("yt", "youtube"):
        badge_key = "yt"
    elif key in ("li", "linkedin"):
        badge_key = "li"
    else:
        badge_key = key

    if badge_key == "x":
        text = handle or label
    else:
        text = f"{label} {handle}".strip()
    w = max(144, int(len(text) * 8.8 + 56))
    h = 44
    fill = th["badge"].get(badge_key, th["card"])

    if badge_key == "yt":
        icon = (
            f'<rect x="14" y="12" width="22" height="16" rx="4.5" fill="{th["pop"]}" stroke="{th["border"]}" stroke-width="1.5"/>'
            f'<path d="M22.5 16.5 L29.5 20 L22.5 23.5 Z" fill="{th["on_pop"]}"/>'
        )
        tx = 44
    elif badge_key == "x":
        icon = (
            f'<rect x="13" y="10" width="20" height="20" rx="5" fill="{th["pop"]}" stroke="{th["border"]}" stroke-width="1.5"/>'
            f'<path d="M18.5 15 L27.5 25 M27.5 15 L18.5 25" stroke="{th["on_pop"]}" stroke-width="2" stroke-linecap="round"/>'
        )
        tx = 42
    elif badge_key == "li":
        icon = (
            f'<rect x="13" y="10" width="20" height="20" rx="5" fill="{th["pop"]}" stroke="{th["border"]}" stroke-width="1.5"/>'
            f'<text x="23" y="24" font-family="{FONT_DISPLAY}" font-weight="900" font-size="11.5" fill="{th["on_pop"]}" text-anchor="middle">in</text>'
        )
        tx = 42
    else:
        icon = (
            f'<circle cx="23" cy="20" r="8.5" fill="{th["pop"]}" stroke="{th["border"]}" stroke-width="1.5"/>'
            f'<path d="M15 20 H31 M23 11.5 C26 15 26 25 23 28.5 M23 11.5 C20 15 20 25 23 28.5" stroke="{th["on_pop"]}" stroke-width="1.2" fill="none"/>'
        )
        tx = 40

    body = (
        f'<rect x="4" y="4" width="{w - 6}" height="{h - 6}" rx="12" fill="{th["shadow"]}"/>'
        f'<rect x="1" y="1" width="{w - 6}" height="{h - 6}" rx="12" fill="{fill}" stroke="{th["border"]}" stroke-width="2"/>'
        + icon
        + f'<text x="{tx}" y="25" font-family="{FONT_DISPLAY}" font-weight="700" font-size="13.5" fill="{th["text"]}">{escape(text)}</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(text, quote=True)}"><title>{escape(text)}</title>{body}</svg>'
    )


def draw_github_board(theme: str, data: dict, P: dict, phone: bool = False) -> tuple[str, str]:
    th = THEMES[theme]
    c, r = data["contrib"], data["repos"]
    cur = c["current_streak"]
    best = c["longest_streak"]
    cur_sub = f"since {fmt_day_month(cur['start'])}" if cur["days"] > 0 and cur["start"] else "active build"
    best_sub = "longest streak"
    since_y = c.get("since_year", "2024")
    nsoc_prs = P.get("nsocMergedPrs", 3)

    top_cards = [
        (fmt_num(c["last_year"]), ["contributions in", "the last year"], "blue", -1.1),
        (f"{cur['days']} days", ["current streak,", cur_sub], "green", 0.9),
        (f"{best['days']} days", [best_sub, "on record"], "amber", -0.8),
        (fmt_num(c["all_time"]), ["contributions", f"since {since_y}"], "purple", 1.1),
    ]
    bot_cards = [
        (str(r["public_repos"]), "public repos", "teal", -0.6),
        (str(r["stars"]), "stars earned", "red", 0.5),
        (str(nsoc_prs), "NSoC PRs merged", "amber", -0.6),
    ]

    aria = (
        f"On GitHub: {fmt_num(c['last_year'])} contributions in the last year, "
        f"{cur['days']}-day current streak, longest streak {best['days']} days, "
        f"{fmt_num(c['all_time'])} contributions since {since_y}, {r['public_repos']} public repos, "
        f"{r['stars']} stars earned, {nsoc_prs} NSoC PRs merged."
    )
    updated = fmt_date_short(data["today"])

    if not phone:
        w, h = 880, 340
        parts = [
            f'<text x="32" y="54" font-family="{FONT_DISPLAY}" font-weight="900" font-size="28" fill="{th["text"]}">On GitHub</text>',
            f'<text x="{w - 32}" y="52" font-family="{FONT_MONO}" font-size="13" fill="{th["muted"]}" text-anchor="end">redrawn nightly · {escape(updated)}</text>',
        ]
        for idx, (val, lines, tone, rot) in enumerate(top_cards):
            x = 32 + idx * 208
            y, cw, ch = 78, 190, 138
            cx, cy = x + cw / 2, y + ch / 2
            fill = th["tones"][tone]
            parts.append(
                f'<g transform="rotate({rot} {cx:.1f} {cy:.1f})">'
                + sticker_rect(x, y, cw, ch, 18, fill, th, 4)
                + f'<circle cx="{x + cw - 24}" cy="{y + 24}" r="8" fill="{th["pop"]}" stroke="{th["border"]}" stroke-width="1.8"/>'
                + f'<text x="{x + 18}" y="{y + 70}" font-family="{FONT_DISPLAY}" font-weight="900" font-size="38" fill="{th["text"]}">{escape(val)}</text>'
                + f'<text x="{x + 18}" y="{y + 96}" font-family="{FONT_MONO}" font-size="13" fill="{th["text"]}">{escape(lines[0])}</text>'
                + f'<text x="{x + 18}" y="{y + 114}" font-family="{FONT_MONO}" font-size="13" fill="{th["text"]}">{escape(lines[1])}</text>'
                + "</g>"
            )
        bx = 32
        widths = [248, 248, 288]
        for (val, label, tone, rot), bw in zip(bot_cards, widths):
            by, bh = 238, 66
            cx, cy = bx + bw / 2, by + bh / 2
            fill = th["tones"][tone]
            lbl_x = bx + 48 + max(1, len(val)) * 20
            parts.append(
                f'<g transform="rotate({rot} {cx:.1f} {cy:.1f})">'
                + sticker_rect(bx, by, bw, bh, 16, fill, th, 4)
                + f'<circle cx="{bx + 26}" cy="{by + 33}" r="7" fill="{th["pop"]}" stroke="{th["border"]}" stroke-width="1.8"/>'
                + f'<text x="{bx + 44}" y="{by + 44}" font-family="{FONT_DISPLAY}" font-weight="900" font-size="32" fill="{th["text"]}">{escape(val)}</text>'
                + f'<text x="{lbl_x}" y="{by + 40}" font-family="{FONT_MONO}" font-size="13.5" fill="{th["text"]}">{escape(label)}</text>'
                + "</g>"
            )
            bx += bw + 16
        return svg_wrap(w, h, aria, theme, "".join(parts)), aria

    # Phone variant
    w, h = 400, 440
    parts = [
        f'<text x="24" y="44" font-family="{FONT_DISPLAY}" font-weight="900" font-size="24" fill="{th["text"]}">On GitHub</text>',
        f'<text x="{w - 24}" y="43" font-family="{FONT_MONO}" font-size="11" fill="{th["muted"]}" text-anchor="end">{escape(updated)}</text>',
    ]
    for idx, (val, lines, tone, _) in enumerate(top_cards):
        col, row = idx % 2, idx // 2
        x = 24 + col * 182
        y = 64 + row * 124
        cw, ch = 170, 112
        fill = th["tones"][tone]
        parts.append(
            sticker_rect(x, y, cw, ch, 14, fill, th, 3)
            + f'<text x="{x + 14}" y="{y + 52}" font-family="{FONT_DISPLAY}" font-weight="900" font-size="30" fill="{th["text"]}">{escape(val)}</text>'
            + f'<text x="{x + 14}" y="{y + 76}" font-family="{FONT_MONO}" font-size="11.5" fill="{th["text"]}">{escape(lines[0])}</text>'
            + f'<text x="{x + 14}" y="{y + 92}" font-family="{FONT_MONO}" font-size="11.5" fill="{th["text"]}">{escape(lines[1])}</text>'
        )
    for idx, (val, label, tone, _) in enumerate(bot_cards):
        y = 316 + idx * 36
        fill = th["tones"][tone]
        parts.append(
            sticker_rect(24, y, w - 48, 30, 10, fill, th, 2)
            + f'<text x="40" y="{y + 20}" font-family="{FONT_DISPLAY}" font-weight="900" font-size="16" fill="{th["text"]}">{escape(val)}</text>'
            + f'<text x="80" y="{y + 19}" font-family="{FONT_MONO}" font-size="12" fill="{th["text"]}">{escape(label)}</text>'
        )
    return svg_wrap(w, h, aria, theme, "".join(parts)), aria


def heat_level(count: int, max_c: int) -> int:
    if count <= 0:
        return 0
    if max_c <= 4:
        return min(4, count)
    ratio = count / max_c
    if ratio <= 0.25:
        return 1
    if ratio <= 0.5:
        return 2
    if ratio <= 0.75:
        return 3
    return 4


def draw_heatmap(theme: str, days: list[dict], start: date, end: date, title: str, phone: bool = False) -> tuple[str, int]:
    th = THEMES[theme]
    by_date = {d["date"]: int(d.get("count", 0)) for d in days}

    # Align start back to Sunday for clean 7-row GitHub columns
    grid_start = start - timedelta(days=(start.weekday() + 1) % 7)
    weeks = []
    cur = grid_start
    total = 0
    max_c = 0
    while cur <= end:
        col = []
        for _ in range(7):
            ds = cur.isoformat()
            in_range = start <= cur <= end
            cnt = by_date.get(ds, 0) if in_range else 0
            if in_range:
                total += cnt
                max_c = max(max_c, cnt)
            col.append((cur, cnt, in_range))
            cur += timedelta(days=1)
        weeks.append(col)

    w = 400 if phone else 880
    pad_x = 18 if phone else 32
    top_y = 58 if phone else 68
    avail_w = w - pad_x * 2
    n_cols = max(1, len(weeks))
    gap = 2.5 if phone else 4
    cell = max(3.5, min(22.0 if not phone else 11.5, (avail_w - gap * (n_cols - 1)) / n_cols))
    grid_w = n_cols * cell + (n_cols - 1) * gap
    start_x = pad_x + (avail_w - grid_w) / 2
    h = int(top_y + 7 * cell + 6 * gap + (24 if phone else 30))

    rects = []
    month_labels = []
    last_month = None
    for wi, col in enumerate(weeks):
        x = start_x + wi * (cell + gap)
        first_in = next((d for d, _, ok in col if ok), None)
        if first_in and first_in.month != last_month and wi < n_cols - 1:
            last_month = first_in.month
            month_labels.append(
                f'<text x="{x:.1f}" y="{top_y - 8}" font-family="{FONT_MONO}" font-size="{9 if phone else 11}" '
                f'fill="{th["muted"]}">{first_in.strftime("%b")}</text>'
            )
        for di, (_, cnt, ok) in enumerate(col):
            if not ok:
                continue
            y = top_y + di * (cell + gap)
            lvl = heat_level(cnt, max_c)
            color = th["heat"][lvl]
            rects.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="{1.5 if cell < 8 else 3}" fill="{color}"/>'
            )

    heading = f"{fmt_num(total)} contributions {title}"
    body = (
        f'<text x="{pad_x}" y="{32 if phone else 38}" font-family="{FONT_DISPLAY}" font-weight="800" '
        f'font-size="{16 if phone else 22}" fill="{th["text"]}">{escape(heading)}</text>'
        + "".join(month_labels)
        + "".join(rects)
    )
    return svg_wrap(w, h, heading, theme, body), total


def draw_sparkline_30d(theme: str, days: list[dict], today: date, phone: bool = False) -> tuple[str, int]:
    th = THEMES[theme]
    by_date = {d["date"]: int(d.get("count", 0)) for d in days}
    pts = []
    total = 0
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        cnt = by_date.get(d.isoformat(), 0)
        total += cnt
        pts.append((d, cnt))

    w = 400 if phone else 880
    h = 150 if phone else 176
    pad_x = 20 if phone else 32
    plot_x0, plot_x1 = pad_x, w - pad_x
    plot_y0, plot_y1 = 56 if phone else 64, h - 26
    max_v = max([c for _, c in pts] + [1])

    coords = []
    for idx, (_, cnt) in enumerate(pts):
        x = plot_x0 + (idx / 29) * (plot_x1 - plot_x0)
        y = plot_y1 - (cnt / max_v) * (plot_y1 - plot_y0)
        coords.append((x, y, cnt))

    poly_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in coords)
    area_pts = f"{plot_x0:.1f},{plot_y1:.1f} {poly_pts} {plot_x1:.1f},{plot_y1:.1f}"
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3.2 if cnt > 0 else 2}" fill="{th["pop"] if cnt > 0 else th["border"]}"/>'
        for x, y, cnt in coords
    )
    heading = f"{fmt_num(total)} contributions in the last 30 days"
    body = (
        f'<text x="{pad_x}" y="{32 if phone else 38}" font-family="{FONT_DISPLAY}" font-weight="800" '
        f'font-size="{16 if phone else 22}" fill="{th["text"]}">{escape(heading)}</text>'
        f'<line x1="{plot_x0}" y1="{plot_y1}" x2="{plot_x1}" y2="{plot_y1}" stroke="{th["border"]}" stroke-width="1.5"/>'
        f'<polygon points="{area_pts}" fill="{th["pop"]}" opacity="0.16"/>'
        f'<polyline points="{poly_pts}" fill="none" stroke="{th["pop"]}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>'
        + dots
    )
    return svg_wrap(w, h, heading, theme, body), total


def draw_whoami(theme: str, P: dict, phone: bool = False) -> str:
    th = THEMES[theme]
    W = P["whoami"]
    now_items = W["now"][:3]

    if not phone:
        w, h = 880, 354
        win_x, win_y, win_w, win_h = 24, 22, w - 48, h - 46
        body = (
            sticker_rect(win_x, win_y, win_w, win_h, 14, th["screen"], th, 4)
            + f'<line x1="{win_x}" y1="{win_y + 38}" x2="{win_x + win_w}" y2="{win_y + 38}" stroke="{th["border"]}" stroke-width="2"/>'
            + f'<circle cx="{win_x + 22}" cy="{win_y + 19}" r="6" fill="{th["pop"]}"/>'
            + f'<circle cx="{win_x + 42}" cy="{win_y + 19}" r="6" fill="#F59E0B"/>'
            + f'<circle cx="{win_x + 62}" cy="{win_y + 19}" r="6" fill="{th["go"]}"/>'
            + f'<text x="{w / 2:.1f}" y="{win_y + 24}" font-family="{FONT_MONO}" font-size="14" fill="#A1A1AA" text-anchor="middle">{escape(P["terminalHost"])}: ~</text>'
            + f'<text x="48" y="96" font-family="{FONT_MONO}" font-size="16"><tspan fill="{th["pop"]}" font-weight="700">$ </tspan><tspan fill="#ECE9E2" font-weight="600">whoami</tspan></text>'
            + f'<text x="48" y="124" font-family="{FONT_MONO}" font-size="15.5" fill="#D4D4D8">{escape(W["roleLine"])}</text>'
            + f'<text x="48" y="150" font-family="{FONT_MONO}" font-size="15" fill="#A1A1AA">{escape(W["bioLine"])}</text>'
            + f'<text x="48" y="192" font-family="{FONT_MONO}" font-size="16"><tspan fill="{th["pop"]}" font-weight="700">$ </tspan><tspan fill="#ECE9E2" font-weight="600">cat now.txt</tspan></text>'
        )
        for i, item in enumerate(now_items):
            body += (
                f'<text x="48" y="{220 + i * 26}" font-family="{FONT_MONO}" font-size="15">'
                f'<tspan fill="{th["go"]}">→ </tspan><tspan fill="#D4D4D8">{escape(item)}</tspan></text>'
            )
        body += (
            f'<text x="48" y="304" font-family="{FONT_MONO}" font-size="16" fill="{th["pop"]}" font-weight="700">$ </text>'
            f'<rect x="70" y="290" width="9" height="17" rx="1" fill="#ECE9E2" class="cur"/>'
        )
        defs = "<style>@keyframes blink{50%{opacity:0}}.cur{animation:blink 1.1s steps(1) infinite}</style>"
        aria = f'whoami: {W["roleLine"]}. {W["bioLine"]} Now: {"; ".join(now_items)}'
        return svg_wrap(w, h, aria, theme, body, defs)

    # Phone variant
    w, h = 400, 344
    win_x, win_y, win_w, win_h = 16, 16, w - 32, h - 34
    bio_lines = wrap_lines(W["bioLine"], 40, 2)
    body = (
        sticker_rect(win_x, win_y, win_w, win_h, 12, th["screen"], th, 3)
        + f'<line x1="{win_x}" y1="{win_y + 32}" x2="{win_x + win_w}" y2="{win_y + 32}" stroke="{th["border"]}" stroke-width="1.8"/>'
        + f'<circle cx="{win_x + 18}" cy="{win_y + 16}" r="4.5" fill="{th["pop"]}"/>'
        + f'<circle cx="{win_x + 33}" cy="{win_y + 16}" r="4.5" fill="#F59E0B"/>'
        + f'<circle cx="{win_x + 48}" cy="{win_y + 16}" r="4.5" fill="{th["go"]}"/>'
        + f'<text x="{w / 2:.1f}" y="{win_y + 21}" font-family="{FONT_MONO}" font-size="11.5" fill="#A1A1AA" text-anchor="middle">{escape(P["terminalHost"])}: ~</text>'
        + f'<text x="30" y="76" font-family="{FONT_MONO}" font-size="13"><tspan fill="{th["pop"]}" font-weight="700">$ </tspan><tspan fill="#ECE9E2">whoami</tspan></text>'
        + f'<text x="30" y="98" font-family="{FONT_MONO}" font-size="12" fill="#ECE9E2">{escape(P["name"].lower())} · {escape(P["city"])}</text>'
    )
    for i, line in enumerate(bio_lines):
        body += f'<text x="30" y="{118 + i * 18}" font-family="{FONT_MONO}" font-size="11.5" fill="#A1A1AA">{escape(line)}</text>'
    body += f'<text x="30" y="168" font-family="{FONT_MONO}" font-size="13"><tspan fill="{th["pop"]}" font-weight="700">$ </tspan><tspan fill="#ECE9E2">cat now.txt</tspan></text>'
    ny = 190
    for item in now_items:
        for li, line in enumerate(wrap_lines(item, 38, 2)):
            prefix = "→ " if li == 0 else "  "
            body += (
                f'<text x="30" y="{ny}" font-family="{FONT_MONO}" font-size="11.5">'
                f'<tspan fill="{th["go"]}">{prefix}</tspan><tspan fill="#D4D4D8">{escape(line)}</tspan></text>'
            )
            ny += 18
        ny += 4
    aria = f'whoami: {W["roleLine"]}. {W["bioLine"]}'
    return svg_wrap(w, h, aria, theme, body)


def draw_label(theme: str, title: str, right_text: str, tone: str, phone: bool = False) -> str:
    th = THEMES[theme]
    w = 400 if phone else 880
    h = 56 if phone else 66
    fill = th["tones"].get(tone, th["card"])
    body = (
        sticker_rect(2, 2, w - 8, h - 8, 16, fill, th, 4)
        + f'<circle cx="{24 if phone else 30}" cy="{h / 2 - 2:.1f}" r="6" fill="{th["pop"]}" stroke="{th["border"]}" stroke-width="1.6"/>'
        + f'<text x="{42 if phone else 50}" y="{h / 2 + 5:.1f}" font-family="{FONT_DISPLAY}" font-weight="900" '
        f'font-size="{20 if phone else 25}" fill="{th["text"]}">{escape(title)}</text>'
        + f'<text x="{w - 22}" y="{h / 2 + 3:.1f}" font-family="{FONT_MONO}" font-size="{11 if phone else 13}" '
        f'fill="{th["muted"]}" text-anchor="end">{escape(right_text)}</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(title, quote=True)}"><title>{escape(title)}</title>{body}</svg>'
    )


def draw_app_card(theme: str, app: dict, phone: bool = False) -> str:
    th = THEMES[theme]
    w = 400 if phone else 440
    h = 264 if phone else 304
    card_fill = th["tones"].get(app["tone"], th["card"])
    icon_uri = file_b64_uri(os.path.join(ICONS_DIR, app["icon"]))

    badge_fill = th["go"] if app["badgeTone"] == "green" else th["pop"]
    badge_text_color = th["on_go"] if app["badgeTone"] == "green" else th["on_pop"]
    bw = max(84, int(len(app["badge"]) * 7.8 + 22))

    ix, iy, isize = (26, 28, 58) if phone else (36, 40, 72)
    tx = ix + isize + 16
    defs = f'<clipPath id="ic_{app["id"]}"><rect x="{ix}" y="{iy}" width="{isize}" height="{isize}" rx="14"/></clipPath>'
    desc_lines = wrap_lines(app["description"], 34 if not phone else 33, 2)

    tags_svg = []
    px = 26 if phone else 36
    py = 178 if phone else 202
    for tag in app["tags"][:3]:
        tw = max(62, int(len(tag) * 7.6 + 20))
        tags_svg.append(
            f'<rect x="{px}" y="{py}" width="{tw}" height="25" rx="6" fill="{th["card"]}" stroke="{th["border"]}" stroke-width="1.5"/>'
            f'<text x="{px + tw / 2:.1f}" y="{py + 16.5}" font-family="{FONT_MONO}" font-size="12" font-weight="600" '
            f'fill="{th["text"]}" text-anchor="middle">{escape(tag)}</text>'
        )
        px += tw + 8

    arrow_x = w - (46 if phone else 58)
    arrow_y = 26 if phone else 30
    body = (
        sticker_rect(14, 14, w - 32, h - 32, 18, card_fill, th, 4)
        + f'<image x="{ix}" y="{iy}" width="{isize}" height="{isize}" href="{icon_uri}" clip-path="url(#ic_{app["id"]})" preserveAspectRatio="xMidYMid slice"/>'
        + f'<rect x="{ix}" y="{iy}" width="{isize}" height="{isize}" rx="14" fill="none" stroke="{th["border"]}" stroke-width="2"/>'
        + f'<text x="{tx}" y="{iy + (30 if phone else 38)}" font-family="{FONT_DISPLAY}" font-weight="900" font-size="{23 if phone else 27}" fill="{th["text"]}">{escape(app["name"])}</text>'
        + f'<rect x="{tx}" y="{iy + (40 if phone else 50)}" width="{bw}" height="22" rx="11" fill="{badge_fill}" stroke="{th["border"]}" stroke-width="1.5"/>'
        + f'<text x="{tx + bw / 2:.1f}" y="{iy + (55 if phone else 65)}" font-family="{FONT_MONO}" font-weight="700" font-size="11.5" fill="{badge_text_color}" text-anchor="middle">{escape(app["badge"])}</text>'
        + sticker_rect(arrow_x, arrow_y, 26, 26, 7, th["pop"], th, 2)
        + f'<path d="M{arrow_x + 8} {arrow_y + 18} L{arrow_x + 18} {arrow_y + 8} M{arrow_x + 10} {arrow_y + 8} H{arrow_x + 18} V{arrow_y + 16}" '
        f'stroke="{th["on_pop"]}" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        + "".join(
            f'<text x="{26 if phone else 36}" y="{(128 if phone else 148) + i * 23}" font-family="{FONT_DISPLAY}" font-weight="500" '
            f'font-size="{16 if phone else 18}" fill="{th["text"]}">{escape(line)}</text>'
            for i, line in enumerate(desc_lines)
        )
        + "".join(tags_svg)
        + f'<text x="{26 if phone else 36}" y="{h - (30 if phone else 38)}" font-family="{FONT_MONO}" font-size="13.5" fill="{th["muted"]}">{escape(app["fact"])}</text>'
    )
    aria = f'{app["name"]}: {app["description"]} {app["badge"]}, {app["fact"]}'
    return svg_wrap(w, h, aria, theme, body, defs)


def draw_video_card(theme: str, video: dict, phone: bool = False) -> str:
    th = THEMES[theme]
    w = 400 if phone else 292
    h = 264 if phone else 290
    pad = 22 if phone else 24
    tw = w - pad * 2
    th_img = int(tw * 9 / 16)
    defs = f'<clipPath id="vc_{video["id"]}"><rect x="{pad}" y="{pad}" width="{tw}" height="{th_img}" rx="10"/></clipPath>'

    title_lines = wrap_lines(video["title"], 32 if phone else 24, 2)
    thumb = video.get("thumb_b64", "")
    img_el = (
        f'<image x="{pad}" y="{pad}" width="{tw}" height="{th_img}" href="{thumb}" clip-path="url(#vc_{video["id"]})" preserveAspectRatio="xMidYMid slice"/>'
        if thumb
        else f'<rect x="{pad}" y="{pad}" width="{tw}" height="{th_img}" rx="10" fill="{th["screen"]}"/>'
    )

    play_x = pad + tw - 24
    play_y = pad + th_img - 22
    ty = pad + th_img + 26
    date_label = f"{fmt_date_short(video.get('date'))}  ·  YouTube".strip(" ·")

    body = (
        sticker_rect(12, 12, w - 28, h - 28, 16, th["card"], th, 4)
        + img_el
        + f'<rect x="{pad}" y="{pad}" width="{tw}" height="{th_img}" rx="10" fill="none" stroke="{th["border"]}" stroke-width="2"/>'
        + f'<circle cx="{play_x + 2}" cy="{play_y + 2}" r="15" fill="{th["shadow"]}"/>'
        + f'<circle cx="{play_x}" cy="{play_y}" r="15" fill="{th["pop"]}" stroke="{th["border"]}" stroke-width="2"/>'
        + f'<path d="M{play_x - 4} {play_y - 6} L{play_x + 7} {play_y} L{play_x - 4} {play_y + 6} Z" fill="{th["on_pop"]}"/>'
        + "".join(
            f'<text x="{pad}" y="{ty + i * 22}" font-family="{FONT_DISPLAY}" font-weight="700" font-size="{16.5 if phone else 16}" fill="{th["text"]}">{escape(line)}</text>'
            for i, line in enumerate(title_lines)
        )
        + f'<text x="{pad}" y="{h - 28}" font-family="{FONT_MONO}" font-size="12.5" fill="{th["muted"]}">{escape(date_label)}</text>'
    )
    return svg_wrap(w, h, video["title"], theme, body, defs)


def picture(name: str, width: str, alt: str, phone: bool = False) -> str:
    a = f"assets/{name}"
    srcs = []
    if phone:
        srcs.append(f'<source media="(prefers-color-scheme: dark) and (max-width: 600px)" srcset="{a}-phone-dark.svg">')
        srcs.append(f'<source media="(max-width: 600px)" srcset="{a}-phone-light.svg">')
    srcs.append(f'<source media="(prefers-color-scheme: dark)" srcset="{a}-dark.svg">')
    attr = f'height="{width[1:]}"' if width.startswith("h") else f'width="{width}"'
    return f'<picture>{"".join(srcs)}<img src="{a}-light.svg" {attr} alt="{escape(alt, quote=True)}"></picture>'


def link(url: str, inner: str) -> str:
    return f'<a href="{url}">{inner}</a>'


def render_readme(data: dict, P: dict, graph_meta: list[tuple[str, str | None, int, str]], spark_total: int, board_aria: str) -> str:
    L = P["links"]
    out = [link(L["site"]["url"], picture("hero", "100%", f'{P["heroHeadline"]}. {P["heroSubtitle"]}', True)), ""]

    badges = []
    for key, name in (("youtube", "yt"), ("x", "x"), ("linkedin", "li"), ("site", "site")):
        alt = f"{L[key]['label']} {L[key]['handle']}".strip()
        badges.append(link(L[key]["url"], picture(f"badge-{name}", "h44", alt)))
    out += ['<p align="center">', *badges, "</p>", ""]

    out += [picture("github", "100%", board_aria, True), ""]

    for key, summary, total, title in graph_meta:
        pic = picture(f"graph-{key}", "100%", title, True)
        if summary is None:
            out += [pic, ""]
        else:
            unit = "contribution" if total == 1 else "contributions"
            out += [f"<details><summary>{summary}: {fmt_num(total)} {unit}</summary>", "", pic, "", "</details>", ""]

    out += [picture("line-30d", "100%", f"{fmt_num(spark_total)} contributions in the last 30 days", True), ""]
    out += [picture("whoami", "100%", f'whoami: {P["whoami"]["roleLine"]}', True), ""]
    out += [picture("label-ship", "100%", "What I ship", True), ""]

    apps_html = [
        link(a["url"], picture(f"app-{a['id']}", "49%", f"{a['name']}: {a['description']}", True))
        for a in P["apps"]
    ]
    out += ['<p align="center">', *apps_html, "</p>", ""]

    oss_links = " · ".join(link(o["url"], o["name"]) for o in P["ossLinks"])
    more_links = " · ".join(link(m["url"], m["name"]) for m in P["moreShips"])
    out += [f'<p align="center"><sub>Open Source (NSoC): {oss_links} · more ships: {more_links}</sub></p>', ""]

    out += [picture("label-videos", "100%", "Latest videos", True), ""]
    vids_html = [
        link(f"https://www.youtube.com/watch?v={v['id']}", picture(f"video-{v['id']}", "32%", v["title"], True))
        for v in data["videos"]
    ]
    out += ['<p align="center">', *vids_html, "</p>", ""]

    out += [
        f'<p align="center"><sub>Drawn in Swar\'s Portfolio V4 design system · numbers and videos redrawn every night by a GitHub Action · {link(L["site"]["url"], P["siteDomain"])}</sub></p>',
        "",
    ]
    return "\n".join(out)


def main(offline: bool = False) -> None:
    P = load_json(PROFILE_PATH)
    state = load_json(STATE_PATH, default={})
    today = date.fromisoformat(state["today"]) if (offline and state.get("today")) else datetime.now(timezone.utc).date()

    if offline and state.get("contrib"):
        gh = {"contrib": state["contrib"], "repos": state["repos"]}
        videos = state.get("videos", P["fallbackVideos"])
    else:
        gh = fetch_github_data(P["user"], today, state)
        videos = fetch_youtube_videos(P["links"]["youtube"]["channelId"], P["fallbackVideos"], state.get("videos", []))

    data = {"today": today.isoformat(), "contrib": gh["contrib"], "repos": gh["repos"], "videos": videos}
    save_json(STATE_PATH, data)

    days = data["contrib"].get("days", [])
    since_year = int(data["contrib"].get("since_year", today.year))
    ranges = [
        ("6m", None, today - timedelta(days=182), today, "in the last 6 months"),
        ("12m", "Last 12 months", today - timedelta(days=364), today, "in the last 12 months"),
    ]
    for y in range(today.year, since_year - 1, -1):
        y_end = today if y == today.year else date(y, 12, 31)
        ranges.append((str(y), str(y), date(y, 1, 1), y_end, f"in {y}"))

    files: dict[str, str] = {}
    graph_meta: list[tuple[str, str | None, int, str]] = []
    board_aria = ""
    spark_total = 0

    for theme in ("light", "dark"):
        files[f"hero-{theme}.svg"] = draw_hero(theme, P, phone=False)
        files[f"hero-phone-{theme}.svg"] = draw_hero(theme, P, phone=True)

        for key, name in (("youtube", "yt"), ("x", "x"), ("linkedin", "li"), ("site", "site")):
            L = P["links"][key]
            files[f"badge-{name}-{theme}.svg"] = draw_badge(theme, L["label"], L["handle"], key)

        board_svg, board_aria = draw_github_board(theme, data, P, phone=False)
        files[f"github-{theme}.svg"] = board_svg
        files[f"github-phone-{theme}.svg"] = draw_github_board(theme, data, P, phone=True)[0]

        for rkey, summary, rstart, r_end, suffix in ranges:
            g_svg, total = draw_heatmap(theme, days, rstart, r_end, suffix, phone=False)
            g_phone, _ = draw_heatmap(theme, days, rstart, r_end, suffix, phone=True)
            files[f"graph-{rkey}-{theme}.svg"] = g_svg
            files[f"graph-{rkey}-phone-{theme}.svg"] = g_phone
            if theme == "light":
                graph_meta.append((rkey, summary, total, f"{fmt_num(total)} contributions {suffix}"))

        sp_svg, spark_total = draw_sparkline_30d(theme, days, today, phone=False)
        files[f"line-30d-{theme}.svg"] = sp_svg
        files[f"line-30d-phone-{theme}.svg"] = draw_sparkline_30d(theme, days, today, phone=True)[0]

        files[f"whoami-{theme}.svg"] = draw_whoami(theme, P, phone=False)
        files[f"whoami-phone-{theme}.svg"] = draw_whoami(theme, P, phone=True)

        files[f"label-ship-{theme}.svg"] = draw_label(theme, "What I ship", f"{len(P['apps'])} flagship builds", "amber", phone=False)
        files[f"label-ship-phone-{theme}.svg"] = draw_label(theme, "What I ship", f"{len(P['apps'])} builds", "amber", phone=True)
        files[f"label-videos-{theme}.svg"] = draw_label(theme, "Latest videos", f"YouTube {P['links']['youtube']['handle']}", "red", phone=False)
        files[f"label-videos-phone-{theme}.svg"] = draw_label(theme, "Latest videos", P["links"]["youtube"]["handle"], "red", phone=True)

        for app in P["apps"]:
            files[f"app-{app['id']}-{theme}.svg"] = draw_app_card(theme, app, phone=False)
            files[f"app-{app['id']}-phone-{theme}.svg"] = draw_app_card(theme, app, phone=True)

        for v in videos:
            files[f"video-{v['id']}-{theme}.svg"] = draw_video_card(theme, v, phone=False)
            files[f"video-{v['id']}-phone-{theme}.svg"] = draw_video_card(theme, v, phone=True)

    os.makedirs(ASSETS_DIR, exist_ok=True)
    for old in os.listdir(ASSETS_DIR):
        if old.endswith(".svg") and old not in files:
            os.remove(os.path.join(ASSETS_DIR, old))
    for name, content in files.items():
        with open(os.path.join(ASSETS_DIR, name), "w", encoding="utf8", newline="\n") as f:
            f.write(content)

    readme_text = render_readme(data, P, graph_meta, spark_total, board_aria)
    with open(os.path.join(ROOT_DIR, "README.md"), "w", encoding="utf8", newline="\n") as f:
        f.write(readme_text.rstrip("\n") + "\n")

    print(f"Generated {len(files)} SVGs and README.md for {today.isoformat()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use cached scripts/state.json without network calls")
    args = parser.parse_args()
    main(offline=args.offline)
