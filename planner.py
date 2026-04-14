"""
AI Day Planner Agent — агент для автоматического планирования задач.

Архитектура: ReAct цикл с function calling.
Агент сам решает какие инструменты вызывать и когда.
"""
import os
import sys
import datetime as dt
import json
import time
from typing import List, TypedDict, Optional, Any
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from langgraph.graph import StateGraph, END

from config import load_config
from security import anonymize_tasks, sanitize_tool_result, validate_tool_input, RateLimiter
from monitoring import MetricsCollector, LangfuseTracker
from evals import evaluate_plan_quality
from guardrails import validate_task_input as guardrail_validate, validate_llm_output

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


config = load_config()
llm_cfg = config["llm"]
agent_cfg = config["agent"]
security_cfg = config["security"]
langfuse_cfg = config["langfuse"]

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = Path(__file__).parent / "token.json"
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"

metrics = MetricsCollector()

langfuse = None
if langfuse_cfg.enabled:
    langfuse = LangfuseTracker(
        host=langfuse_cfg.host,
        public_key=langfuse_cfg.public_key,
        secret_key=langfuse_cfg.secret_key,
    )

client = None
use_llm = bool(llm_cfg.api_key)

if use_llm:
    try:
        from openai import OpenAI
        client_kwargs = {"api_key": llm_cfg.api_key}
        if llm_cfg.base_url:
            client_kwargs["base_url"] = llm_cfg.base_url
        client = OpenAI(**client_kwargs)
        print(f"LLM: {llm_cfg.base_url or 'default'} ({llm_cfg.model})")
    except Exception as e:
        print(f"LLM ошибка: {e}")
        use_llm = False

if not use_llm:
    print("Ошибка: OPENAI_API_KEY не найден. Агент требует LLM.")
    sys.exit(1)

rate_limiter = RateLimiter(security_cfg.rate_limit_per_minute)


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def get_calendar_service():
    creds = get_credentials()
    if creds is None:
        return None
    return build("calendar", "v3", credentials=creds)


def to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def to_time(minutes_val):
    return f"{minutes_val // 60:02d}:{minutes_val % 60:02d}"


class ToolResult:
    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self):
        return {"success": self.success, "data": self.data, "error": self.error}


def tool_get_events(date: str = None) -> ToolResult:
    if date is None:
        date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    try:
        service = get_calendar_service()
        if service is None:
            return ToolResult(False, error="Нет доступа к календарю")
        time_min = f"{date}T00:00:00+03:00"
        time_max = f"{date}T23:59:59+03:00"
        result = service.events().list(
            calendarId="primary", timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy="startTime",
        ).execute()
        events = []
        for e in result.get("items", []):
            s = e["start"].get("dateTime", e["start"].get("date", ""))
            en = e["end"].get("dateTime", e["end"].get("date", ""))
            events.append({
                "name": e.get("summary", "event"),
                "start": s[11:16] if "T" in s else None,
                "end": en[11:16] if "T" in en else None,
            })
        return ToolResult(True, data={"date": date, "events": events})
    except Exception as e:
        return ToolResult(False, error=str(e))


