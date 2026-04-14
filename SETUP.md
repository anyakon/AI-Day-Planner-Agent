# Инструкция по запуску AI Day Planner Agent

## Предварительные требования

1. **Python 3.10+**
2. **OpenAI API Key** — получите на platform.openai.com/api-keys
3. **Google Calendar API Credentials** — настройте доступ к Google Calendar

## Настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка OpenAI API

Создайте файл `.env` в корне проекта:

```env
OPENAI_API_KEY=sk-...
OPENAI_URL=https://litellm.tokengate.ru/v1
OPENAI_MODEL=openai/gpt-4o
LANGFUSE_HOST=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

### 3. Настройка Google Calendar API

1. Перейдите в Google Cloud Console
2. Создайте новый проект или выберите существующий
3. Включите Google Calendar API:
   - APIs & Services → Library → Google Calendar API → Enable
4. Создайте OAuth 2.0 Client ID:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop app
5. Скачайте JSON файл credentials и переименуйте его в `credentials.json`
6. Поместите `credentials.json` в корень проекта (рядом с `planner.py`)

### 4. Запуск

```bash
python planner.py
```

При первом запуске откроется браузер для авторизации Google. После авторизации будет создан файл `token.json` для последующих запусков.
