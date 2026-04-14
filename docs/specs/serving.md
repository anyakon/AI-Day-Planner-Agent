# Serving, Config & Infra

## Запуск

```bash
pip install -r requirements.txt
python server.py
```

Сервер: FastAPI на порту 8000.

## Конфигурация

Файл .env:

```
OPENAI_API_KEY=sk-...
OPENAI_URL=https://litellm.tokengate.ru/v1
OPENAI_MODEL=openai/gpt-4o
LANGFUSE_HOST=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

## Секции конфига (config.py)

- ProductConfig — цель, метрики успеха, eval sample size
- LLMConfig — api_key, base_url, model, temperature, timeout, max_tokens, max_retries
- AgentConfig — max_iterations=25, recursion_limit=150, max_validation_attempts
- SecurityConfig — anonymize_pii, pii_patterns, rate_limit_per_minute
- LangfuseConfig — enabled, host, public_key, secret_key

## API Endpoints

- POST /api/chat — текстовый запрос (NLP -> план)
- POST /api/plan — структурированные задачи -> план
- GET /api/metrics — текущие метрики (JSON)
- GET /metrics — метрики для Prometheus scrape (text)
- GET / — статус и список endpoint'ов

## Docker инфраструктура

```bash
docker-compose up -d
```

| Сервис | Порт | Описание |
|---|---|---|
| Prometheus | 9090 | Scrape /metrics каждые 10с |
| Grafana | 3000 | Дашборд (admin/admin) |

## Ограничения

- Rate limit: 10 вызовов инструментов в минуту
- Max iterations: 25 циклов ReAct
- Max tokens: 2000 на ответ LLM
- Timeout: 30 секунд на вызов LLM
- Запрет на ночное время: 00:00-07:00
