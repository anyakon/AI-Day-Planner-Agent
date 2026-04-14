# Agent Orchestrator

- **Архитектура:** ReAct (Reason + Act), LangGraph StateGraph
- **Цикл:** think (LLM) -> execute (tools) -> think -> ... -> END
- **Ограничение:** max 25 итераций, recursion_limit 150
- **Автозавершение:** когда все задачи размещены в plan

## NLP Parser (вход)

1. extract_tasks_from_text(text, client) — LLM извлекает задачи
2. Каждая задача: name, duration, deadline, preferred_time, suggested_start
3. suggested_start: утро=09:00, день=13:00, вечер=18:00

## Guardrails перед запуском

1. validate_task_input() — Pydantic валидация + injection check
2. anonymize_tasks() — замена PII на [REDACTED]
3. При rejection — ValueError, метрика guardrail_rejections

## Переходы

- think -> execute — если LLM вернул tool_calls
- think -> END — если LLM ответил текстом без tool_calls
- execute -> think — если итерация < 25
- execute -> END — если итерация >= 25 или все задачи размещены

## State

```
AgentState:
  tasks, original_tasks, messages, plan
  plan_valid, plan_errors, tool_results
  iteration, events_created
```

## Узлы графа

### llm_think

- Формирует system prompt с задачами пользователя
- SYSTEM_PROMPT включает: suggested_start, запрет ночного времени
- Вызывает LLM с tools=build_tools_spec()
- Добавляет ответ в messages

### tool_execute

- Парсит tool_calls из последнего сообщения
- Проверяет rate limit
- Выполняет инструменты через execute_tool()
- Для validate_schedule — человекочитаемый результат
- Для create_event — добавляет в plan и счётчик
- Проверяет все ли задачи размещены
