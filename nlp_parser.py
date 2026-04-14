"""
NLP парсер запросов пользователя.
Превращает естественный язык в структурированные задачи.
"""
import datetime as dt
import json
import re
from typing import List, Optional


TIME_KEYWORDS = {
    "утром": {"start": "09:00", "end": "12:00", "duration": 60},
    "утренн": {"start": "09:00", "end": "12:00", "duration": 60},
    "днём": {"start": "13:00", "end": "16:00", "duration": 60},
    "днем": {"start": "13:00", "end": "16:00", "duration": 60},
    "после обеда": {"start": "14:00", "end": "17:00", "duration": 60},
    "вечером": {"start": "18:00", "end": "21:00", "duration": 60},
    "вечерн": {"start": "18:00", "end": "21:00", "duration": 60},
    "ночью": {"start": "21:00", "end": "23:00", "duration": 60},
}

DAY_KEYWORDS = {
    "сегодня": 0,
    "завтра": 1,
    "послезавтра": 2,
}

DURATION_KEYWORDS = {
    "час": 60,
    "полчаса": 30,
    "пол часа": 30,
    "два часа": 120,
    "три часа": 180,
    "15 минут": 15,
    "30 минут": 30,
    "45 минут": 45,
    "90 минут": 90,
}


def _detect_date(text: str) -> str:
    """Определить целевую дату из текста."""
    lower = text.lower()
    today = dt.datetime.now(dt.timezone.utc).astimezone(
        dt.timezone(dt.timedelta(hours=3))
    )
    # Проверка в правильном порядке (длинные ключевые слова первые)
    for keyword in sorted(DAY_KEYWORDS.keys(), key=len, reverse=True):
        if keyword in lower:
            offset = DAY_KEYWORDS[keyword]
            target = today + dt.timedelta(days=offset)
            return target.strftime("%Y-%m-%d")
    # По умолчанию завтра
    target = today + dt.timedelta(days=1)
    return target.strftime("%Y-%m-%d")


def extract_tasks_from_text(text: str, client) -> List[dict]:
    """Извлечь задачи из текста пользователя через LLM."""
    if client is None:
        return []

    target_date = _detect_date(text)

    prompt = f"""Извлеки задачи из запроса пользователя. Верни JSON массив.

Правила:
- Каждая задача: {{"name": "...", "duration": минут_числом, "deadline": "HH:MM", "preferred_time": "утро/день/вечер/любое", "suggested_start": "HH:MM", "target_date": "YYYY-MM-DD"}}
- suggested_start — конкретное время начала. "утром" → 09:00, "днём" → 13:00, "вечером" → 18:00.
- target_date: "{target_date}" (определено из текста). Используй эту дату для всех задач.
- Если длительность не указана — оцени сам
- preferred_time: "утро" (09-12), "день" (13-17), "вечер" (18-22), "любое"
- deadline: "23:59" если не указан явно
- Извлекай ВСЕ активности: спорт, встречи, личные дела

Примеры:
"Хочу завтра утром сходить на теннис" → [{{"name":"Теннис","duration":60,"deadline":"23:59","preferred_time":"утро","suggested_start":"09:00","target_date":"{target_date}"}}]
"Завтра днем гуляю с подругой" → [{{"name":"Гулять с подругой","duration":120,"deadline":"23:59","preferred_time":"день","suggested_start":"13:00","target_date":"{target_date}"}}]

Запрос: {text}

Верни ТОЛЬКО JSON массив, без markdown."""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        content = response.choices[0].message.content

        # Извлечь JSON
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            tasks = json.loads(match.group(0))
            # Добавить target_date если LLM не вернул
            for task in tasks:
                if "target_date" not in task:
                    task["target_date"] = target_date
            return tasks
        return []
    except Exception:
        return []
