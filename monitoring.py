"""
Мониторинг: детальные метрики + Prometheus endpoint.

Метрики:
- total_runs, successful_runs, failed_runs
- task_placement_rate, success_rate
- latency: avg, p50, p95 (e2e)
- time_to_first_token (TTFT)
- time_per_output_token (TPOT)
- total_input_tokens, total_output_tokens
- total_cost_usd
- tool_call_counts, error_counts
- guardrail_rejections
"""
import time
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
from typing import List, Optional


METRICS_FILE = Path(__file__).parent / "metrics.json"


@dataclass
class LatencyTracker:
    """Трекинг латентности с перцентилями."""
    values: List[float] = field(default_factory=list)

    def add(self, value: float):
        self.values.append(value)
        if len(self.values) > 10000:
            self.values = self.values[-5000:]

    @property
    def avg(self) -> float:
        return sum(self.values) / max(1, len(self.values))

    @property
    def p50(self) -> float:
        if not self.values:
            return 0.0
        s = sorted(self.values)
        return s[len(s) // 2]

    @property
    def p95(self) -> float:
        if not self.values:
            return 0.0
        s = sorted(self.values)
        idx = int(math.ceil(0.95 * len(s))) - 1
        return s[max(0, idx)]

    @property
    def count(self) -> int:
        return len(self.values)


@dataclass
class AgentMetrics:
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_tasks: int = 0
    placed_tasks: int = 0
    failed_tasks: int = 0
    avg_plan_quality: float = 0.0
    tool_call_counts: dict = field(default_factory=dict)
    error_counts: dict = field(default_factory=dict)
    guardrail_rejections: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    e2e_latency: LatencyTracker = field(default_factory=LatencyTracker)
    ttft_values: LatencyTracker = field(default_factory=LatencyTracker)
    tpot_values: LatencyTracker = field(default_factory=LatencyTracker)
    ttft: float = 0.0
    tpot: float = 0.0

    @property
    def task_placement_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.placed_tasks / self.total_tasks

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.successful_runs / self.total_runs

    @property
    def avg_tokens_per_run(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return (self.total_input_tokens + self.total_output_tokens) / self.total_runs

    def to_dict(self) -> dict:
        return {
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "total_tasks": self.total_tasks,
            "placed_tasks": self.placed_tasks,
            "failed_tasks": self.failed_tasks,
            "task_placement_rate": round(self.task_placement_rate, 3),
            "success_rate": round(self.success_rate, 3),
            "avg_plan_quality": round(self.avg_plan_quality, 3),
            "guardrail_rejections": self.guardrail_rejections,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "avg_tokens_per_run": round(self.avg_tokens_per_run, 1),
            "e2e_latency": {
                "avg": round(self.e2e_latency.avg, 3),
                "p50": round(self.e2e_latency.p50, 3),
                "p95": round(self.e2e_latency.p95, 3),
                "count": self.e2e_latency.count,
            },
            "time_to_first_token": {
                "avg": round(self.ttft_values.avg, 3),
                "p50": round(self.ttft_values.p50, 3),
                "p95": round(self.ttft_values.p95, 3),
                "count": self.ttft_values.count,
            },
            "time_per_output_token": {
                "avg": round(self.tpot_values.avg, 3),
                "p50": round(self.tpot_values.p50, 3),
                "p95": round(self.tpot_values.p95, 3),
                "count": self.tpot_values.count,
            },
            "tool_call_counts": self.tool_call_counts,
            "error_counts": self.error_counts,
        }


class MetricsCollector:
    """Сборщик метрик с сохранением в файл."""

    def __init__(self, metrics_file: Path = METRICS_FILE):
        self.metrics_file = metrics_file
        self.metrics = self._load()

    def _load(self) -> AgentMetrics:
        if self.metrics_file.exists():
            try:
                data = json.loads(self.metrics_file.read_text(encoding="utf-8"))
                m = AgentMetrics()
                skip = {"task_placement_rate", "success_rate", "avg_tokens_per_run",
                        "e2e_latency", "time_to_first_token", "time_per_output_token"}
                for k, v in data.items():
                    if k not in skip and hasattr(m, k):
                        if isinstance(v, dict) and k in ("tool_call_counts", "error_counts"):
                            setattr(m, k, v)
                        elif isinstance(v, (int, float)):
                            setattr(m, k, v)
                return m
            except Exception:
                pass
        return AgentMetrics()

    def _save(self):
        self.metrics_file.write_text(
            json.dumps(self.metrics.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record_run(self, success: bool, tasks_total: int, tasks_placed: int,
                   e2e_time: float, plan_quality: float = 0.0,
                   input_tokens: int = 0, output_tokens: int = 0,
                   cost_usd: float = 0.0, ttft: float = 0.0,
                   tpot: float = 0.0):
        m = self.metrics
        m.total_runs += 1
        if success:
            m.successful_runs += 1
        else:
            m.failed_runs += 1
        m.total_tasks += tasks_total
        m.placed_tasks += tasks_placed
        m.failed_tasks += max(0, tasks_total - tasks_placed)
        m.avg_plan_quality = (
            (m.avg_plan_quality * (m.total_runs - 1) + plan_quality) / m.total_runs
        )
        m.total_input_tokens += input_tokens
        m.total_output_tokens += output_tokens
        m.total_cost_usd += cost_usd
        m.e2e_latency.add(e2e_time)
        if ttft > 0:
            m.ttft_values.add(ttft)
        if tpot > 0:
            m.tpot_values.add(tpot)
        self._save()

    def record_tool_call(self, tool_name: str):
        counts = self.metrics.tool_call_counts
        counts[tool_name] = counts.get(tool_name, 0) + 1
        self._save()

    def record_error(self, error_type: str):
        counts = self.metrics.error_counts
        counts[error_type] = counts.get(error_type, 0) + 1
        self._save()

    def record_guardrail_rejection(self):
        self.metrics.guardrail_rejections += 1
        self._save()

    def get_metrics(self) -> dict:
        return self.metrics.to_dict()

    def get_prometheus_text(self) -> str:
        """Формат для Prometheus text exposition."""
        m = self.metrics
        lines = [
            f"# HELP agent_total_runs Total number of agent runs",
            f"# TYPE agent_total_runs counter",
            f"agent_total_runs {m.total_runs}",
            f"# HELP agent_successful_runs Successful runs",
            f"# TYPE agent_successful_runs counter",
            f"agent_successful_runs {m.successful_runs}",
            f"# HELP agent_failed_runs Failed runs",
            f"# TYPE agent_failed_runs counter",
            f"agent_failed_runs {m.failed_runs}",
            f"# HELP agent_task_placement_rate Fraction of tasks placed",
            f"# TYPE agent_task_placement_rate gauge",
            f"agent_task_placement_rate {m.task_placement_rate:.4f}",
            f"# HELP agent_success_rate Fraction of successful runs",
            f"# TYPE agent_success_rate gauge",
            f"agent_success_rate {m.success_rate:.4f}",
            f"# HELP agent_avg_plan_quality Average plan quality",
            f"# TYPE agent_avg_plan_quality gauge",
            f"agent_avg_plan_quality {m.avg_plan_quality:.4f}",
            f"# HELP agent_e2e_latency_avg E2E latency average (seconds)",
            f"# TYPE agent_e2e_latency_avg gauge",
            f"agent_e2e_latency_avg {m.e2e_latency.avg:.4f}",
            f"# HELP agent_e2e_latency_p50 E2E latency p50 (seconds)",
            f"# TYPE agent_e2e_latency_p50 gauge",
            f"agent_e2e_latency_p50 {m.e2e_latency.p50:.4f}",
            f"# HELP agent_e2e_latency_p95 E2E latency p95 (seconds)",
            f"# TYPE agent_e2e_latency_p95 gauge",
            f"agent_e2e_latency_p95 {m.e2e_latency.p95:.4f}",
            f"# HELP agent_ttft_avg Time to first token avg (seconds)",
            f"# TYPE agent_ttft_avg gauge",
            f"agent_ttft_avg {m.ttft_values.avg:.4f}",
            f"# HELP agent_ttft_p95 Time to first token p95 (seconds)",
            f"# TYPE agent_ttft_p95 gauge",
            f"agent_ttft_p95 {m.ttft_values.p95:.4f}",
            f"# HELP agent_tpot_avg Time per output token avg (seconds)",
            f"# TYPE agent_tpot_avg gauge",
            f"agent_tpot_avg {m.tpot_values.avg:.4f}",
            f"# HELP agent_tpot_p95 Time per output token p95 (seconds)",
            f"# TYPE agent_tpot_p95 gauge",
            f"agent_tpot_p95 {m.tpot_values.p95:.4f}",
            f"# HELP agent_total_input_tokens Total input tokens",
            f"# TYPE agent_total_input_tokens counter",
            f"agent_total_input_tokens {m.total_input_tokens}",
            f"# HELP agent_total_output_tokens Total output tokens",
            f"# TYPE agent_total_output_tokens counter",
            f"agent_total_output_tokens {m.total_output_tokens}",
            f"# HELP agent_total_cost_usd Total cost in USD",
            f"# TYPE agent_total_cost_usd counter",
            f"agent_total_cost_usd {m.total_cost_usd:.6f}",
            f"# HELP agent_guardrail_rejections Guardrail rejections",
            f"# TYPE agent_guardrail_rejections counter",
            f"agent_guardrail_rejections {m.guardrail_rejections}",
        ]
        for tool, count in m.tool_call_counts.items():
            lines.append(
                f'agent_tool_calls_total{{tool="{tool}"}} {count}'
            )
        lines.insert(len(lines) - len(m.tool_call_counts),
                     "# HELP agent_tool_calls_total Tool calls by name")
        lines.insert(len(lines) - len(m.tool_call_counts) + 1,
                     "# TYPE agent_tool_calls_total counter")

        for err, count in m.error_counts.items():
            lines.append(
                f'agent_errors_total{{type="{err}"}} {count}'
            )
        if m.error_counts:
            lines.insert(len(lines) - len(m.error_counts),
                         "# HELP agent_errors_total Errors by type")
            lines.insert(len(lines) - len(m.error_counts) + 1,
                         "# TYPE agent_errors_total counter")

        return "\n".join(lines) + "\n"


class LangfuseTracker:
    """Интеграция с Langfuse для трейсинга (SDK v3)."""

    def __init__(self, host: str, public_key: str, secret_key: str):
        self.enabled = True
        self.host = host
        try:
            from langfuse import Langfuse
            self.langfuse = Langfuse(
                host=host,
                public_key=public_key,
                secret_key=secret_key,
            )
            ok = self.langfuse.auth_check()
            if ok:
                print(f"Langfuse подключён: {host}")
            else:
                print("Langfuse auth failed")
                self.enabled = False
        except Exception as e:
            print(f"Langfuse не подключён: {e}")
            self.enabled = False

    def trace(self, name: str, input_data: dict, output_data: dict,
              metadata: dict = None):
        if not self.enabled:
            return
        try:
            with self.langfuse.start_as_current_observation(
                name=name,
                as_type="agent",
                input=input_data,
                output=output_data,
                metadata=metadata or {},
            ):
                pass
        except Exception as e:
            print(f"Langfuse ошибка: {e}")

    def flush(self):
        if self.enabled:
            try:
                self.langfuse.flush()
            except Exception:
                pass
