#!/usr/bin/env python3
"""
Перезаписывает hero-фото в products/_assets/niches/*.{jpg,webp,png} для
карточек карусели products/app.html, у которых уже есть <img> (т.е. где
картинка уже стояла, но Адиль захотел освежить hero из обзора).

Берёт base64 background из wiki/kz/ZEREK_*.html, удаляет старый ассет,
сохраняет новый с расширением из base64. Если имя файла поменялось —
правит ссылку в HTML.

SKIP — карточки, которые НЕ трогаем.
"""
from __future__ import annotations
import re
import base64
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_HTML = REPO / 'products' / 'app.html'
WIKI_DIR = REPO / 'wiki' / 'kz'
ASSETS_DIR = REPO / 'products' / '_assets' / 'niches'

# wiki-ключи, у которых hero менять НЕ нужно
SKIP: set[str] = {
    'ZEREK_Coffee',       # кофейня
    'ZEREK_Confection',   # кондитерская
    'ZEREK_Doner',        # донерная (shaurma.jpg)
    'ZEREK_DryClean',     # химчистка
    'ZEREK_Epilation',    # эпиляция
    'ZEREK_Fastfood',     # фастфуд (burger.jpg)
    'ZEREK_Flowers',      # цветочный магазин
    'ZEREK_Fruitsvegs',   # фрукты и овощи (fruits.jpg)
    'ZEREK_Massage',      # массажный салон (spa.jpg)
    'ZEREK_Sushi',        # суши-бар
    'ZEREK_Semifood',     # магазин полуфабрикатов
    'ZEREK_BrowLash',     # бровист
    'ZEREK_Meatshop',     # мясная лавка (meat.jpg)
}

CARD_RX = re.compile(
    r"""(<article\ class="hero-card"\ onclick="openWiki\('(ZEREK_[A-Za-z]+)'\)">\s*
        <div\ class="hero-cover"><img\ src="_assets/niches/([^"]+)"\ alt="([^"]+)"\ loading="lazy"></div>)""",
    re.VERBOSE,
)

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


def main() -> int:
    html = APP_HTML.read_text(encoding='utf-8')
    cards = list(CARD_RX.finditer(html))
    print(f'Карточек с <img> в карусели: {len(cards)}')

    refreshed: list[str] = []
    renamed: list[str] = []
    skipped: list[str] = []
    no_wiki: list[str] = []
    no_hero: list[str] = []

    replacements: list[tuple[int, int, str]] = []

    for m in cards:
        wiki_key = m.group(2)              # ZEREK_Autoservice
        old_filename = m.group(3)          # autoservice.jpg
        title = m.group(4)
        slug = old_filename.rsplit('.', 1)[0]

        if wiki_key in SKIP:
            skipped.append(f'{wiki_key} ({old_filename})')
            continue

        wiki_file = WIKI_DIR / f'{wiki_key}.html'
        if not wiki_file.exists():
            no_wiki.append(wiki_key)
            continue

        wiki_html = wiki_file.read_text(encoding='utf-8')
        result = extract_hero_b64(wiki_html)
        if result is None:
            no_hero.append(wiki_key)
            continue

        raw, ext = result
        new_filename = f'{slug}.{ext}'
        old_path = ASSETS_DIR / old_filename
        new_path = ASSETS_DIR / new_filename

        # удаляем старый ассет (мог быть с другим расширением)
        if old_path.exists():
            old_path.unlink()
        new_path.write_bytes(raw)

        if old_filename != new_filename:
            renamed.append(f'{old_filename} → {new_filename}')
            new_card = m.group(1).replace(
                f'_assets/niches/{old_filename}',
                f'_assets/niches/{new_filename}',
                1,
            )
            replacements.append((m.start(), m.end(), new_card))

        refreshed.append(f'{new_filename} ({len(raw) // 1024} KiB)')

    if replacements:
        chunks = []
        cursor = 0
        for start, end, new_text in sorted(replacements, key=lambda x: x[0]):
            chunks.append(html[cursor:start])
            chunks.append(new_text)
            cursor = end
        chunks.append(html[cursor:])
        APP_HTML.write_text(''.join(chunks), encoding='utf-8')

    print(f'\nОбновлено: {len(refreshed)}')
    for line in refreshed:
        print(f'  ✓ {line}')
    if renamed:
        print(f'\nПереименовано (расширение поменялось): {len(renamed)}')
        for line in renamed:
            print(f'  ↻ {line}')
    if skipped:
        print(f'\nПропущено по SKIP-листу: {len(skipped)}')
        for s in skipped:
            print(f'  ◌ {s}')
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
