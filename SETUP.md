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
OPENAI_API_KEY=sk-your-api-key-here
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

### 4. Первый запуск

```bash
python planner.py
```

При первом запуске откроется браузер для авторизации Google. После авторизации будет создан файл `token.json` для последующих запусков.

## Использование в коде

```python
from planner import run_agent

tasks = [
    {"name": "Подготовка отчета", "duration": 60, "deadline": "18:00"},
    {"name": "Изучение материалов", "duration": 90, "deadline": "20:00"},
]

plan = run_agent(tasks)
for item in plan:
    print(f"{item['start']}–{item['end']} — {item['task']}")
```

## Устранение проблем

### Ошибка: `FileNotFoundError: credentials.json не найден`
- Скачайте OAuth credentials из Google Cloud Console
- Положите файл в корень проекта

### Ошибка: `openai.AuthenticationError`
- Проверьте API ключ в файле `.env`
- Убедитесь, что у вас есть доступ к GPT-4o

### Ошибка: `google.auth.exceptions.RefreshError`
- Удалите `token.json` и запустите заново
- Пройдите авторизацию в браузере снова

## Безопасность

НИКОГДА не коммитьте следующие файлы:
- `.env`
- `credentials.json`
- `token.json`
