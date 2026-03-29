"""Тестовый запуск Quick Check — 3 сценария."""

import sys
sys.path.insert(0, "/home/claude/zerek_engine")
sys.path.insert(0, "/home/claude")

from engine import ZerekDB, run_quick_check
from report import render_report

# Загружаем базу
db = ZerekDB(data_dir="/home/claude/zerek_data")

# ── ТЕСТ 1: Кофейня-киоск в Актобе ──
print("\n" + "="*60)
print("ТЕСТ 1: Кофейня-киоск в Актобе, спальный район")
print("="*60)
result1 = run_quick_check(
    db=db,
    city_id="AKT",
    niche_id="COFFEE",
    format_id="COFFEE_KIOSK",
    area_m2=8,
    loc_type="Спальный район стрит",
    capital=3_500_000,
    start_month=4,
    capex_level="стандарт",
)
print(render_report(result1))

# ── ТЕСТ 2: Барбершоп стандарт в Алматы ──
print("\n" + "="*60)
print("ТЕСТ 2: Барбершоп стандарт в Алматы, центр")
print("="*60)
result2 = run_quick_check(
    db=db,
    city_id="ALA",
    niche_id="BARBER",
    format_id="BARBER_STD",
    area_m2=48,
    loc_type="Центр стрит 1 лин",
    capital=6_000_000,
    start_month=3,
    capex_level="стандарт",
)
print(render_report(result2))

# ── ТЕСТ 3: Автомойка 1 пост в Уральске ──
print("\n" + "="*60)
print("ТЕСТ 3: Автомойка 1 пост в Уральске")
print("="*60)
result3 = run_quick_check(
    db=db,
    city_id="URA",
    niche_id="CARWASH",
    format_id="CARWASH_BOX1",
    area_m2=80,
    loc_type="Отдельное здание/бокс",
    capital=5_000_000,
    start_month=5,
    capex_level="стандарт",
)
print(render_report(result3))
