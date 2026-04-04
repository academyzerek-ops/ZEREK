"""
ZEREK — Генератор финансовой модели из шаблона.
Берёт отредактированный шаблон Адиля, подставляет данные из анкеты/движка.
Заголовки = формулы (автообновление при смене параметров).

Использование:
    from gen_finmodel import generate_finmodel
    path = generate_finmodel(template_path, params)
"""
from openpyxl import load_workbook
from openpyxl.styles import Font
from datetime import datetime
import os, copy, shutil

# Карта ячеек ПАРАМЕТРЫ (row → column C)
# Эти ячейки подставляются из данных анкеты/движка
PARAM_MAP = {
    5: 'business_name',    # Название бизнеса
    6: 'city',             # Город
    7: 'entity_type',      # ИП / ТОО
    8: 'tax_regime',       # УСН / ОУР
    9: 'tax_rate',         # 0.03
    10: 'horizon',         # 36
    13: 'check_med',       # Средний чек
    14: 'traffic_med',     # Клиентов/день
    15: 'work_days',       # Рабочих дней
    16: 'traffic_growth',  # Рост трафика
    17: 'check_growth',    # Рост чека
    20: 'cogs_pct',        # Себестоимость %
    21: 'loss_pct',        # Потери %
    24: 'rent',            # Аренда
    25: 'area_m2',         # Площадь
    26: 'fot_net',         # ФОТ чистый
    27: 'headcount',       # Кол-во сотрудников
    28: 'utilities',       # Коммунальные
    29: 'marketing',       # Маркетинг
    30: 'consumables',     # Расходники
    31: 'software',        # Софт
    32: 'other',           # Прочие
    33: 'rent_growth',     # Рост аренды
    34: 'fot_growth',      # Рост ФОТ
    35: 'inflation',       # Инфляция прочих
    38: 'capex',           # CAPEX
    39: 'deposit_months',  # Депозит
    40: 'working_cap',     # Оборотный капитал
    41: 'amort_years',     # Амортизация лет
    47: 'credit_amount',   # Кредит
    48: 'credit_rate',     # Ставка кредита
    49: 'credit_term',     # Срок кредита
    53: 'rampup_months',   # Ramp-up
    54: 'rampup_start',    # Старт %
    57: 'wacc',            # WACC
}

# Карта ячеек ДОПУЩЕНИЯ — сезонность (row 5, columns C-N)
SEASON_COLS = list(range(3, 15))  # C=3, D=4, ... N=14


def generate_finmodel(
    template_path: str,
    params: dict,
    seasonality: list = None,
    output_path: str = None,
    eq_note: str = '',
) -> str:
    """
    Генерирует финмодель из шаблона.
    
    params — dict с ключами из PARAM_MAP.values():
        business_name, city, check_med, traffic_med, rent, fot_net, capex, ...
    seasonality — список 12 коэффициентов [0.85, 0.85, 0.90, ...]
    output_path — куда сохранить (None = автоимя)
    eq_note — описание оборудования для дисклеймера CAPEX
    """
    
    if seasonality is None:
        seasonality = [0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.90, 1.15]
    
    # Дефолты
    defaults = {
        'business_name': 'Бизнес',
        'city': 'Актобе',
        'entity_type': 'ИП',
        'tax_regime': 'УСН',
        'tax_rate': 0.03,
        'horizon': 36,
        'check_med': 1400,
        'traffic_med': 70,
        'work_days': 30,
        'traffic_growth': 0.07,
        'check_growth': 0.08,
        'cogs_pct': 0.35,
        'loss_pct': 0.03,
        'rent': 70000,
        'area_m2': 20,
        'fot_net': 150000,
        'headcount': 1,
        'utilities': 8000,
        'marketing': 10000,
        'consumables': 3500,
        'software': 5000,
        'other': 0,
        'rent_growth': 0.10,
        'fot_growth': 0.08,
        'inflation': 0.10,
        'capex': 800000,
        'deposit_months': 2,
        'working_cap': 160000,
        'amort_years': 7,
        'credit_amount': 0,
        'credit_rate': 0.22,
        'credit_term': 36,
        'rampup_months': 3,
        'rampup_start': 0.40,
        'wacc': 0.20,
    }
    
    # Мержим дефолты с переданными параметрами
    for k, v in defaults.items():
        if k not in params or params[k] is None:
            params[k] = v
    
    # Копируем шаблон
    wb = load_workbook(template_path)
    
    P = "'⚙️ ПАРАМЕТРЫ'"
    today = datetime.now().strftime('%d.%m.%Y')
    
    # ── 1. Подставляем ПАРАМЕТРЫ ──
    ws = wb['⚙️ ПАРАМЕТРЫ']
    for row, key in PARAM_MAP.items():
        value = params.get(key)
        if value is not None:
            ws.cell(row=row, column=3, value=value)
    
    # Обновляем дисклеймер CAPEX если есть eq_note
    if eq_note:
        ws.cell(row=38, column=5, value=f'💡 {eq_note}')
    
    # Обновляем дату в футере
    ws.cell(row=59, column=2, value=f'ZEREK Financial Model | {today} | @zerekai_bot')
    
    # ── 2. Подставляем ДОПУЩЕНИЯ (сезонность) ──
    ws2 = wb['📊 ДОПУЩЕНИЯ']
    for j, coef in enumerate(seasonality[:12]):
        ws2.cell(row=5, column=3 + j, value=coef)
    
    # ── 3. Динамические заголовки (формулы) ──
    # НАВИГАЦИЯ
    ws_nav = wb['📋 НАВИГАЦИЯ']
    ws_nav['A1'] = f'="ФИНАНСОВАЯ МОДЕЛЬ — "&UPPER({P}!C5)'
    ws_nav['A2'] = f'="Город: "&{P}!C6&"  |  Горизонт: "&{P}!C10&" месяцев  |  ZEREK"'
    
    # ПАРАМЕТРЫ  
    ws['A1'] = f'="ПАРАМЕТРЫ МОДЕЛИ — "&UPPER(C5)'
    
    # ДОПУЩЕНИЯ
    ws2['A1'] = f'="ДОПУЩЕНИЯ МОДЕЛИ — "&UPPER({P}!C5)'
    
    # ДАШБОРД
    ws_d = wb['🎯 ДАШБОРД']
    ws_d['A1'] = f'="ДАШБОРД — "&UPPER({P}!C5)&" ("&{P}!C6&")"'
    ws_d['A2'] = f'="Дата: {today}  |  Горизонт: "&{P}!C10&" мес  |  Все показатели обновляются автоматически"'
    
    # P&L
    ws_pl = wb['📈 P&L']
    ws_pl['A1'] = f'="ОТЧЁТ О ПРИБЫЛЯХ И УБЫТКАХ — "&UPPER({P}!C5)&" ("&{P}!C6&")"'
    
    # CASH FLOW
    ws_cf = wb['💰 CASH FLOW']
    ws_cf['A1'] = f'="ДВИЖЕНИЕ ДЕНЕЖНЫХ СРЕДСТВ — "&UPPER({P}!C5)&" ("&{P}!C6&")"'
    
    # БАЛАНС
    ws_b = wb['📑 БАЛАНС']
    ws_b['A1'] = f'="БАЛАНС (упрощённый) — "&UPPER({P}!C5)'
    
    # ── 4. Сохраняем ──
    if output_path is None:
        name = params.get('business_name', 'Бизнес').replace(':', '_').replace(' ', '_')
        city = params.get('city', 'Город')
        output_path = f'ZEREK_FinModel_{name}_{city}.xlsx'
    
    wb.save(output_path)
    return output_path


