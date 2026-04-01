# Observability & Evals

- **Метрики (Prometheus/Grafana):**
  - `llm_request_duration_seconds`
  - `llm_tokens_total` (с лейблами prompt/completion)
  - `tool_execution_errors_total` (критично для отслеживания сломанных API интеграций).
- **Трейсинг (LangSmith / OpenTelemetry):**
  - Запись каждого шага графа. Позволяет дебажить, *почему* LLM решила поставить встречу на 3 часа ночи.
- **Логирование:** JSON-формат в stdout. Уровни: INFO для транзакций, WARN для ретраев LLM/Tools, ERROR для падений графа.
