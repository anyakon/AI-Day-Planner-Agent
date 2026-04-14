# Tools / APIs

## get_current_time

Возвращает текущие дату и время.

Параметры: нет

Результат:
```json
{"time": "14:30", "date": "2026-04-13", "day_of_week": "Monday"}
```

## get_date

Возвращает дату со смещением.

Параметры: offset_days (int)

Результат:
```json
{"date": "2026-04-14", "day_of_week": "Tuesday", "offset": 1}
```

## get_events

Возвращает события календаря на дату.

Параметры: date (YYYY-MM-DD)

Результат:
```json
{"date": "2026-04-13", "events": [
  {"name": "standup", "start": "10:00", "end": "10:30"}
]}
```

## validate_schedule

Проверяет план на конфликты.

Параметры: plan (list), date (YYYY-MM-DD)

План — список объектов с полями task, start (HH:MM), end (HH:MM).

Проверки:
- нет событий в прошлом (для сегодняшней даты)
- нет пересечений между задачами
- end > start для каждой задачи

Результат:
```json
{"valid": true, "date": "2026-04-13", "issues": []}
```

Или:
```json
{"valid": false, "date": "2026-04-13", "issues": ["task1: время 10:00 уже прошло"]}
```

Для LLM результат возвращается в человекочитаемом формате.

## create_event

Создаёт событие в календаре.

Параметры: date (YYYY-MM-DD), task_name, start_time (HH:MM), end_time (HH:MM)

Проверки перед созданием:
- время не в прошлом (сравнение с timezone-aware datetime)
- нет пересечений с существующими событиями

Защита:
- strict comparison start_dt_aware < now
- проверка пересечений через список событий календаря
- возврат ToolResult(False) при конфликте

Результат:
```json
{"id": "...", "name": "task", "start": "09:00", "end": "10:00", "date": "2026-04-13"}
```

## Безопасность инструментов

- validate_tool_input() проверяет аргументы на PII (телефон, email, паспорт, карта)
- RateLimiter ограничивает 10 вызовами в минуту
- Анонимизация задач перед отправкой в LLM
- Guardrail reject при обнаружении injection в параметрах
