"""
Guardrails: валидация входных/выходных данных агента.
"""
import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional


PROMPT_INJECTION_PATTERNS = [
    r'ignore\s+(previous|above|all)\s+(instructions|rules|prompts)',
    r'(system|developer)\s*:\s*',
    r'you\s+are\s+now\s+',
    r'forget\s+(your|all)\s+(previous|prior)',
    r'(disregard|override)\s+(the\s+)?(previous|prior|system)',
    r'act\s+as\s+(a\s+)?(different|new|another)',
    r'(bypass|ignore|skip)\s+(safety|security|guardrails|restrictions)',
    r'(delete|drop|truncate|modify)\s+(the\s+)?(database|table|logs)',
    r'(execute|run)\s+(shell|command|code|script)',
    r'(admin|root|sudo|password|secret|api_key)\s*[=:]\s*',
]

INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]


class GuardrailResult:
    def __init__(self, passed: bool, severity: str, reason: str):
        self.passed = passed
        self.severity = severity
        self.reason = reason

    def to_dict(self):
        return {
            "passed": self.passed,
            "severity": self.severity,
            "reason": self.reason,
        }


class TaskInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    duration: int = Field(..., gt=0, le=1440)
    deadline: str = Field(..., pattern=r'^\d{2}:\d{2}$')

    @field_validator('name')
    @classmethod
    def name_no_injection(cls, v: str) -> str:
        for pattern in INJECTION_RE:
            if pattern.search(v):
                raise ValueError(f"Обнаружен prompt injection в имени задачи: {v[:50]}")
        return v


def check_prompt_injection(text: str) -> GuardrailResult:
    """Проверить текст на prompt injection."""
    for pattern in INJECTION_RE:
        match = pattern.search(text)
        if match:
            return GuardrailResult(
                passed=False,
                severity="high",
                reason=f"Prompt injection pattern: '{match.group()[:50]}'"
            )
    return GuardrailResult(passed=True, severity="none", reason="OK")


def check_output_safety(text: str) -> GuardrailResult:
    """Проверить выходной ответ LLM на безопасность."""
    dangerous_patterns = [
        (r'rm\s+-rf', "Dangerous command: rm -rf"),
        (r'drop\s+table', "SQL injection: DROP TABLE"),
        (r'delete\s+from', "SQL injection: DELETE FROM"),
        (r'<script', "XSS attempt"),
        (r'javascript:', "XSS attempt"),
    ]
    for pattern, desc in dangerous_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return GuardrailResult(
                passed=False, severity="critical", reason=desc
            )
    return GuardrailResult(passed=True, severity="none", reason="OK")


def validate_task_input(tasks: list) -> tuple[bool, str]:
    """Валидировать входные задачи через Pydantic + injection check."""
    for i, task in enumerate(tasks):
        try:
            TaskInput(**task)
        except Exception as e:
            return False, f"Задача {i}: {e}"
        inj = check_prompt_injection(task.get("name", ""))
        if not inj.passed:
            return False, inj.reason
    return True, ""


def validate_llm_output(text: str) -> tuple[bool, str]:
    """Валидировать ответ LLM."""
    if not text:
        return False, "Empty response"
    safety = check_output_safety(text)
    if not safety.passed:
        return False, safety.reason
    return True, ""
