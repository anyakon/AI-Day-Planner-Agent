"""
Безопасность: анонимизация персональных данных и защита инструментов.
"""
import re
from typing import Any


PII_REPLACEMENTS = [
    (r'\b\d{10,}\b', '[CARD_REDACTED]'),
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD_REDACTED]'),
    (r'\b\d{10}\b', '[PASSPORT_REDACTED]'),
    (r'\b\+7[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b', '[PHONE_REDACTED]'),
    (r'\b\d{11}\b', '[PHONE_REDACTED]'),
    (r'[\w.+-]+@[\w-]+\.[\w.-]+', '[EMAIL_REDACTED]'),
]

RUSSIAN_PII_KEYWORDS = [
    "телефон", "phone", "email", "почта", "паспорт", "passport",
    "карта", "card", "снилс", "инн", "адрес", "address",
]


def anonymize_text(text: str) -> str:
    """Анонимизировать PII в тексте."""
    result = text
    for pattern, replacement in PII_REPLACEMENTS:
        result = re.sub(pattern, replacement, result)
    return result


def anonymize_tasks(tasks: list) -> list:
    """Анонимизировать задачи пользователя перед отправкой в LLM."""
    anonymized = []
    for task in tasks:
        clean_task = {}
        for key, value in task.items():
            if isinstance(value, str):
                clean_task[key] = anonymize_text(value)
            else:
                clean_task[key] = value
        anonymized.append(clean_task)
    return anonymized


def sanitize_tool_result(result: dict) -> dict:
    """Очистить результат инструмента от чувствительных данных."""
    sanitized = {}
    for key, value in result.items():
        if isinstance(value, str):
            sanitized[key] = anonymize_text(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_tool_result(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_tool_result(item) if isinstance(item, dict)
                else anonymize_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def validate_tool_input(tool_name: str, arguments: dict, security_config: dict) -> tuple[bool, str]:
    """Проверить входные данные инструмента на безопасность.
    
    Returns:
        (is_safe, error_message)
    """
    for key, value in arguments.items():
        if isinstance(value, str):
            for keyword in RUSSIAN_PII_KEYWORDS:
                if keyword.lower() in value.lower():
                    return False, f"Обнаружен потенциальный PII в параметре '{key}' инструмента '{tool_name}'"
    return True, ""


class RateLimiter:
    """Простой rate limiter на основе счётчика."""
    
    def __init__(self, max_calls: int, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls = []
    
    def check(self) -> bool:
        """Проверить, можно ли выполнить запрос."""
        import time
        now = time.time()
        self._calls = [t for t in self._calls if now - t < self.window_seconds]
        if len(self._calls) >= self.max_calls:
            return False
        self._calls.append(now)
        return True