def tool_create_event(date: str, task_name: str, start_time: str, end_time: str) -> ToolResult:
    try:
        service = get_calendar_service()
        if service is None:
            return ToolResult(False, error="Нет доступа к календарю")
        start_dt = dt.datetime.fromisoformat(f"{date}T{start_time}:00")
        end_dt = dt.datetime.fromisoformat(f"{date}T{end_time}:00")
        tz = dt.timezone(dt.timedelta(hours=3))
        now = dt.datetime.now(tz)
        start_dt_aware = dt.datetime(start_dt.year, start_dt.month, start_dt.day,
                                     start_dt.hour, start_dt.minute, tzinfo=tz)
        end_dt_aware = dt.datetime(end_dt.year, end_dt.month, end_dt.day,
                                   end_dt.hour, end_dt.minute, tzinfo=tz)
        if start_dt_aware < now:
            return ToolResult(False, error=f"Время {start_time} уже прошло")
        events_result = service.events().list(
            calendarId="primary",
            timeMin=f"{date}T00:00:00+03:00",
            timeMax=f"{date}T23:59:59+03:00",
            singleEvents=True, orderBy="startTime",
        ).execute()
        for e in events_result.get("items", []):
            s = e["start"].get("dateTime", "")
            en = e["end"].get("dateTime", "")
            if s and en:
                bs = dt.datetime.fromisoformat(s)
                be = dt.datetime.fromisoformat(en)
                if start_dt_aware < be and end_dt_aware > bs:
                    return ToolResult(False, error=f"Пересечение с '{e.get('summary')}'")
        event = {
            "summary": task_name,
            "description": "Создано AI Day Planner Agent",
            "start": {"dateTime": f"{date}T{start_time}:00", "timeZone": "Europe/Moscow"},
            "end": {"dateTime": f"{date}T{end_time}:00", "timeZone": "Europe/Moscow"},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return ToolResult(True, data={
            "id": created["id"], "name": created.get("summary"),
            "start": start_time, "end": end_time, "date": date,
        })
    except Exception as e:
        return ToolResult(False, error=str(e))


def tool_validate_schedule(plan: List[dict], date: str = None) -> ToolResult:
    if date is None:
        date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    now = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=3)))
    now_minutes = now.hour * 60 + now.minute
    issues = []
    prev_end = 0
    for i, item in enumerate(plan):
        if "start" not in item or "end" not in item:
            issues.append(f"Задача {i}: нет start/end")
            continue
        start = to_minutes(item["start"])
        end = to_minutes(item["end"])
        if start < now_minutes and date == now.strftime("%Y-%m-%d"):
            issues.append(f"{item.get('task', '?')}: время {item['start']} уже прошло")
        if start < prev_end:
            issues.append(f"{item.get('task', '?')}: пересечение ({item['start']} < {to_time(prev_end)})")
        if end <= start:
            issues.append(f"{item.get('task', '?')}: end <= start")
        prev_end = end
    return ToolResult(
        success=True,
        data={"valid": len(issues) == 0, "date": date, "issues": issues},
        error=None,
    )


def tool_get_date(offset_days: int = 0) -> ToolResult:
    today = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=3)))
    target = today + dt.timedelta(days=offset_days)
    return ToolResult(True, data={
        "date": target.strftime("%Y-%m-%d"),
        "day_of_week": target.strftime("%A"),
        "offset": offset_days,
    })


def tool_get_current_time() -> ToolResult:
    now = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=3)))
    return ToolResult(True, data={
        "time": now.strftime("%H:%M"),
        "date": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
    })


TOOLS_REGISTRY = {
    "get_events": {"fn": tool_get_events, "params": ["date"]},
    "create_event": {"fn": tool_create_event, "params": ["date", "task_name", "start_time", "end_time"]},
    "validate_schedule": {"fn": tool_validate_schedule, "params": ["plan", "date"]},
    "get_date": {"fn": tool_get_date, "params": ["offset_days"]},
    "get_current_time": {"fn": tool_get_current_time, "params": []},
}


SYSTEM_PROMPT = """Ты — AI Day Planner Agent. Размести ВСЕ задачи в календаре.

Инструменты:
- get_events(date): события календаря на дату
- create_event(date, task_name, start_time, end_time): создать событие
- validate_schedule(plan, date): проверить план
- get_current_time(): текущее время
- get_date(offset_days): дата со смещением

В каждой задаче есть:
- suggested_start — рекомендуемое время начала (например "13:00")
- target_date — целевая дата в формате YYYY-MM-DD

КРИТИЧЕСКИ: Используй target_date из задачи. НЕ меняй дату.
Если в задаче target_date="2026-04-15", создавай событие на 2026-04-15.

Используй suggested_start как точку отсчёта. Если время занято — пробуй 13:30, 14:00, 14:30 и т.д.
НЕЛЬЗЯ ставить задачи на время с 00:00 до 07:00 (ночной сон).

Порядок:
1. get_current_time()
2. Сгруппируй задачи по target_date
3. Для каждой даты: get_events(date)
4. Для каждой задачи: найди свободный слот начиная с suggested_start (избегай 00:00-07:00)
5. validate_schedule(plan, date)
6. create_event для каждой задачи
7. Покажи расписание по дням

Правила:
- ВСЕ задачи должны быть размещены
- Используй target_date из задачи
- suggested_start — точка отсчёта, сдвигай если занято
- НЕЛЬЗЯ 00:00-07:00
- Не пересекай события

Задачи:
{tasks}

Отвечай на русском."""