def generate_from_quickcheck(template_path: str, qc_result: dict, output_path: str = None) -> str:
    """
    Генерирует финмодель из результата Quick Check.
    qc_result — dict из engine.run_quick_check_v3()
    """
    inp = qc_result.get('input', {})
    fin = qc_result.get('financials', {})
    sf = qc_result.get('staff', {})
    cap = qc_result.get('capex', {})
    tx = qc_result.get('tax', {})
    
    niche_name = inp.get('niche_name', '')
    format_name = inp.get('format_name', '')
    business_name = f'{niche_name}: {format_name}' if niche_name else inp.get('format_id', 'Бизнес')
    
    bk = cap.get('breakdown', {})
    capex_total = (bk.get('equipment', 0) or 0) + (bk.get('renovation', 0) or 0) + \
                  (bk.get('furniture', 0) or 0) + (bk.get('first_stock', 0) or 0) + \
                  (bk.get('permits_sez', 0) or 0)
    
    params = {
        'business_name': business_name,
        'city': inp.get('city_name', inp.get('city_id', 'Актобе')),
        'entity_type': 'ИП',
        'tax_regime': tx.get('regime', 'УСН'),
        'tax_rate': (tx.get('rate_pct', 3) or 3) / 100,
        'check_med': fin.get('check_med', 1400),
        'traffic_med': fin.get('traffic_med', 70),
        'work_days': 30,
        'cogs_pct': fin.get('cogs_pct', 0.35),
        'loss_pct': fin.get('loss_pct', 0.03),
        'rent': fin.get('rent_month', 70000),
        'area_m2': inp.get('area_m2', 20),
        'fot_net': sf.get('fot_net_med', 150000),
        'headcount': sf.get('headcount', 1),
        'utilities': fin.get('utilities', 8000),
        'marketing': fin.get('marketing', 10000),
        'consumables': fin.get('consumables', 3500),
        'software': fin.get('software', 5000),
        'other': fin.get('transport', 0),
        'capex': capex_total or cap.get('capex_med', 800000),
        'deposit_months': fin.get('deposit_months', 2),
        'working_cap': bk.get('working_cap', 160000) or 160000,
    }
    
    return generate_finmodel(template_path, params, output_path=output_path)


# ═══ ТЕСТ ═══
if __name__ == '__main__':
    template = '/mnt/user-data/uploads/ZEREK_FinModel_Кофейня_Актобе.xlsx'
    
    # Тест 1: подстановка параметров для донерной
    params = {
        'business_name': 'Донерная: Мини-кафе',
        'city': 'Астана',
        'check_med': 2000,
        'traffic_med': 55,
        'cogs_pct': 0.35,
        'rent': 130000,
        'fot_net': 270000,
        'headcount': 2,
        'capex': 1500000,
        'tax_rate': 0.03,
    }
    
    path = generate_finmodel(template, params, output_path='/home/claude/ZEREK_FinModel_Донерная_Астана.xlsx')
    print(f'Тест 1: {path}')
    
    # Проверяем что подставилось
    from openpyxl import load_workbook as lw
    wb = lw(path)
    ws = wb['⚙️ ПАРАМЕТРЫ']
    print(f'  C5 (бизнес): {ws["C5"].value}')
    print(f'  C6 (город): {ws["C6"].value}')
    print(f'  C13 (чек): {ws["C13"].value}')
    print(f'  C14 (трафик): {ws["C14"].value}')
    print(f'  C24 (аренда): {ws["C24"].value}')
    print(f'  C38 (CAPEX): {ws["C38"].value}')
    
    # Проверяем заголовки = формулы
    ws_d = wb['🎯 ДАШБОРД']
    print(f'  Дашборд A1: {ws_d["A1"].value[:60]}')
    print('OK!')
