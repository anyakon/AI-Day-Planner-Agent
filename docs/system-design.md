# System Design
AI Day Planner Agent

## Архитектура

Реализован паттерн **ReAct** (Reason + Act) через LangGraph State Graph:

```
think (LLM решает) -> execute (инструменты) -> think -> ... -> END
```

Дополнительно: NLP парсер преобразует текст пользователя в структурированные задачи с `suggested_start`.

## Ключевые решения

- **NLP Parser** — LLM извлекает задачи из текста с suggested_start (утро=09:00, день=13:00, вечер=18:00)
- **ReAct цикл** — LLM сама решает какие инструменты вызывать, анализирует результаты и повторяет
- **Function calling** — OpenAI-compatible API для вызова инструментов через LiteLLM прокси
- **Guardrails** — prompt injection detection (10 regex), Pydantic validation, output safety check
- **PII Anonymization** — все задачи проходят через anonymize_text() перед отправкой в LLM
- **Валидация до создания** — validate_schedule проверяет план перед create_event
- **Детальные метрики** — e2e latency (avg/p50/p95), TTFT, TPOT, tokens, cost
- **Prometheus endpoint** — GET /metrics для scrape
- **Ограничение итераций** — max 25 циклов + recursion_limit 150 для защиты от зацикливания
- **Rate limiting** — RateLimiter контролирует частоту вызовов инструментов
- **Ночной запрет** — 00:00-07:00 запрещено через системный промпт

## Модули

| Модуль | Файл | Роль |
|--------|------|------|
| NLP Parser | nlp_parser.py | Распознавание задач из текста, suggested_start |
| Agent | planner.py | ReAct цикл, LangGraph, 5 инструментов, guardrails check |
| Config | config.py | Продуктовая конфигурация, LLM, безопасность |
| Security | security.py | Анонимизация PII, валидация, RateLimiter |
| Guardrails | guardrails.py | Injection detection, Pydantic, output safety |
| Evals | evals.py | 4 метрики качества + общий скор |
| Monitoring | monitoring.py | MetricsCollector (p50/p95), Prometheus format, Langfuse |
| Server | server.py | FastAPI API, Prometheus /metrics |

## Workflow

1. Пользователь вызывает POST /api/chat с текстом
2. Guardrail check: validate_task_input() — PII + injection + Pydantic
3. NLP парсер: extract_tasks_from_text() — извлекает задачи с suggested_start
4. Анонимизация задач (security.py)
5. Инициализация LangGraph StateGraph
6. Цикл think -> execute:
   - think: LLM получает контекст и решает какие инструменты вызвать
   - execute: инструменты выполняются с rate limiting и валидацией
   - Результаты добавляются в историю сообщений
7. Автозавершение когда все задачи размещены или достигнут лимит итераций
8. Оценка качества плана (evals.py) — placement, overlaps, deadlines, efficiency
9. Сохранение метрик: latency, tokens, cost (monitoring.py)
10. Langfuse trace (если подключён)
11. Возврат результата

## State

```
AgentState:
  tasks: List[dict]           — анонимизированные задачи
  original_tasks: List[dict]  — исходные задачи
  messages: List[dict]        — история диалога LLM
  plan: List[dict]            — размещённые события
  plan_valid: bool            — результат последней валидации
  plan_errors: List[str]      — ошибки валидации
  tool_results: List[dict]    — результаты инструментов
  iteration: int              — счётчик циклов
  events_created: int         — счётчик созданных событий
```

## Инструменты

| Инструмент | Параметры | Что делает |
|-----------|-----------|-----------|
| get_current_time | — | Возвращает дату, время, день недели |
| get_date | offset_days | Дата со смещением от сегодня |
| get_events | date | События календаря на дату |
| validate_schedule | plan, date | Проверка: прошлое, пересечения, end <= start |
| create_event | date, task_name, start_time, end_time | Создание события с проверкой конфликтов |

## Failure Modes

| Сбой | Защита |
|------|--------|
| LLM недоступна | sys.exit(1) при старте, RuntimeError при вызове |
| Зацикливание | max_iterations=25, recursion_limit=150 |
| Создание в прошлом | Проверка в create_event и validate_schedule |
| Пересечение событий | Проверка календаря перед записью в create_event |
| Ночное размещение | Прямой запрет в SYSTEM_PROMPT (00:00-07:00) |
| Rate limit | RateLimiter (10 вызовов/мин) |
| PII утечка | anonymize_text() перед LLM, validate_tool_input() |
| Prompt injection | check_prompt_injection() + Pydantic field_validator |
| Опасный output LLM | check_output_safety() |
| Ошибка календаря | ToolResult(success=False), агент пробует другой путь |

## Ограничения

- Latency: ответ < 60 секунд для текстового запроса
- Cost: контроль через max_tokens=2000
- Reliability: agent retry при ошибках инструментов
- Без алгоритмического fallback — требует LLM
- Один календарь (Google Calendar primary)

## Мониторинг

### Метрики

- total_runs, successful_runs, failed_runs
- task_placement_rate, success_rate
- e2e_latency: avg, p50, p95
- time_to_first_token: avg, p50, p95
- time_per_output_token: avg, p50, p95
- total_input_tokens, total_output_tokens
- total_cost_usd
- guardrail_rejections
- tool_call_counts (по каждому инструменту)
- error_counts (по типу исключения)

### Инфраструктура

- **Prometheus** — scrape /metrics каждые 10 секунд
- **Grafana** — 16 панелей (overview, latency, tokens, cost, tools, errors)
- **Langfuse** — трассировка вызовов LLM (cloud)
