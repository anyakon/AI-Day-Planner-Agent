# Observability & Evals

## Метрики (MetricsCollector)

Сохраняются в metrics.json после каждого запуска:

| Метрика | Тип | Описание |
|---|---|---|
| total_runs | counter | Всего запусков |
| successful_runs / failed_runs | counter | Успешные/неуспешные |
| task_placement_rate | gauge | Доля размещённых задач |
| success_rate | gauge | Доля успешных запусков |
| avg_plan_quality | gauge | Средний скор качества |
| e2e_latency (avg/p50/p95) | gauge | Полное время выполнения |
| time_to_first_token (avg/p50/p95) | gauge | Задержка до первого токена |
| time_per_output_token (avg/p50/p95) | gauge | Время на выходной токен |
| total_input_tokens | counter | Входные токены LLM |
| total_output_tokens | counter | Выходные токены LLM |
| total_cost_usd | counter | Стоимость вызовов LLM |
| guardrail_rejections | counter | Отклонённые запросы |
| tool_call_counts | counter | Вызовы каждого инструмента |
| error_counts | counter | Типы ошибок |

LatencyTracker хранит до 5000 последних значений для расчёта перцентилей.

## Evals (evaluate_plan_quality)

Оценка каждого плана по 4 метрикам:

- task_placement_rate (вес 0.35) — доля размещённых задач
- no_overlaps (вес 0.30) — отсутствие пересечений между задачами и событиями
- deadline_respect (вес 0.25) — соблюдение дедлайнов
- time_efficiency (вес 0.10) — плотность расписания (штраф за большие пробелы)

overall_score = взвешенная сумма

## Prometheus

Endpoint: `GET /metrics` — формат text exposition.

Scrape каждые 10 секунд. Все метрики с HELP и TYPE.

## Трейсинг (Langfuse)

При каждом запуске:
- trace("planner_run", input, output, metadata)
- metadata: response_time, iterations, input_tokens, output_tokens, cost_usd
- SDK v3: start_as_current_observation()

## Логирование

- stdout: инициализация LLM, Langfuse, ошибки
- metrics.json: количественные метрики
- error_counts: типы исключений
