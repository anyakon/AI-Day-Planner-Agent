# Serving, Config & Infra

- **Запуск:** Docker compose (App + Redis + PostgreSQL).
- **Конфигурация (Environment variables):**
  - `LLM_PROVIDER` (openai, anthropic, ollama)
  - `MODEL_NAME` (primary model)
  - `FALLBACK_MODEL_NAME` (secondary model для ретраев)
  - Секреты (`OPENAI_API_KEY`, `GOOGLE_OAUTH_JSON`) пробрасываются через `.env` .
- **Ограничения ресурсов (Docker):** CPU limit: 1, RAM limit: 512MB для контейнера агента.
