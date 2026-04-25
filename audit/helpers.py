"""helpers.py · фундаментальные функции для правил.

`extract_block`, `find_context`, `extract_numbers_near`, `parse_number`,
`collect_all_engine_numbers` — без них правила не работают, поэтому всё
здесь.

Все функции устойчивы к мусору: если входной текст пустой/None, возвращают
пустые значения (не падают). Это важно потому что pdftotext иногда даёт
пустые страницы, а правила должны корректно их пропускать.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, List


_NUM_PAT = re.compile(r"\b\d{1,3}(?:[   ]\d{3})+|\b\d{2,3}\s*[KkКк]\b|\b\d+\b")


def find_context(text: str, phrase: str, window: int = 80) -> str:
    """Кусок текста вокруг найденной фразы. Возвращает '' если не нашли."""
    if not text or not phrase:
        return ""
    idx = text.lower().find(phrase.lower())
    if idx < 0:
        return ""
    lo = max(0, idx - window)
    hi = min(len(text), idx + len(phrase) + window)
    snippet = text[lo:hi].replace("\n", " ")
    return re.sub(r"\s+", " ", snippet).strip()


def extract_block(page_text: str, header: str, max_chars: int = 800) -> str:
    """Текст после заголовка `header` до следующего заголовка (h-style) либо
    `max_chars` символов. Использовать для блоков типа «Финансовая подушка»,
    «Достаточность капитала», «Частые ошибки».

    Эвристика для границ:
      · следующий заголовок-капс (3+ слова всеми строчными CAPS)
      · следующая «Маникюр · ...» строка-футер
      · следующая строка «Страница N из M»
      · max_chars

    Если заголовок не найден — '' (правило это распознаёт как «нет блока»).
    Регистронезависимый поиск; pdftotext иногда даёт SHOUTY CAPS «Ф И Н А Н С О В А Я».
    """
    if not page_text or not header:
        return ""
    # pdftotext рендерит UPPERCASE+letter-spacing как «Ф И Н А Н С О В А Я».
    # Делаем устойчивый поиск: если буквенный паттерн встречается с пробелами
    # между буквами — найдём его, иначе обычный поиск.
    norm_text = re.sub(r"\s+", " ", page_text)
    norm_header = re.sub(r"\s+", " ", header)

    # Try direct
    idx = norm_text.lower().find(norm_header.lower())
    # Try spaced UPPER
    if idx < 0:
        spaced = " ".join(list(norm_header.upper()))
        idx_sp = norm_text.find(spaced)
        if idx_sp >= 0:
            idx = idx_sp
            # переходим в конец заголовка
            idx += len(spaced)
        else:
            return ""
    else:
        idx += len(norm_header)

    block = norm_text[idx : idx + max_chars]
    # Обрезка по footer-маркерам
    for stop in ["Маникюр ·", "ZEREK · QUICK CHECK", "Страница "]:
        cut = block.find(stop)
        if cut >= 0:
            block = block[:cut]
            break
    return block.strip(" :·")


def parse_number(s: str) -> int:
    """Парсит «315 000» / «315K» / «1.2М» в int. На мусоре → 0."""
    if not s:
        return 0
    s = s.replace(" ", " ").replace(" ", " ").strip()
    m = re.match(r"^([\d\s]+)$", s)
    if m:
        try:
            return int(re.sub(r"\s+", "", s))
        except ValueError:
            return 0
    m = re.match(r"^(\d+(?:[.,]\d+)?)\s*[Kk]$", s)
    if m:
        try:
            return int(float(m.group(1).replace(",", ".")) * 1000)
        except ValueError:
            return 0
    m = re.match(r"^(\d+(?:[.,]\d+)?)\s*[МMм]$", s)
    if m:
        try:
            return int(float(m.group(1).replace(",", ".")) * 1_000_000)
        except ValueError:
            return 0
    try:
        return int(s)
    except ValueError:
        return 0


def extract_numbers_after(page_text: str, anchor: str, window: int = 80) -> List[int]:
    """Все числа > 1000 в окне `window` символов СРАЗУ ПОСЛЕ `anchor`.

    Используем для случаев типа «На мощности: 281 000 ₸» — нужно брать
    число справа от фразы, иначе ловится средняя ЗП слева. На каждое
    вхождение anchor собираем числа после него; если anchor встретился
    несколько раз — список содержит числа со всех вхождений.
    """
    if not page_text or not anchor:
        return []
    norm = re.sub(r"\s+", " ", page_text)
    out: List[int] = []
    start = 0
    while True:
        idx = norm.lower().find(anchor.lower(), start)
        if idx < 0:
            break
        snippet_start = idx + len(anchor)
        snippet = norm[snippet_start : snippet_start + window]
        for m in _NUM_PAT.finditer(snippet):
            v = parse_number(m.group())
            if v > 1000:
                out.append(v)
        start = idx + len(anchor)
    return out


def extract_numbers_near(page_text: str, anchor: str, window: int = 80) -> List[int]:
    """Все числа > 1000 в окне ±window символов от первого вхождения `anchor`.

    Полезно для проверок «после слова мощности на стр. N стоит 315K»:

        nums = extract_numbers_near(page8, 'мощности', window=100)
        # → [315000, 315000]   ← если упомянуто дважды на странице
    """
    if not page_text or not anchor:
        return []
    norm = re.sub(r"\s+", " ", page_text)
    idx = norm.lower().find(anchor.lower())
    if idx < 0:
        return []
    lo = max(0, idx - window)
    hi = min(len(norm), idx + len(anchor) + window)
    snippet = norm[lo:hi]
    out: List[int] = []
    for m in _NUM_PAT.finditer(snippet):
        v = parse_number(m.group())
        if v > 1000:
            out.append(v)
    return out


def collect_all_engine_numbers(engine_result: dict) -> List[int]:
    """Все числа > 1000 из плоского engine_result. Используется правилом
    `check_no_orphan_numbers` для поиска чисел в PDF без пары в движке.
    """
    out: List[int] = []
    for v in (engine_result or {}).values():
        try:
            iv = int(v)
            if iv > 1000:
                out.append(iv)
        except (TypeError, ValueError):
            continue
    return out


def text_contains_phrase(text: str, phrase: str) -> bool:
    """Регистронезависимая проверка наличия фразы.

    Устойчива к pdftotext-артефактам: множественные пробелы / переносы
    строк нормализуются до одного пробела перед сравнением.
    """
    if not text or not phrase:
        return False
    norm_text = re.sub(r"\s+", " ", text).lower()
    norm_phrase = re.sub(r"\s+", " ", phrase).lower()
    return norm_phrase in norm_text


def find_phrase_context(text: str, phrase: str, window: int = 80) -> str:
    """Как find_context, но устойчиво к множественным пробелам в PDF."""
    if not text or not phrase:
        return ""
    norm_text = re.sub(r"\s+", " ", text)
    idx = norm_text.lower().find(phrase.lower())
    if idx < 0:
        return ""
    lo = max(0, idx - window)
    hi = min(len(norm_text), idx + len(phrase) + window)
    return norm_text[lo:hi].strip()
