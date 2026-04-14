# AI Day Planner Agent

Автоматическое планирование задач с учётом календаря, дедлайнов и занятых слотов. Принимает запросы на естественном языке.

## Цель

Агент для автоматического планирования задач в календаре пользователя. Принимает текстовый запрос (например "Завтра утром теннис, после обеда код-ревью"), распознаёт задачи, проверяет занятые слоты, составляет расписание без пересечений и создаёт события.

## Операционные ограничения

- События нельзя создавать в прошлом
- События нельзя создавать без предварительной валидации
- Rate limit: 10 вызовов инструментов в минуту
- Максимум 25 итераций ReAct-цикла
- Запрет на ночное время (00:00-07:00)

## Запуск

```bash
pip install -r requirements.txt
python server.py
```

http://localhost:8000

## Способы взаимодействия

### 1. Текстовый запрос (обработка NLP через агента)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Завтра утром теннис, после обеда код-ревью, вечером ретро"}'
```

Агент распознаёт задачи из текста, определяет предпочтительное время и размещает в календаре.

### 2. Структурированный запрос

```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{"tasks":[{"name":"Теннис","duration":60,"deadline":"23:59"}]}'
```


## Архитектура

```
Текст пользователя
       │
       ▼
┌──────────────┐
│ NLP Parser   │  LLM: извлекает задачи с suggested_start
│ nlp_parser.py│
└──────┬───────┘
       ▼
┌──────────────┐
│ Guardrails   │  Pydantic + injection check + PII anonymization
│ guardrails.py│
└──────┬───────┘
       ▼
┌──────────────┐
│ Agent (ReAct)│  LangGraph: think → execute → ... → END
│ planner.py   │  5 инструментов + suggested_start
└──────┬───────┘
       ▼
┌──────────────┐
│ Calendar     │  Google Calendar API
│ + Metrics    │  Prometheus + Langfuse
└──────────────┘
```

## Компоненты

| Файл | Назначение |
|---|---|
| `planner.py` | Агент: ReAct цикл, 5 инструментов, LangGraph |
| `nlp_parser.py` | Распознавание задач из текста (LLM + suggested_start) |
| `config.py` | Продуктовая конфигурация |
| `security.py` | Анонимизация PII, валидация, RateLimiter |
| `guardrails.py` | Prompt injection detection, Pydantic, output safety |
| `evals.py` | Оценка качества: placement, overlaps, deadlines, efficiency |
| `monitoring.py` | Метрики (p50/p95, TTFT, TPOT, tokens, cost), Prometheus, Langfuse |
| `server.py` | FastAPI API + Prometheus endpoint |

## NLP: Распознавание задач из текста

| Фраза | Распознанная задача |
|---|---|
| "Завтра утром теннис" | name=Теннис, duration=60, suggested_start=09:00, preferred_time=утро |
| "После обеда код-ревью" | name=Код-ревью, duration=45, suggested_start=14:00, preferred_time=день |
| "Вечером ретро" | name=Ретро, duration=60, suggested_start=18:00, preferred_time=вечер |

Временные окна: утро=09:00-12:00, день=13:00-17:00, вечер=18:00-21:00

## Guardrails

| Тип | Механизм | Где реализовано |
|---|---|---|
| Prompt injection | 10 regex паттернов + Pydantic | `guardrails.py` |
| Input validation | Pydantic: name max 200, duration > 0 <= 1440, deadline HH:MM | `guardrails.py` |
| Output safety | Dangerous commands, SQL injection, XSS | `guardrails.py` |
| PII anonymization | Regex: телефоны, email, паспорта, карты, СНИЛС | `security.py` |
| Tool input validation | Блокировка PII-ключей в аргументах | `security.py` |
| Rate limiting | 10 вызовов/мин, скользящее окно | `security.py` |
| Time validation | Прошлое время, пересечения, end <= start, ночной запрет | `planner.py` |
| Loop protection | max 25 итераций + recursion_limit 150 | `config.py` |
| LLM required | Без API ключа агент не запускается | `planner.py` |

## Инструменты агента

| Инструмент | Параметры | Что делает |
|---|---|---|
| `get_current_time` | — | Текущие дата и время |
| `get_date` | offset_days | Дата со смещением (0=сегодня, 1=завтра) |
| `get_events` | date (YYYY-MM-DD) | События календаря на дату |
| `validate_schedule` | plan, date | Проверка: прошлое, пересечения, end <= start |
| `create_event` | date, task_name, start_time, end_time | Создание события с проверкой конфликтов |

## Метрики

| Метрика | Описание |
|---|---|
| total_runs / success_rate | Всего запусков и доля успешных |
| task_placement_rate | Доля размещённых задач |
| e2e_latency (avg/p50/p95) | Полное время выполнения |
| time_to_first_token (avg/p95) | Задержка до первого токена |
| time_per_output_token (avg/p95) | Время на выходной токен |
| total_input_tokens / total_output_tokens | Токены LLM |
| total_cost_usd | Стоимость вызовов LLM |
| guardrail_rejections | Отклонённые запросы |
| tool_call_counts | Вызовы каждого инструмента |
| error_counts | Типы ошибок |

## Мониторинг

| Сервис | URL | Описание |
|---|---|---|
| Agent API | http://localhost:8000 | FastAPI сервер |
| Prometheus | http://localhost:9090 | Сбор метрик (scrape /metrics каждые 10с) |
| Grafana | http://localhost:3000 (admin/admin) | Визуализация (16 панелей) |
| Langfuse | https://us.cloud.langfuse.com | Трейсинг вызовов LLM |

```bash
docker-compose up -d
```

## Конфигурация

Файл `.env`:

```
OPENAI_API_KEY=sk-...
OPENAI_URL=https://litellm.tokengate.ru/v1
OPENAI_MODEL=openai/gpt-4o
LANGFUSE_HOST=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

## Безопасность

- PII анонимизируется перед отправкой в LLM
- Входные данные валидируются через Pydantic + injection check
- Rate limiting на вызовы инструментов
- Валидация времени и пересечений до создания событий
- Запрет на ночное время (00:00-07:00)
- Guardrail rejection логируется

## Ограничения PoC

- Планирование на день/несколько дней
- Один календарь (Google Calendar)
- Без долгосрочной истории предпочтений
- Без интеграции с таск-менеджерами