def build_tools_spec():
    return [
        {"type": "function", "function": {
            "name": "get_events",
            "description": "События из календаря на дату (YYYY-MM-DD)",
            "parameters": {"type": "object", "properties": {
                "date": {"type": "string", "description": "Дата YYYY-MM-DD"},
            }},
        }},
        {"type": "function", "function": {
            "name": "create_event",
            "description": "Создать событие в календаре",
            "parameters": {"type": "object", "properties": {
                "date": {"type": "string"}, "task_name": {"type": "string"},
                "start_time": {"type": "string"}, "end_time": {"type": "string"},
            }, "required": ["date", "task_name", "start_time", "end_time"]},
        }},
        {"type": "function", "function": {
            "name": "validate_schedule",
            "description": "Проверить план на конфликты",
            "parameters": {"type": "object", "properties": {
                "plan": {"type": "array", "items": {"type": "object", "properties": {
                    "task": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"},
                }, "required": ["task", "start", "end"]}},
                "date": {"type": "string"},
            }, "required": ["plan"]},
        }},
        {"type": "function", "function": {
            "name": "get_date",
            "description": "Дата со смещением (0=сегодня)",
            "parameters": {"type": "object", "properties": {
                "offset_days": {"type": "integer"},
            }},
        }},
        {"type": "function", "function": {
            "name": "get_current_time",
            "description": "Текущие дата и время",
            "parameters": {"type": "object", "properties": {}},
        }},
    ]


class AgentState(TypedDict):
    tasks: List[dict]
    original_tasks: List[dict]
    messages: List[dict]
    plan: List[dict]
    plan_valid: bool
    plan_errors: List[str]
    tool_results: List[dict]
    iteration: int
    events_created: int


def execute_tool(tool_name: str, arguments: dict) -> ToolResult:
    tool = TOOLS_REGISTRY.get(tool_name)
    if tool is None:
        return ToolResult(False, error=f"Инструмент '{tool_name}' не найден")
    is_safe, error_msg = validate_tool_input(tool_name, arguments, security_cfg)
    if not is_safe:
        return ToolResult(False, error=f"Блокировка: {error_msg}")
    params = tool["params"]
    args = [arguments.get(p) for p in params]
    return tool["fn"](*args)


def llm_think(state: AgentState):
    messages = state["messages"]
    tasks_str = json.dumps(state["tasks"], ensure_ascii=False, indent=2)
    system_msg = SYSTEM_PROMPT.format(tasks=tasks_str)
    response = client.chat.completions.create(
        model=llm_cfg.model,
        messages=[{"role": "system", "content": system_msg}] + messages,
        tools=build_tools_spec(),
        tool_choice="auto",
        temperature=llm_cfg.temperature,
        max_tokens=llm_cfg.max_tokens,
    )
    msg = response.choices[0].message
    state["messages"].append({
        "role": "assistant", "content": msg.content or "",
        "tool_calls": msg.tool_calls if msg.tool_calls else None,
    })
    return state


def tool_execute(state: AgentState):
    last_msg = state["messages"][-1]
    tool_calls = last_msg.get("tool_calls") or []
    results = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            tool_name = tc["function"]["name"]
            tc_id = tc["id"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}
        else:
            tool_name = tc.function.name
            tc_id = tc.id
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

        if not rate_limiter.check():
            tool_content = json.dumps({"error": "Rate limit exceeded"})
            result = ToolResult(False, error="Rate limit exceeded")
        else:
            result = execute_tool(tool_name, args)
            metrics.record_tool_call(tool_name)
            if tool_name == "validate_schedule" and result.data:
                if result.data.get("valid"):
                    tool_content = f"Валидация пройдена. Расписание корректно для {result.data.get('date')}."
                else:
                    issues = result.data.get("issues", [])
                    tool_content = f"Найдены проблемы для {result.data.get('date')}:\n"
                    for issue in issues:
                        tool_content += f"  - {issue}\n"
                    tool_content += "\nИсправь расписание."
            else:
                tool_content = json.dumps(result.to_dict(), ensure_ascii=False)

        state["messages"].append({
            "role": "tool", "tool_call_id": tc_id, "content": tool_content,
        })

        if tool_name == "validate_schedule" and result.data:
            state["plan_valid"] = result.data.get("valid", False)
            state["plan_errors"] = result.data.get("issues", [])

        if tool_name == "create_event" and result.success:
            state["plan"].append(result.data)
            state["events_created"] = state.get("events_created", 0) + 1

        results.append({"tool": tool_name, "args": args})

    state["tool_results"] = results
    state["iteration"] = state.get("iteration", 0) + 1

    task_names = {t["name"] for t in state.get("original_tasks", state["tasks"])}
    created_names = {item.get("name") for item in state["plan"]}
    if task_names.issubset(created_names) or len(created_names) >= len(state.get("original_tasks", state["tasks"])):
        state["messages"].append({"role": "assistant", "content": "Все задачи размещены."})

    return state


