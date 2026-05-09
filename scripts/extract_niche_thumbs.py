#!/usr/bin/env python3
"""
Извлекает hero-base64 из обзоров wiki/kz/ZEREK_*.html и сохраняет
как products/_assets/niches/{slug}.jpg, затем подменяет эмодзи-fallback
в карусели products/app.html на <img>.

Парсит карусель сама — реестра не требует.
Slug = нижний регистр wiki-ключа без префикса ZEREK_.
"""
from __future__ import annotations
import re
import base64
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_HTML = REPO / 'products' / 'app.html'
WIKI_DIR = REPO / 'wiki' / 'kz'
ASSETS_DIR = REPO / 'products' / '_assets' / 'niches'
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Карточки на эмодзи-fallback:
#   <article class="hero-card" onclick="openWiki('ZEREK_X')">
#     <div class="hero-cover cv-niche"><span class="hero-emoji">EMOJI</span></div>
#     <div class="hero-body">
#       <h3 class="hero-title">TITLE</h3>
#       ...
CARD_RX = re.compile(
    r"""(<article\ class="hero-card"\ onclick="openWiki\('(ZEREK_[A-Za-z]+)'\)">\s*
        <div\ class="hero-cover\ cv-niche"><span\ class="hero-emoji">[^<]+</span></div>\s*
        <div\ class="hero-body">\s*
        <h3\ class="hero-title">([^<]+)</h3>)""",
    re.VERBOSE,
)

# base64 hero в CSS обзора: background:url(data:image/jpeg;base64,...)
# Кавычки опциональные, тип image/* любой, но берём только первый match (hero).
HERO_RX = re.compile(
    r"""background:url\(\s*['"]?(data:image/(jpe?g|png|webp);base64,[A-Za-z0-9+/=\s]+?)['"]?\s*\)""",
    re.IGNORECASE,
)


def extract_hero_b64(html: str) -> tuple[bytes, str] | None:
    m = HERO_RX.search(html)
    if not m:
        return None
    data_url, mime = m.group(1), m.group(2).lower()
    _, b64 = data_url.split(',', 1)
    b64 = re.sub(r'\s+', '', b64)
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception:
        return None
    ext = {'jpeg': 'jpg', 'jpg': 'jpg', 'png': 'png', 'webp': 'webp'}.get(mime, 'jpg')
    return raw, ext


def asset_exists(slug: str) -> str | None:
    for ext in ('jpg', 'jpeg', 'png', 'webp'):
        p = ASSETS_DIR / f'{slug}.{ext}'
        if p.exists():
            return p.name
    return None


def replace_card(match: re.Match, slug: str, asset_name: str, title: str) -> str:
    head = match.group(1)
    new_cover = (
        f'<div class="hero-cover"><img src="_assets/niches/{asset_name}" '
        f'alt="{title}" loading="lazy"></div>'
    )
    return re.sub(
        r'<div\ class="hero-cover\ cv-niche"><span\ class="hero-emoji">[^<]+</span></div>',
        new_cover,
        head,
        count=1,
    )


def main() -> int:
    app_html = APP_HTML.read_text(encoding='utf-8')
    cards = list(CARD_RX.finditer(app_html))
    if not cards:
        print('cv-niche карточек не найдено — нечего извлекать.')
        return 0

    print(f'Найдено карточек на эмодзи-fallback: {len(cards)}')
    extracted: list[str] = []
    reused: list[str] = []
    no_wiki: list[str] = []
    no_hero: list[str] = []

    # patch заявок: replacements: list[(start, end, new_text)]
    replacements: list[tuple[int, int, str]] = []

    for m in cards:
        wiki_key = m.group(2)              # ZEREK_Autoservice
        title = m.group(3).strip()         # «Автосервис»
        slug = wiki_key.removeprefix('ZEREK_').lower()
        wiki_file = WIKI_DIR / f'{wiki_key}.html'

        # 1) уже есть готовый ассет?
        existing = asset_exists(slug)
        if existing:
            reused.append(slug)
            new_card = replace_card(m, slug, existing, title)
            replacements.append((m.start(), m.end(), new_card))
            continue

        # 2) есть wiki-обзор?
        if not wiki_file.exists():
            no_wiki.append(slug)
            continue

        # 3) есть base64 hero?
        wiki_html = wiki_file.read_text(encoding='utf-8')
        result = extract_hero_b64(wiki_html)
        if result is None:
            no_hero.append(slug)
            continue

        raw, ext = result
        out_path = ASSETS_DIR / f'{slug}.{ext}'
        out_path.write_bytes(raw)
        extracted.append(f'{slug}.{ext} ({len(raw) // 1024} KiB)')
        new_card = replace_card(m, slug, out_path.name, title)
        replacements.append((m.start(), m.end(), new_card))

    # применяем замены с конца, чтобы offsets не поплыли
    if replacements:
        chunks = []
        cursor = 0
        for start, end, new_text in sorted(replacements, key=lambda x: x[0]):
            chunks.append(app_html[cursor:start])
            chunks.append(new_text)
            cursor = end
        chunks.append(app_html[cursor:])
        APP_HTML.write_text(''.join(chunks), encoding='utf-8')

    print(f'\nИзвлечено новых: {len(extracted)}')
    for line in extracted:
        print(f'  ✓ {line}')
    if reused:
        print(f'\nПереиспользовано существующих: {len(reused)}')
        for s in reused:
            print(f'  ↺ {s}')
    if no_wiki:
        print(f'\nНет wiki-обзора: {len(no_wiki)}')
        for s in no_wiki:
            print(f'  ✗ {s}')
    if no_hero:
        print(f'\nНет base64 hero в обзоре: {len(no_hero)}')
        for s in no_hero:
            print(f'  ✗ {s}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
