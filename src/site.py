"""Render Markdown pages into a small static site for GitHub Pages."""
from __future__ import annotations

import html
import os
import re
from pathlib import Path

import markdown

from . import config

CSS = """
:root {
  --paper: #F6F7F6;
  --surface: #FFFFFF;
  --ink: #15233B;
  --muted: #586374;
  --rule: #D8DDE4;
  --link: #1F4E8C;
  --expand: #1D6F6A;
  --contract: #A8631A;
  --serif: "Source Serif 4", Georgia, "Times New Roman", serif;
  --sans: "Public Sans", "Segoe UI", system-ui, -apple-system, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #0E1621; --surface: #142030; --ink: #E3E8EF; --muted: #9AA6B6;
    --rule: #2A3A4E; --link: #8DB7F0; --expand: #5FB8AF; --contract: #E0A15A;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: var(--serif); font-size: 1.0625rem; line-height: 1.68;
}
.wrap { max-width: 66rem; margin: 0 auto; padding: 0 1.25rem; }
.site-header { border-bottom: 1px solid var(--rule); }
.site-header .wrap {
  display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between;
  gap: .4rem 1.5rem; padding-top: 1.1rem; padding-bottom: 1rem;
}
.brand { color: var(--ink); text-decoration: none; font-weight: 600; font-size: 1.15rem; }
.brand small { display: block; font-family: var(--sans); font-weight: 400; font-size: .8rem; color: var(--muted); }
nav { font-family: var(--sans); font-size: .9rem; }
nav a { color: var(--muted); text-decoration: none; margin-right: 1.1rem; }
nav a:last-child { margin-right: 0; }
nav a:hover, nav a[aria-current="page"] { color: var(--ink); text-decoration: underline; text-underline-offset: 5px; }
main { padding-top: 2.25rem; padding-bottom: 4rem; }
main > * { max-width: 44rem; }
main > .table-wrap, main > p:has(> img), main > h2 { max-width: none; }
h1 { font-size: 2.05rem; line-height: 1.2; font-weight: 600; margin: 0 0 1.1rem; letter-spacing: -0.01em; }
h2 {
  font-size: 1.4rem; line-height: 1.3; font-weight: 600;
  margin: 3rem 0 .8rem; padding-top: 1.1rem; border-top: 1px solid var(--rule);
}
h3 { font-family: var(--sans); font-size: 1rem; font-weight: 600; margin: 2rem 0 .4rem; }
a { color: var(--link); text-underline-offset: 3px; }
a:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; border-radius: 2px; }
ul, ol { padding-left: 1.3rem; }
li + li { margin-top: .35rem; }
.regime {
  font-size: clamp(1.35rem, 2.6vw, 1.85rem); line-height: 1.32; font-weight: 500;
  margin: 0 0 .9rem; padding: .1rem 0 .1rem 1.1rem; border-left: 5px solid var(--muted);
  max-width: 40rem;
}
.regime.expanding { border-left-color: var(--expand); }
.regime.contracting { border-left-color: var(--contract); }
.regime-note { font-family: var(--sans); font-size: .92rem; color: var(--muted); margin-top: 0; }
.table-wrap { overflow-x: auto; margin: 1.1rem 0 1.6rem; border: 1px solid var(--rule); background: var(--surface); }
table { border-collapse: collapse; width: 100%; font-family: var(--sans); font-size: .84rem; font-variant-numeric: tabular-nums; }
th, td { padding: .5rem .8rem; border-bottom: 1px solid var(--rule); white-space: nowrap; }
th { font-weight: 600; vertical-align: bottom; }
th:first-child, td:first-child { position: sticky; left: 0; background: var(--surface); }
tbody tr:last-child td { border-bottom: none; }
img { display: block; max-width: 100%; height: auto; margin: 1.4rem 0; border: 1px solid var(--rule); background: #fff; }
blockquote { margin: 1.4rem 0; padding: .2rem 0 .2rem 1rem; border-left: 3px solid var(--rule); color: var(--muted); }
code { font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; font-size: .86em; }
.report-list p { margin: .2rem 0 1.2rem; }
.site-footer { border-top: 1px solid var(--rule); font-family: var(--sans); font-size: .82rem; color: var(--muted); }
.site-footer .wrap { padding-top: 1.2rem; padding-bottom: 2.2rem; }
.site-footer p { max-width: 44rem; margin: .3rem 0; }
@media (max-width: 40rem) {
  body { font-size: 1rem; }
  h1 { font-size: 1.7rem; }
}
"""

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{PAGE_TITLE}}</title>
<meta name="description" content="{{DESCRIPTION}}">
<meta name="author" content="{{AUTHOR}}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{{ROOT}}style.css">
</head>
<body>
<header class="site-header"><div class="wrap">
<a class="brand" href="{{ROOT}}index.html">{{SITE_TITLE}}<small>{{AUTHOR}}</small></a>
<nav aria-label="Primary">{{NAV}}</nav>
</div></header>
<main class="wrap">
{{BODY}}
</main>
<footer class="site-footer"><div class="wrap">
<p>{{FOOTER}}</p>
<p>For research and education only; not investment advice. Data from FRED (Federal Reserve Bank of St. Louis) and Yahoo Finance may contain errors or revisions.</p>
</div></footer>
</body>
</html>
"""


def repo_url() -> str | None:
    repo = os.environ.get("GITHUB_REPOSITORY")
    return f"https://github.com/{repo}" if repo else None


def _nav(root: str, current: str) -> str:
    items = [("Monitor", f"{root}index.html", "index"),
             ("Research", f"{root}index.html#research", "research"),
             ("About", f"{root}index.html#about", "about")]
    url = repo_url()
    if url:
        items.append(("Code", url, "code"))
    links = []
    for label, href, key in items:
        cur = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{href}"{cur}>{label}</a>')
    return "".join(links)


def render(md_text: str, page_title: str, root: str, current: str, footer: str) -> str:
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc", "attr_list"])
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    out = TEMPLATE
    for key, val in {
        "PAGE_TITLE": html.escape(page_title),
        "DESCRIPTION": html.escape(config.SITE_DESCRIPTION),
        "AUTHOR": html.escape(config.AUTHOR),
        "SITE_TITLE": html.escape(config.SITE_TITLE),
        "ROOT": root,
        "NAV": _nav(root, current),
        "BODY": body,
        "FOOTER": footer,
    }.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def strip_repo_only(md_text: str) -> str:
    return re.sub(r"<!-- REPO_ONLY -->.*?<!-- /REPO_ONLY -->\n?", "", md_text, flags=re.S)


def write_css(out_dir: Path) -> None:
    (out_dir / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
