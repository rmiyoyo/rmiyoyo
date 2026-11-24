#!/usr/bin/env python3
"""Generate the contribution and language cards shown on the profile README.

Reads the GitHub GraphQL API with the token in STATS_TOKEN (falling back to
GITHUB_TOKEN) and writes four SVG files to assets/:

    stats.svg, stats-dark.svg          total contributions, current and longest streak
    languages.svg, languages-dark.svg  most used languages across owned repositories

Only the standard library is used, so the workflow needs no install step.

Environment:
    STATS_TOKEN / GITHUB_TOKEN  token for the GraphQL API
    STATS_USER                  login to report on (default: GITHUB_REPOSITORY_OWNER)
    EXCLUDE_LANGS               comma-separated languages to leave out
    TOP_LANGS                   how many languages to list (default 7)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

API = "https://api.github.com/graphql"
OUT = Path(__file__).resolve().parent.parent / "assets"

DEFAULT_EXCLUDE = "HTML,CSS,SCSS,Less,Jupyter Notebook,Procfile,Makefile,Dockerfile"

def graphql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


CREATED_Q = "query($login: String!) { user(login: $login) { createdAt } }"

CALENDAR_Q = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

REPOS_Q = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        isArchived
        languages(first: 25, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch_days(token: str, login: str) -> dict[date, int]:
    """Daily contribution counts from account creation to today (one query per year)."""
    created = datetime.fromisoformat(
        graphql(token, CREATED_Q, {"login": login})["user"]["createdAt"].replace("Z", "+00:00")
    )
    now = datetime.now(timezone.utc)
    days: dict[date, int] = {}
    start = created
    while start < now:
        end = min(start + timedelta(days=365), now)
        data = graphql(
            token,
            CALENDAR_Q,
            {"login": login, "from": start.isoformat(), "to": end.isoformat()},
        )
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for d in week["contributionDays"]:
                days[date.fromisoformat(d["date"])] = d["contributionCount"]
        start = end
    return days


def fetch_languages(token: str, login: str) -> dict[str, tuple[int, str]]:
    """Bytes per language summed over every non-fork repository the user owns,
    leaving out the profile repository itself."""
    totals: dict[str, tuple[int, str]] = {}
    cursor = None
    while True:
        data = graphql(token, REPOS_Q, {"login": login, "cursor": cursor})
        repos = data["user"]["repositories"]
        for repo in repos["nodes"]:
            if repo["name"].lower() == login.lower():
                continue  # the profile repository only holds this script
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                color = edge["node"]["color"] or "#8b949e"
                size, _ = totals.get(name, (0, color))
                totals[name] = (size + edge["size"], color)
        if not repos["pageInfo"]["hasNextPage"]:
            return totals
        cursor = repos["pageInfo"]["endCursor"]

@dataclass
class Streak:
    length: int = 0
    start: date | None = None
    end: date | None = None


@dataclass
class Stats:
    total: int
    first_day: date
    current: Streak
    longest: Streak
    active_days: int


def compute_stats(days: dict[date, int], today: date) -> Stats:
    ordered = sorted(d for d in days if d <= today)
    longest = Streak()
    run = Streak()
    for d in ordered:
        if days[d] > 0:
            if run.length and run.end == d - timedelta(days=1):
                run = Streak(run.length + 1, run.start, d)
            else:
                run = Streak(1, d, d)
            if run.length > longest.length:
                longest = run

    current = Streak()
    cursor = today if days.get(today, 0) > 0 else today - timedelta(days=1)
    while days.get(cursor, 0) > 0:
        current = Streak(current.length + 1, cursor, current.end or cursor)
        cursor -= timedelta(days=1)

    first_active = next((d for d in ordered if days[d] > 0), ordered[0] if ordered else today)
    return Stats(
        total=sum(days[d] for d in ordered),
        first_day=first_active,
        current=current,
        longest=longest,
        active_days=sum(1 for d in ordered if days[d] > 0),
    )

def top_languages(totals: dict[str, tuple[int, str]], exclude: set[str], limit: int):
    kept = {k: v for k, v in totals.items() if k.lower() not in exclude}
    grand = sum(size for size, _ in kept.values()) or 1
    ranked = sorted(kept.items(), key=lambda kv: kv[1][0], reverse=True)
    top = [(name, size / grand, color) for name, (size, color) in ranked[:limit]]
    rest = sum(size for _, (size, _) in ranked[limit:])
    if rest:
        top.append(("Other", rest / grand, "#8b949e"))
    return top

THEMES = {
    "light": {"bg": "#ffffff", "border": "#d0d7de", "fg": "#1f2328", "muted": "#59636e",
              "accent": "#0969da", "track": "#eaeef2", "rule": "#d8dee4"},
    "dark": {"bg": "#0d1117", "border": "#30363d", "fg": "#e6edf3", "muted": "#9198a1",
             "accent": "#4493f8", "track": "#21262d", "rule": "#30363d"},
}

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
W, H = 420, 180


def _frame(t: dict, title: str, body: str, label: str, h: int = H) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(label)}">
<title>{escape(label)}</title>
<style>
  text {{ font-family: {FONT}; fill: {t['fg']}; }}
  .title {{ font-size: 14px; font-weight: 600; }}
  .big {{ font-size: 26px; font-weight: 600; }}
  .label {{ font-size: 12px; fill: {t['muted']}; }}
  .small {{ font-size: 11px; fill: {t['muted']}; }}
  .lang {{ font-size: 12px; }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="6" fill="{t['bg']}" stroke="{t['border']}"/>
<text class="title" x="20" y="30">{escape(title)}</text>
{body}
</svg>
"""


