"""Unit tests for tax_constants_loader (YAML-first налоговые константы КЗ 2026)."""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from loaders import tax_constants_loader as t  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_cache():
    """Сброс lru_cache между тестами."""
    t.clear_cache()
    yield
    t.clear_cache()


# ═══ Базовые показатели ═════════════════════════════════════════════════


def test_mrp_returns_4325():
    assert t.get_mrp() == 4325


def test_mzp_returns_85000():
    assert t.get_mzp() == 85000


# ═══ УСН по городам ═════════════════════════════════════════════════════


def test_usn_astana_returns_3_pct():
    assert t.get_usn_rate_for_city("astana") == 3.0


def test_usn_astana_case_insensitive():
    """city_id нормализуется к upper."""
    assert t.get_usn_rate_for_city("Astana") == 3.0
    assert t.get_usn_rate_for_city("ASTANA") == 3.0


def test_usn_shymkent_returns_2_pct():
    assert t.get_usn_rate_for_city("shymkent") == 2.0


# ═══ Города с расхождением xlsx vs YAML v1.1 (регрессия против баги) ═══
# Эти 6 городов в xlsx значились как 3%, реальная ставка по решениям
# маслихатов на 2026 — 2%. YAML v1.1 — источник истины.


def test_karaganda_rate_is_2_pct():
    """Карагандинская область — 2% (не 3% как было в xlsx)."""
    assert t.get_usn_rate_for_city("karaganda") == 2.0


def test_atyrau_rate_is_2_pct():
    """Атырауская область — 2%."""
    assert t.get_usn_rate_for_city("atyrau") == 2.0


def test_oskemen_rate_is_2_pct():
    """Усть-Каменогорск (ВКО) — 2%."""
    assert t.get_usn_rate_for_city("oskemen") == 2.0


def test_taraz_rate_is_2_pct():
    """Тараз (Жамбылская область) — 2%."""
    assert t.get_usn_rate_for_city("taraz") == 2.0


def test_kokshetau_rate_is_2_pct():
    """Кокшетау (Акмолинская область) — 2%."""
    assert t.get_usn_rate_for_city("kokshetau") == 2.0


def test_semey_rate_is_2_pct():
    """Семей (область Абай) — 2%."""
    assert t.get_usn_rate_for_city("semey") == 2.0


def test_astana_baseline_still_3_pct():
    """Регрессия: Астана осталась на 3% (не сломали при миграции)."""
    assert t.get_usn_rate_for_city("astana") == 3.0


def test_turkistan_spelling_variants_match_turkestan():
    """TURKISTAN (каз.) и turkestan (англ.) резолвятся в одну ставку."""
    assert t.get_usn_rate_for_city("TURKISTAN") == t.get_usn_rate_for_city("turkestan")


def test_petropavlovsk_full_name_matches_petropavl():
    """PETROPAVLOVSK (полная форма) резолвится как petropavl."""
    assert t.get_usn_rate_for_city("PETROPAVLOVSK") == t.get_usn_rate_for_city("petropavl")


def test_usn_unknown_city_returns_default_4_pct():
    """Неизвестный город → базовая ставка по умолчанию (4%)."""
    assert t.get_usn_rate_for_city("UNKNOWN_CITY_XYZ") == 4.0


def test_usn_empty_city_returns_default():
    assert t.get_usn_rate_for_city("") == 4.0


def test_usn_base_rate_is_4_pct():
    assert t.get_usn_base_rate() == 4.0


# ═══ Минимальный платёж ИП ═════════════════════════════════════════════


def test_ip_minimum_monthly_is_21675():
    """Минимальный обязательный платёж ИП/мес = 21 675 ₸."""
    assert t.get_ip_minimum_monthly_payment() == 21675


def test_ip_minimum_components_sum_matches_total():
    """Сумма компонент = total (иначе YAML рассинхронен)."""
    components = t.get_ip_minimum_components()
    assert sum(components.values()) == t.get_ip_minimum_monthly_payment()


def test_ip_minimum_components_names():
    """Компоненты содержат все 4 налоговых платежа."""
    components = t.get_ip_minimum_components()
    assert set(components.keys()) == {"opv", "opvr", "so", "vosms"}


def test_ip_minimum_components_individual():
    """Индивидуальные значения совпадают со спекой YAML."""
    c = t.get_ip_minimum_components()
    assert c["opv"] == 8500     # 10% × 85000
    assert c["opvr"] == 2975    # 3.5% × 85000
    assert c["so"] == 4250      # 5% × 85000
    assert c["vosms"] == 5950   # 5% × (1.4 × 85000)


# ═══ НДС ═══════════════════════════════════════════════════════════════


def test_nds_base_rate_is_16_pct():
    """Ставка НДС 2026 = 16% (повышена с 12%)."""
    assert t.get_nds_rate() == 0.16


def test_nds_threshold_is_43_250_000():
    """Порог обязательной регистрации НДС = 10 000 МРП = 43,25 млн ₸."""
    assert t.get_nds_threshold_kzt() == 43_250_000


# ═══ Payroll multiplier ═══════════════════════════════════════════════


def test_employer_payroll_multiplier_is_1_115():
    """1 + 3.5% (OPVR) + 5% (СО) + 3% (ООСМС) = 1.115."""
    assert t.get_employer_payroll_multiplier() == 1.115


# ═══ Кеширование ═══════════════════════════════════════════════════════


def test_load_cached_across_calls():
    """Повторные вызовы не перечитывают YAML (lru_cache работает)."""
    # После clear_cache вызываем get_mrp — один hit. Далее вызовы должны
    # не вызывать чтение файла. Проверяем по cache_info.
    t.clear_cache()
    _ = t.get_mrp()
    _ = t.get_mzp()
    _ = t.get_nds_rate()
    info = t._load.cache_info()
    assert info.hits >= 2, f"ожидается ≥2 hit, got {info}"
    assert info.misses == 1, f"ожидается 1 miss (первый вызов), got {info}"
