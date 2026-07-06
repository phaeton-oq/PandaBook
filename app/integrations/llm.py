"""ИИ PandaBook — рецепты, объяснения рациона и список докупок.

Работает в режиме «Думающий» (Pro). При недоступности сервиса приложение
не падает: отдаёт алгоритмический fallback.
"""
from __future__ import annotations

import json
import re

import httpx

from app.config import settings
from app.schemas import Recipe, ShoppingItem

_RECIPE_SYSTEM = (
    "Ты шеф-повар. По списку продуктов предложи ОДИН вариант приёма пищи. "
    "Если это сырые ингредиенты — дай рецепт блюда. Если продукты уже готовые "
    "(суп, борщ, консервы, полуфабрикаты) — предложи, как их удобно скомбинировать "
    "и подать, без лишних шагов. Не добавляй продукты, которых нет в списке "
    "(допустимы только базовые специи, соль, масло, вода). Верни СТРОГО JSON без "
    'markdown по схеме: {"title": строка, "ingredients": [строки], "steps": [строки]}. '
    "Пиши по-русски."
)
_EXPLAIN_SYSTEM = (
    "Ты персональный диетолог. Объясни коротко (2-3 предложения, простым языком, "
    "без markdown), почему составленный рацион подходит под цель пользователя. "
    "Если пользователь оставил пожелание — учти его в ответе."
)
_SHOPPING_SYSTEM = (
    "Ты персональный диетолог и помощник по закупкам. Составь список докупок на ОДИН день.\n\n"
    "СТРОГИЕ ПРАВИЛА:\n"
    "1. Верни ТОЛЬКО JSON без markdown: "
    '{"items":[{"product_name":"...","grams":123,"reason":"..."}]}\n'
    "2. product_name — конкретный продукт из обычного российского магазина.\n"
    "3. grams — целое число граммов (не штуки, не упаковки).\n"
    "4. reason — одно короткое предложение: зачем именно этот продукт (дефицит макроса, "
    "замена скоропортящемуся, разнообразие и т.д.).\n"
    "5. Учитывай цель (похудеть/поддерживать/набрать), диет-ограничения и аллергены.\n"
    "6. ЗАПРЕЩЕНО включать продукты из блока «УЖЕ ЕСТЬ В ХОЛОДИЛЬНИКЕ» — даже под другим названием.\n"
    "7. Докупай только то, чего нет дома, чтобы дополнить рацион и закрыть дефицит.\n"
    "8. Если дома уже есть макароны/каша/рис — НЕ докупай углеводы; предложи белок, овощи и жиры К НИМ.\n"
    "9. Подстраивайся под реальное содержимое холодильника, а не выдавай один и тот же шаблон.\n"
    "10. От 1 до 6 позиций. Если докупать нечего — {\"items\":[]}.\n"
    "11. Пиши по-русски. Только реалистичные продукты из обычного магазина."
)


class _LLMError(Exception):
    pass


def _extract_json_content(msg: dict) -> str:
    """Some providers return JSON only in a reasoning field — recover it."""
    content = (msg.get("content") or "").strip()
    if content:
        return content
    reasoning = msg.get("reasoning") or ""
    for pattern in (
        r'\{"items"\s*:\s*\[\s*\]\s*\}',
        r'\{"items"\s*:\s*\[.*?\]\s*\}',
        r'\{"title"\s*:.*?"steps"\s*:\s*\[.*?\]\s*\}',
    ):
        matches = re.findall(pattern, reasoning, flags=re.DOTALL)
        if matches:
            return matches[-1]
    return ""


def _plain_text_content(msg: dict) -> str:
    content = (msg.get("content") or "").strip()
    if content:
        return content
    reasoning = (msg.get("reasoning") or "").strip()
    if not reasoning:
        return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n", reasoning) if p.strip()]
    for part in reversed(parts):
        if len(part) > 30 and not re.match(r"^(We |The user|The |I need|Let me)", part):
            return part[:2000]
    return reasoning[-1500:].strip()


def _chat(messages: list[dict], *, effort: str = "high",
          max_tokens: int = 1500, json_mode: bool = False) -> str:
    if not settings.LLM_API_KEY:
        raise _LLMError("no api key")
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "reasoning_effort": effort,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        resp = httpx.post(
            f"{settings.LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        content = _extract_json_content(msg) if json_mode else _plain_text_content(msg)
        if not content:
            raise _LLMError("empty model content")
        return content
    except (httpx.HTTPError, KeyError) as e:
        raise _LLMError(str(e)) from e


def suggest_recipe(ingredients: list[str], effort: str = "low") -> Recipe:
    try:
        content = _chat(
            [
                {"role": "system", "content": _RECIPE_SYSTEM},
                {"role": "user", "content": "Ингредиенты: " + ", ".join(ingredients)},
            ],
            effort=effort, max_tokens=2000, json_mode=True,
        )
        data = json.loads(content)
        return Recipe(
            title=data.get("title", "Рецепт"),
            ingredients=data.get("ingredients", ingredients),
            steps=data.get("steps", []),
        )
    except (_LLMError, json.JSONDecodeError):
        return Recipe(title="Рецепт временно недоступен", ingredients=ingredients, steps=[])


def explain_plan(summary: str, effort: str = "low") -> str:
    try:
        return _chat(
            [
                {"role": "system", "content": _EXPLAIN_SYSTEM},
                {"role": "user", "content": summary},
            ],
            effort=effort, max_tokens=1500,
        ).strip()
    except _LLMError:
        return ""


def suggest_shopping_list(context: str, effort: str = "low") -> list[ShoppingItem] | None:
    """ИИ shopping list; returns None on failure so caller can fall back."""
    try:
        content = _chat(
            [
                {"role": "system", "content": _SHOPPING_SYSTEM},
                {"role": "user", "content": context},
            ],
            effort=effort, max_tokens=1200, json_mode=True,
        )
        data = json.loads(content)
        items = data.get("items", [])
        out: list[ShoppingItem] = []
        for raw in items:
            name = str(raw.get("product_name", "")).strip()
            grams = float(raw.get("grams", 0))
            reason = str(raw.get("reason", "")).strip()
            if name and grams > 0 and reason:
                out.append(ShoppingItem(
                    product_name=name,
                    grams=round(grams),
                    reason=reason,
                ))
        return out
    except (_LLMError, json.JSONDecodeError, TypeError, ValueError):
        return None
