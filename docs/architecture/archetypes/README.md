# Архетипы расчёта

Архетип = шаблон финансовой формулы. Привязывается к format_id через `formats_r12.<format>.archetype`.

| Архетип | Описание | Состояние | Файл |
|---|---|---|---|
| A1 | Мастер-одиночка | ✓ в коде (MANICURE pilot) | [A1-master-solo.md](A1-master-solo.md) |
| A2 | Мастер за % в чужой структуре | ✓ в коде (через A1 + commission_pct) | [A2-master-rent-out.md](A2-master-rent-out.md) |
| B1 | Владелец-сдатчик (пассивный) | ⚠ TBD — engine extension нужно | [B1-owner-passive.md](B1-owner-passive.md) |
| B2 | Владелец-наёмщик (активный) | ⚠ TBD — engine extension нужно | [B2-owner-active.md](B2-owner-active.md) |

## Когда добавлять новый архетип

Не добавлять, если можно представить через существующий через параметры. Пример: A2 = A1 + `commission_pct > 0`, отдельный архетип формально не нужен, но удобно для документации.

Реальные новые архетипы (B1, B2) требуют:
- Новой функции в `api/services/economics_service.py` (calc_owner_b1_economics / calc_owner_b2_economics)
- Расширения `_apply_r12_5_overrides` под новые поля
- Новой ветки в `compute_pnl_aggregates` и `simulate_calendar_pnl`

После реализации обновить этот README — пометить ✓.