def _fmt_date(d: date | None, with_year: bool = True) -> str:
    if d is None:
        return ""
    return d.strftime("%-d %b %Y" if with_year else "%-d %b")


def _span(s: Streak) -> str:
    if not s.length:
        return "No active streak"
    if s.start == s.end:
        return _fmt_date(s.start)
    same_year = s.start.year == s.end.year
    return f"{_fmt_date(s.start, not same_year)} – {_fmt_date(s.end)}"


def render_stats(stats: Stats, t: dict) -> str:
    cols = [
        (f"{stats.total:,}", "Contributions", f"Since {_fmt_date(stats.first_day)}"),
        (f"{stats.current.length:,}", "Current streak", _span(stats.current)),
        (f"{stats.longest.length:,}", "Longest streak", _span(stats.longest)),
    ]
    col_w = (W - 40) / 3
    parts = []
    for i, (value, label, sub) in enumerate(cols):
        x = 20 + i * col_w
        if i:
            parts.append(f'<line x1="{x - 8:.1f}" y1="66" x2="{x - 8:.1f}" y2="154" stroke="{t["rule"]}"/>')
        fill = f' style="fill:{t["accent"]}"' if i == 1 else ""
        parts.append(f'<text class="big" x="{x:.1f}" y="102"{fill}>{escape(value)}</text>')
        parts.append(f'<text class="label" x="{x:.1f}" y="124">{escape(label)}</text>')
        parts.append(f'<text class="small" x="{x:.1f}" y="144">{escape(sub)}</text>')
    parts.append(
        f'<text class="small" x="{W - 20}" y="30" text-anchor="end">'
        f'{stats.active_days:,} active days</text>'
    )
    label = (f"{stats.total} contributions, current streak {stats.current.length} days, "
             f"longest streak {stats.longest.length} days")
    return _frame(t, "Contributions", "\n".join(parts), label)


def render_languages(langs: list[tuple[str, float, str]], t: dict) -> str:
    bar_x, bar_y, bar_w, bar_h = 20, 48, W - 40, 8
    parts = [f'<clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="4"/></clipPath>',
             f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="4" fill="{t["track"]}"/>',
             '<g clip-path="url(#bar)">']
    x = float(bar_x)
    for _, share, color in langs:
        w = share * bar_w
        parts.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w + 0.5:.2f}" height="{bar_h}" fill="{color}"/>')
        x += w
    parts.append("</g>")

    rows = (len(langs) + 1) // 2
    col_w = (W - 40) / 2
    for i, (name, share, color) in enumerate(langs):
        col, row = divmod(i, rows) if rows else (0, 0)
        cx = 20 + col * col_w
        cy = 80 + row * 22
        parts.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{color}"/>')
        parts.append(f'<text class="lang" x="{cx + 16}" y="{cy}">{escape(name)}</text>')
        parts.append(f'<text class="small" x="{cx + col_w - 16}" y="{cy}" text-anchor="end">{share * 100:.1f}%</text>')
    parts.append(f'<text class="small" x="{W - 20}" y="30" text-anchor="end">by code size, all owned repositories</text>')
    label = "Most used languages: " + ", ".join(f"{n} {s * 100:.0f}%" for n, s, _ in langs)
    height = max(H, 80 + rows * 22 + 12)
    return _frame(t, "Languages", "\n".join(parts), label, height)


def write_cards(stats: Stats, langs: list[tuple[str, float, str]], out: Path = OUT) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        (out / f"stats{suffix}.svg").write_text(render_stats(stats, THEMES[theme]))
        (out / f"languages{suffix}.svg").write_text(render_languages(langs, THEMES[theme]))


# -------------------------------------------------------------------------- main


def main() -> int:
    # Secrets pasted into the GitHub UI often carry a trailing newline.
    token = (os.environ.get("STATS_TOKEN") or "").strip() or (os.environ.get("GITHUB_TOKEN") or "").strip()
    login = os.environ.get("STATS_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER")
    if not token or not login:
        print("Set STATS_TOKEN (or GITHUB_TOKEN) and STATS_USER.", file=sys.stderr)
        return 1
    exclude = {s.strip().lower() for s in os.environ.get("EXCLUDE_LANGS", DEFAULT_EXCLUDE).split(",") if s.strip()}
    limit = int(os.environ.get("TOP_LANGS", "7"))

    today = datetime.now(timezone.utc).date()
    stats = compute_stats(fetch_days(token, login), today)
    langs = top_languages(fetch_languages(token, login), exclude, limit)
    write_cards(stats, langs)
    print(f"{login}: {stats.total} contributions, current streak {stats.current.length}, "
          f"longest {stats.longest.length}; {len(langs)} languages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