builder = StateGraph(AgentState)
builder.add_node("think", llm_think)
builder.add_node("execute", tool_execute)
builder.set_entry_point("think")
builder.add_conditional_edges(
    "think",
    lambda s: "execute" if s["messages"][-1].get("tool_calls") else "end",
    {"execute": "execute", "end": END},
)
builder.add_conditional_edges(
    "execute",
    lambda s: "think" if s.get("iteration", 0) < agent_cfg.max_iterations else "end",
    {"think": "think", "end": END},
)
graph = builder.compile()


def run_agent(tasks: List[dict]) -> dict:
    if not use_llm or client is None:
        raise RuntimeError("Агент требует LLM. Убедитесь что OPENAI_API_KEY установлен.")

    start_time = time.time()

    valid, reason = guardrail_validate(tasks)
    if not valid:
        metrics.record_guardrail_rejection()
        metrics.record_error("guardrail_rejection")
        raise ValueError(f"Guardrail rejected input: {reason}")

    anonymized_tasks = anonymize_tasks(tasks) if security_cfg.anonymize_pii else tasks

    state: AgentState = {
        "tasks": anonymized_tasks,
        "original_tasks": tasks,
        "messages": [],
        "plan": [],
        "plan_valid": False,
        "plan_errors": [],
        "tool_results": [],
        "iteration": 0,
        "events_created": 0,
    }

    total_input_tokens = 0
    total_output_tokens = 0
    ttft = 0.0

    try:
        result = graph.invoke(state, config={"recursion_limit": agent_cfg.recursion_limit})
        e2e_time = time.time() - start_time

        for msg in result.get("messages", []):
            if msg.get("role") == "assistant" and msg.get("content"):
                safe, safe_reason = validate_llm_output(msg["content"])
                if not safe:
                    metrics.record_guardrail_rejection()
                    metrics.record_error("output_guardrail")

        quality = evaluate_plan_quality(tasks, result["plan"], [])
        cost_usd = (total_input_tokens * 0.0000025 + total_output_tokens * 0.000010)
        tpot = (e2e_time - ttft) / max(1, total_output_tokens) if total_output_tokens > 0 else 0

        metrics.record_run(
            success=bool(result["plan"]),
            tasks_total=len(tasks),
            tasks_placed=len(result["plan"]),
            e2e_time=e2e_time,
            plan_quality=quality.get("overall_score", 0),
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=cost_usd,
            ttft=ttft,
            tpot=tpot,
        )

        if langfuse:
            langfuse.trace(
                name="planner_run",
                input_data={"tasks": tasks},
                output_data={"plan": result["plan"], "quality": quality},
                metadata={
                    "response_time": e2e_time,
                    "iterations": result.get("iteration", 0),
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "cost_usd": cost_usd,
                },
            )
            langfuse.flush()

        return {
            "plan": result["plan"],
            "messages": result["messages"],
            "valid": result["plan_valid"],
            "errors": result["plan_errors"],
            "quality": quality,
            "response_time": round(e2e_time, 2),
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cost_usd": round(cost_usd, 6),
        }
    except Exception as e:
        metrics.record_error(type(e).__name__)
        raise


def print_plan(result: dict):
    plan = result.get("plan", [])
    if not plan:
        for msg in reversed(result.get("messages", [])):
            if msg.get("role") == "assistant" and msg.get("content"):
                if any(kw in msg["content"].lower() for kw in ["расписан", "план", "schedule"]):
                    print("\nОтвет агента:")
                    print(msg["content"])
                    return
    by_date = {}
    for item in plan:
        d = item.get("date", "unknown")
        by_date.setdefault(d, []).append(item)
    for d in sorted(by_date.keys()):
        events = by_date[d]
        print(f"\n{d}:")
        for item in events:
            name = item.get("name", item.get("task", "?"))
            start = item.get("start", "?")
            end = item.get("end", "?")
            print(f"  {start}--{end} - {name}")
    quality = result.get("quality", {})
    if quality:
        print(f"\nКачество: {quality.get('overall_score', 0):.1%}")
    if result.get("errors"):
        print("\nОшибки:")
        for e in result["errors"]:
            print(f"  - {e}")


if __name__ == "__main__":
    tasks = [
        {"name": "Подготовка отчета", "duration": 60, "deadline": "18:00"},
        {"name": "Изучение материалов", "duration": 90, "deadline": "20:00"},
        {"name": "Код-ревью", "duration": 45, "deadline": "17:00"},
    ]
    result = run_agent(tasks)
    print_plan(result)
