"""
AI Day Planner Agent API.
FastAPI server with REST endpoints.
"""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional

from planner import run_agent, client, use_llm
from nlp_parser import extract_tasks_from_text
from monitoring import MetricsCollector

app = FastAPI(title="AI Day Planner Agent")


class TaskInput(BaseModel):
    name: str
    duration: int
    deadline: str


class PlanRequest(BaseModel):
    tasks: List[TaskInput]


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat_plan(req: ChatRequest):
    """Принимает текстовый запрос, парсит в задачи, планирует."""
    if not use_llm or client is None:
        raise HTTPException(status_code=500, detail="LLM недоступен")

    tasks = extract_tasks_from_text(req.message, client)
    if not tasks:
        raise HTTPException(status_code=400, detail="Не удалось извлечь задачи из запроса")

    try:
        result = run_agent(tasks)
        return {
            "parsed_tasks": tasks,
            "plan": result["plan"],
            "quality": result.get("quality", {}),
            "response_time": result.get("response_time", 0),
            "valid": result.get("valid", False),
            "errors": result.get("errors", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan")
async def create_plan(req: PlanRequest):
    tasks = [{"name": t.name, "duration": t.duration, "deadline": t.deadline} for t in req.tasks]
    try:
        result = run_agent(tasks)
        return {
            "plan": result["plan"],
            "quality": result.get("quality", {}),
            "response_time": result.get("response_time", 0),
            "valid": result.get("valid", False),
            "errors": result.get("errors", []),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cost_usd": result.get("cost_usd", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics")
async def get_metrics():
    m = MetricsCollector()
    return m.get_metrics()


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus text exposition format."""
    m = MetricsCollector()
    return Response(content=m.get_prometheus_text(), media_type="text/plain")


@app.get("/")
async def root():
    return {"status": "ok", "endpoints": ["/api/chat", "/api/plan", "/api/metrics", "/metrics"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
