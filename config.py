"""
Конфигурация AI Day Planner Agent.

Продуктовая логика:
- Цель: автоматически планировать задачи пользователя в календаре
- Метрика успеха: процент успешно размещённых задач без конфликтов
- Ограничения: не создавать события в прошлом, не пересекать существующие события
"""
import os
from dataclasses import dataclass, field


@dataclass
class ProductConfig:
    """Продуктовая конфигурация агента."""
    name: str = "AI Day Planner Agent"
    version: str = "1.0.0"
    description: str = "Автоматическое планирование задач с учётом календаря"
    
    success_metric: str = "task_placement_rate"
    target_metric_value: float = 0.90
    eval_sample_size: int = 50


@dataclass
class LLMConfig:
    """Конфигурация LLM."""
    api_key: str = ""
    base_url: str = ""
    model: str = "openai/gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: float = 30.0
    max_retries: int = 3


@dataclass
class AgentConfig:
    """Конфигурация агента."""
    max_iterations: int = 25
    recursion_limit: int = 150
    max_validation_attempts: int = 2
    default_start_hour: int = 0
    default_end_hour: int = 23


@dataclass
class SecurityConfig:
    """Конфигурация безопасности."""
    anonymize_pii: bool = True
    pii_patterns: list = field(default_factory=lambda: [
        "phone", "email", "passport", "сник", "карт", "паспорт", "телефон"
    ])
    max_calendar_events_read: int = 500
    rate_limit_per_minute: int = 10


@dataclass
class LangfuseConfig:
    """Конфигурация Langfuse мониторинга."""
    enabled: bool = False
    host: str = "http://localhost:3000"
    public_key: str = ""
    secret_key: str = ""


def load_config() -> dict:
    """Загрузить конфигурацию из .env и вернуть все секции."""
    from dotenv import load_dotenv
    load_dotenv()

    llm = LLMConfig(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_URL", ""),
        model=os.getenv("OPENAI_MODEL", "openai/gpt-4o"),
    )

    langfuse = LangfuseConfig(
        enabled=bool(os.getenv("LANGFUSE_HOST")),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
    )

    return {
        "product": ProductConfig(),
        "llm": llm,
        "agent": AgentConfig(),
        "security": SecurityConfig(),
        "langfuse": langfuse,
    }
