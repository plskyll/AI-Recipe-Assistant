import os
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

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
- Якщо рецепт знайдено, але в ньому є інгредієнти яких немає у користувача → виклич suggest_substitutes для цих інгредієнтів

Форматуй рецепти зручно: назва жирним, інгредієнти списком, кроки нумеровані."""

TOOL_DECLARATIONS = Tool(function_declarations=[
    FunctionDeclaration(
        name="get_recipes_by_ingredients",
        description="Шукає рецепти за списком наявних інгредієнтів.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "ingredients": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Список інгредієнтів",
                }
            },
            "required": ["ingredients"],
        },
    ),
    FunctionDeclaration(
        name="filter_recipes",
        description="Фільтрує рецепти за обмеженнями: веган, без глютену, швидке, сніданок тощо.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "recipe_ids": {
                    "type": "ARRAY",
                    "items": {"type": "INTEGER"},
                    "description": "ID рецептів для фільтрації (порожній = всі)",
                },
                "constraints": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Обмеження, наприклад ['веган', 'без глютену']",
                },
            },
            "required": ["constraints"],
        },
    ),
    FunctionDeclaration(
        name="generate_recipe",
        description="Генерує новий рецепт з наданих інгредієнтів, коли в базі нічого не знайдено.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "ingredients": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Інгредієнти для нового рецепту",
                }
            },
            "required": ["ingredients"],
        },
    ),
    FunctionDeclaration(
        name="modify_recipe",
        description="Модифікує існуючий рецепт відповідно до побажань користувача.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "recipe_id": {
                    "type": "INTEGER",
                    "description": "ID рецепту з бази",
                },
                "changes": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Список змін, наприклад ['прибрати молоко', 'зробити веганським']",
                },
            },
            "required": ["recipe_id", "changes"],
        },
    ),
    FunctionDeclaration(
        name="estimate_calories",
        description="Оцінює калорійність страви за списком інгредієнтів.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "ingredients": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Список інгредієнтів страви",
                }
            },
            "required": ["ingredients"],
        },
    ),
    FunctionDeclaration(
        name="suggest_substitutes",
        description=(
            "Пропонує заміни для відсутніх або небажаних інгредієнтів. "
            "Викликати коли: користувач каже що чогось немає, питає чим замінити інгредієнт, "
            "або коли знайдений рецепт містить інгредієнти яких немає у користувача."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "ingredients": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Інгредієнти для яких шукати заміни",
                }
            },
            "required": ["ingredients"],
        },
    ),
])


def _dispatch(name: str, args: dict, context: dict) -> dict:
    if name == "get_recipes_by_ingredients":
        result = get_recipes_by_ingredients(list(args.get("ingredients", [])))
        context["last_recipes"] = result
        return {"found": len(result), "recipes": result}

    if name == "filter_recipes":
        result = filter_recipes(
            list(args.get("recipe_ids", [])),
            list(args.get("constraints", [])),
        )
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


def run_agent(user_message: str, history: list, context: dict) -> tuple[str, list]:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        tools=[TOOL_DECLARATIONS],
        system_instruction=SYSTEM_PROMPT,
    )

    chat = model.start_chat(history=history)

    try:
        response = chat.send_message(user_message)

        while response.parts and getattr(response.parts[0], "function_call", None):
            fc = response.parts[0].function_call
            tool_result = _dispatch(fc.name, dict(fc.args), context)

            response = chat.send_message({
                "function_response": {
                    "name": fc.name,
                    "response": tool_result,
                }
            })

        return response.text, chat.history

    except Exception as e:
        return f"Помилка API: {e}", history