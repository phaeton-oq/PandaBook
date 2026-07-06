"""LLM layer via Cerebras (gpt-oss-120b, OpenAI-compatible).

Powers the "Думающий" (Pro) mode: recipe generation and ration explanations,
using reasoning_effort to literally make the model think harder. Every call
degrades gracefully (missing key / network error) so the app never breaks.
"""
from __future__ import annotations

import json

import httpx

from app.config import settings
from app.schemas import Recipe

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


class _LLMError(Exception):
    pass


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
        return resp.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError) as e:
        raise _LLMError(str(e)) from e


def suggest_recipe(ingredients: list[str], effort: str = "high") -> Recipe:
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


def explain_plan(summary: str, effort: str = "high") -> str:
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
