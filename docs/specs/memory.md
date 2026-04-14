# Memory & Context

## Session State

Хранится в AgentState (LangGraph). Формат: list of messages (role, content, tool_calls).

## Долгосрочная память

Файл memory.json — сохранённые предпочтения пользователя.

Инструменты:
- save_preference(key, value) — записать
- get_preferences() — прочитать

## Контекст для LLM

System prompt включает:
- описание инструментов
- порядок действий
- правила (suggested_start, ночной запрет)
- задачи пользователя (анонимизированные)

## NLP Context

NLP парсер добавляет к каждой задаче:
- suggested_start: рекомендуемое время начала
- preferred_time: утро/день/вечер/любое

## Context Budgeting

- max_tokens=2000 на ответ LLM
- temperature=0.3 для детерминированности
- Полная история сообщений передаётся в каждом вызове
