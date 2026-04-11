#!/usr/bin/env python3
"""
Inject the floating back button (.zk-back), scroll-to-top button (.zk-top),
and Telegram WebApp init script into any wiki review HTML file that does
not already have them.

Target: wiki/kz/*.html and wiki/ru/*.html

Usage:
    python scripts/wiki_inject.py            # fix all wiki files
    python scripts/wiki_inject.py --check    # exit 1 if any file needs fixing

This is run automatically by .github/workflows/wiki-inject.yml on push,
so authors can upload a new review HTML via the GitHub web UI and the
back button / Mini App init will be added in a follow-up commit.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIRS = [REPO_ROOT / "wiki" / "kz", REPO_ROOT / "wiki" / "ru"]

MARKER = 'class="zk-back"'

ZK_CSS = """.zk-back{position:fixed;top:max(env(safe-area-inset-top,0px),60px);left:50%;transform:translateX(-50%);z-index:9999;display:inline-flex;align-items:center;gap:6px;padding:10px 16px;background:rgba(6,6,12,0.92);color:#fff;border:1px solid rgba(255,255,255,0.15);border-radius:22px;font-family:-apple-system,'Source Sans 3',sans-serif;font-size:13px;font-weight:700;text-decoration:none;cursor:pointer;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);box-shadow:0 4px 16px rgba(0,0,0,0.3)}
.zk-back:active{transform:translateX(-50%) scale(0.95)}
.zk-back svg{width:14px;height:14px}
.zk-top{position:fixed;bottom:28px;right:20px;z-index:9998;width:52px;height:52px;border-radius:50%;background:#1a1a1a;color:#fff;border:none;display:none;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,0.4);opacity:0;transition:opacity .3s,transform .2s}
.zk-top.on{display:flex;opacity:1}
.zk-top:active{transform:scale(0.92)}
.zk-top svg{width:20px;height:20px}
"""

ZK_HTML = """<a class="zk-back" href="../../products/index.html?tab=niches" onclick="if(window.Telegram&&window.Telegram.WebApp){event.preventDefault();window.location.href=this.href}">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"/></svg>
  Назад
</a>
<button class="zk-top" id="zkTop" onclick="smoothScrollTop()">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="18 15 12 9 6 15"/></svg>
</button>
<script>
function smoothScrollTop(){var start=window.pageYOffset;var startTime=null;var duration=900;function ease(t){return 1-Math.pow(1-t,3)}function step(now){if(!startTime)startTime=now;var progress=Math.min((now-startTime)/duration,1);window.scrollTo(0,start*(1-ease(progress)));if(progress<1)requestAnimationFrame(step)}requestAnimationFrame(step)}
window.addEventListener('scroll',function(){var t=document.getElementById('zkTop');if(!t)return;if(window.scrollY>400){t.classList.add('on')}else{t.classList.remove('on')}});
try{if(window.Telegram&&window.Telegram.WebApp){var tg=window.Telegram.WebApp;tg.ready&&tg.ready();tg.expand&&tg.expand()}}catch(e){}
</script>
"""


def needs_injection(text: str) -> bool:
    return MARKER not in text


def inject(text: str) -> str:
    # 1. Insert CSS right before the first </style>
    close_style = text.find("</style>")
    if close_style == -1:
        raise ValueError("no </style> tag found")
    text = text[:close_style] + ZK_CSS + text[close_style:]

    # 2. Insert HTML block right after the first <body...> tag
    body_open = text.find("<body")
    if body_open == -1:
        raise ValueError("no <body> tag found")
    body_close = text.find(">", body_open)
    if body_close == -1:
        raise ValueError("malformed <body> tag")
    insert_at = body_close + 1
    # keep a newline after <body>
    prefix = "\n" if not text[insert_at:insert_at + 1] == "\n" else ""
    text = text[:insert_at] + prefix + ZK_HTML + text[insert_at:]
    return text


def iter_wiki_files():
    for d in WIKI_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.html")):
            yield p


def main() -> int:
    check_only = "--check" in sys.argv
    changed: list[Path] = []

    for path in iter_wiki_files():
        text = path.read_text(encoding="utf-8")
        if not needs_injection(text):
            continue
        if check_only:
            changed.append(path)
            continue
        try:
            new_text = inject(text)
        except ValueError as exc:
            print(f"skip {path.name}: {exc}", file=sys.stderr)
            continue
        path.write_text(new_text, encoding="utf-8")
        changed.append(path)
        print(f"injected: {path.relative_to(REPO_ROOT)}")

    if check_only and changed:
        for p in changed:
            print(f"needs injection: {p.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    if not changed:
        print("all wiki files already have .zk-back block")
    return 0


if __name__ == "__main__":
    sys.exit(main())
