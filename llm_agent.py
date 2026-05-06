import os
import time
from google import genai
from google.genai import types

from functions import (
    get_recipes_by_ingredients,
    filter_recipes,
    generate_recipe,
    modify_recipe,
    estimate_calories,
    suggest_substitutes,
)

SYSTEM_PROMPT = """Ти — кулінарний асистент. Допомагаєш знаходити рецепти, генерувати нові та адаптувати існуючі.
Відповідай лише українською мовою. Не вигадуй рецепти без виклику інструментів.

Правила:
- Користувач перераховує інгредієнти → виклич get_recipes_by_ingredients
- База повернула порожній список (found: 0) → виклич generate_recipe з тими самими інгредієнтами
- Є дієтичні або часові обмеження → виклич filter_recipes (можна після пошуку)
- Користувач хоче змінити конкретний рецепт → виклич modify_recipe
- Запитують про калорії → виклич estimate_calories
- Користувач каже що немає якогось інгредієнта, або питає чим замінити → виклич suggest_substitutes
- Якщо рецепт знайдено але в ньому є інгредієнти яких немає у користувача → виклич suggest_substitutes

Форматуй рецепти зручно: назва жирним, інгредієнти списком, кроки нумеровані."""

TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="get_recipes_by_ingredients",
        description="Шукає рецепти за списком наявних інгредієнтів.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"ingredients": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Список інгредієнтів")},
            required=["ingredients"],
        ),
    ),
    types.FunctionDeclaration(
        name="filter_recipes",
        description="Фільтрує рецепти за обмеженнями: веган, без глютену, швидке, сніданок тощо.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "recipe_ids": types.Schema(type="ARRAY", items=types.Schema(type="INTEGER"), description="ID рецептів (порожній = всі)"),
                "constraints": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Обмеження: ['веган', 'без глютену']"),
            },
            required=["constraints"],
        ),
    ),
    types.FunctionDeclaration(
        name="generate_recipe",
        description="Генерує новий рецепт з наданих інгредієнтів, коли в базі нічого не знайдено.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"ingredients": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Інгредієнти для нового рецепту")},
            required=["ingredients"],
        ),
    ),
    types.FunctionDeclaration(
        name="modify_recipe",
        description="Модифікує існуючий рецепт відповідно до побажань користувача.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "recipe_id": types.Schema(type="INTEGER", description="ID рецепту з бази"),
                "changes": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Список змін"),
            },
            required=["recipe_id", "changes"],
        ),
    ),
    types.FunctionDeclaration(
        name="estimate_calories",
        description="Оцінює калорійність страви за списком інгредієнтів.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"ingredients": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Список інгредієнтів страви")},
            required=["ingredients"],
        ),
    ),
    types.FunctionDeclaration(
        name="suggest_substitutes",
        description="Пропонує заміни для відсутніх або небажаних інгредієнтів. Викликати коли користувач каже що чогось немає або питає чим замінити.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"ingredients": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Інгредієнти для яких шукати заміни")},
            required=["ingredients"],
        ),
    ),
])


def _dispatch(name: str, args: dict, context: dict) -> dict:
    if name == "get_recipes_by_ingredients":
        result = get_recipes_by_ingredients(list(args.get("ingredients", [])))
        context["last_recipes"] = result
        return {"found": len(result), "recipes": result}
    if name == "filter_recipes":
        result = filter_recipes(list(args.get("recipe_ids", [])), list(args.get("constraints", [])))
        context["last_recipes"] = result
        return {"found": len(result), "recipes": result}
    if name == "generate_recipe":
        return generate_recipe(list(args.get("ingredients", [])))
    if name == "modify_recipe":
        return modify_recipe(int(args.get("recipe_id", 0)), list(args.get("changes", [])))
    if name == "estimate_calories":
        return estimate_calories(list(args.get("ingredients", [])))
    if name == "suggest_substitutes":
        return suggest_substitutes(list(args.get("ingredients", [])))
    return {"error": f"Невідомий інструмент: {name}"}


def _send_with_retry(chat, message, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return chat.send_message(message)
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(20 * (attempt + 1))
                continue
            raise


def run_agent(user_message: str, history: list, context: dict) -> tuple[str, list]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[TOOLS],
    )

    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=config,
        history=history,
    )

    try:
        response = _send_with_retry(chat, user_message)

        while True:
            fn_calls = []
            for part in response.candidates[0].content.parts:
                if part.function_call and part.function_call.name:
                    fn_calls.append(part.function_call)

            if not fn_calls:
                break

            tool_results = [
                types.Part.from_function_response(
                    name=fc.name,
                    response=_dispatch(fc.name, dict(fc.args), context),
                )
                for fc in fn_calls
            ]
            response = _send_with_retry(chat, tool_results)

        text_parts = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        result_text = "\n".join(text_parts) if text_parts else "Не вдалося отримати відповідь."
        return result_text, chat.get_history()

    except Exception as e:
        err = str(e)
        if "429" in err:
            return "⏳ Перевищено ліміт запитів. Зачекайте хвилину і спробуйте знову.", history
        if "API_KEY" in err or "403" in err or "401" in err:
            return "🔑 Помилка автентифікації. Перевірте GEMINI_API_KEY у файлі .env.", history
        return f"❌ Помилка: {err}", history