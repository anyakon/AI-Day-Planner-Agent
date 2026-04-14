"""
Система оценки качества (evals).

Оценивает качество планировки по нескольким метрикам:
- task_placement_rate: доля задач которые удалось разместить
- no_overlaps: нет ли пересечений в расписании
- deadline_respect: соблюдены ли дедлайны
- time_efficiency: насколько плотно заполнено время
"""
from typing import Any


def evaluate_plan_quality(
    tasks: list[dict],
    plan: list[dict],
    events: list[dict],
) -> dict[str, float]:
    """Оценить качество планировки.
    
    Returns:
        dict с метриками качества (0.0 - 1.0)
    """
    if not tasks:
        return {
            "task_placement_rate": 0.0,
            "no_overlaps": 1.0,
            "deadline_respect": 1.0,
            "time_efficiency": 0.0,
            "overall_score": 0.0,
        }

    results = {
        "task_placement_rate": _eval_placement_rate(tasks, plan),
        "no_overlaps": _eval_no_overlaps(plan, events),
        "deadline_respect": _eval_deadlines(tasks, plan),
        "time_efficiency": _eval_time_efficiency(plan),
    }

    weights = {
        "task_placement_rate": 0.35,
        "no_overlaps": 0.30,
        "deadline_respect": 0.25,
        "time_efficiency": 0.10,
    }

    results["overall_score"] = sum(
        results[k] * weights[k] for k in weights
    )

    return {k: round(v, 3) for k, v in results.items()}


def _eval_placement_rate(tasks: list, plan: list) -> float:
    """Доля задач которые удалось разместить."""
    if not tasks:
        return 1.0
    task_names = {t["name"] for t in tasks}
    placed_names = {p.get("name", p.get("task")) for p in plan if p.get("name") or p.get("task")}
    return len(task_names & placed_names) / len(task_names)


def _eval_no_overlaps(plan: list, events: list) -> float:
    """Нет ли пересечений в расписании."""
    if len(plan) < 2:
        return 1.0

    def to_min(t: str) -> int:
        h, m = map(int, t.split(":"))
        return h * 60 + m

    violations = 0
    all_items = []
    for p in plan:
        s = p.get("start")
        e = p.get("end")
        if s and e:
            all_items.append((to_min(s), to_min(e), "plan"))
    for ev in events:
        s = ev.get("start")
        e = ev.get("end")
        if s and e:
            all_items.append((to_min(s), to_min(e), "event"))

    all_items.sort()
    for i in range(len(all_items) - 1):
        if all_items[i][1] > all_items[i + 1][0]:
            violations += 1

    total_pairs = max(1, len(all_items) - 1)
    return 1.0 - (violations / total_pairs)


def _eval_deadlines(tasks: list, plan: list) -> float:
    """Соблюдены ли дедлайны."""
    if not tasks:
        return 1.0

    def to_min(t: str) -> int:
        h, m = map(int, t.split(":"))
        return h * 60 + m

    violations = 0
    checked = 0
    for task in tasks:
        deadline = task.get("deadline")
        if not deadline:
            continue
        checked += 1
        deadline_min = to_min(deadline)
        task_name = task["name"]
        for p in plan:
            if p.get("name") == task_name or p.get("task") == task_name:
                end = p.get("end")
                if end and to_min(end) > deadline_min:
                    violations += 1
                break

    return 1.0 - (violations / max(1, checked))


def _eval_time_efficiency(plan: list) -> float:
    """Насколько плотно заполнено время (без больших пробелов)."""
    if len(plan) < 2:
        return 0.5

    def to_min(t: str) -> int:
        h, m = map(int, t.split(":"))
        return h * 60 + m

    sorted_plan = sorted(plan, key=lambda p: to_min(p.get("start", "00:00")))
    gaps = []
    for i in range(len(sorted_plan) - 1):
        end = to_min(sorted_plan[i].get("end", "00:00"))
        start = to_min(sorted_plan[i + 1].get("start", "00:00"))
        if start > end:
            gaps.append(start - end)

    if not gaps:
        return 1.0

    avg_gap = sum(gaps) / len(gaps)
    return max(0.0, min(1.0, 1.0 - (avg_gap / 120)))
