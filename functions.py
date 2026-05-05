import json
import os
from pathlib import Path


RECIPES_PATH = Path(__file__).parent / "recipes.json"


def _load_recipes() -> list[dict]:
    with open(RECIPES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_recipes_by_ingredients(ingredients: list[str]) -> list[dict]:
    """
    Шукає рецепти за списком інгредієнтів.
    Повертає рецепти, відсортовані за кількістю збігів.
    """
    recipes = _load_recipes()
    ingredients_lower = [i.strip().lower() for i in ingredients]

    scored = []
    for recipe in recipes:
        recipe_ingredients = [ri.lower() for ri in recipe["ingredients"]]
        matches = sum(
            1 for ing in ingredients_lower
            if any(ing in ri or ri in ing for ri in recipe_ingredients)
        )
        if matches > 0:
            scored.append((matches, recipe))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:5]]


def filter_recipes(recipes: list[dict], constraints: list[str]) -> list[dict]:
    """
    Фільтрує список рецептів за обмеженнями.
    Підтримує: веган, без глютену, без молока, вегетаріанське, швидке (до 15 хв).
    """
    constraint_map = {
        "веган": "веган",
        "vegan": "веган",
        "без глютену": "без глютену",
        "gluten free": "без глютену",
        "вегетаріанське": "вегетаріанське",
        "vegetarian": "вегетаріанське",
        "швидке": "швидке",
        "quick": "швидке",
        "сніданок": "сніданок",
        "обід": "обід",
        "без молока": None,  # обробляється окремо
    }

    dairy_ingredients = ["молоко", "вершки", "масло", "сир", "йогурт", "кефір", "сметана"]
    result = []

    for recipe in recipes:
        passes = True
        for constraint in constraints:
            c = constraint.strip().lower()

            if c == "без молока":
                has_dairy = any(
                    d in ri.lower()
                    for d in dairy_ingredients
                    for ri in recipe["ingredients"]
                )
                if has_dairy:
                    passes = False
                    break

            elif c in constraint_map and constraint_map[c]:
                tag = constraint_map[c]
                if c == "швидке" and recipe["time_minutes"] > 15:
                    passes = False
                    break
                elif c != "швидке" and tag not in recipe.get("tags", []):
                    passes = False
                    break

        if passes:
            result.append(recipe)

    return result


def generate_recipe(ingredients: list[str]) -> dict:
    """
    Формує шаблон рецепту з наявних інгредієнтів для передачі в LLM.
    Повертає структуру із заповненими інгредієнтами.
    """
    return {
        "id": None,
        "name": "Новий рецепт",
        "ingredients": ingredients,
        "steps": [],
        "tags": [],
        "time_minutes": None,
        "calories_per_serving": None,
        "servings": None,
        "_needs_generation": True
    }


def modify_recipe(recipe: dict, changes: list[str]) -> dict:
    """
    Застосовує зміни до рецепту.
    Повертає модифікований рецепт з позначкою для LLM.
    """
    modified = dict(recipe)
    modified["_modifications"] = changes
    modified["_needs_modification"] = True
    return modified


def estimate_calories(ingredients: list[str]) -> dict:
    """
    Приблизна оцінка калорій за популярними інгредієнтами (на 100г).
    """
    calorie_db = {
        "яйця": 155, "сир": 350, "масло": 720, "молоко": 60,
        "курка": 165, "куряче філе": 165, "рис": 130, "морква": 35,
        "картопля": 77, "цибуля": 40, "томати": 18, "огірок": 15,
        "паста": 131, "гречка": 343, "вівсяні пластівці": 370,
        "банан": 89, "гриби": 22, "капуста": 25, "буряк": 43,
        "оливкова олія": 884, "олія": 900, "хліб": 265,
    }

    found = {}
    total_estimate = 0
    for ing in ingredients:
        ing_lower = ing.strip().lower()
        for key, cal in calorie_db.items():
            if key in ing_lower or ing_lower in key:
                found[ing] = cal
                total_estimate += cal
                break

    return {
        "per_ingredient_per_100g": found,
        "estimated_total_raw": total_estimate,
        "note": "Орієнтовні дані на 100г кожного інгредієнта. Точні калорії залежать від кількості."
    }


# Схеми функцій для передачі в API Anthropic (tool_use format)
TOOL_DEFINITIONS = [
    {
        "name": "get_recipes_by_ingredients",
        "description": "Шукає рецепти в базі даних за списком наявних інгредієнтів. Використовуй, коли користувач перераховує продукти.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список інгредієнтів, наприклад ['курка', 'рис', 'морква']"
                }
            },
            "required": ["ingredients"]
        }
    },
    {
        "name": "filter_recipes",
        "description": "Фільтрує рецепти за дієтичними або часовими обмеженнями. Використовуй після пошуку або якщо користувач вказує обмеження.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "ID рецептів для фільтрації (порожній масив = фільтрувати всі)"
                },
                "constraints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Обмеження: 'веган', 'без глютену', 'без молока', 'вегетаріанське', 'швидке'"
                }
            },
            "required": ["constraints"]
        }
    },
    {
        "name": "generate_recipe",
        "description": "Генерує новий рецепт з наданих інгредієнтів, якщо в базі нічого підходящого не знайдено.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Інгредієнти для нового рецепту"
                }
            },
            "required": ["ingredients"]
        }
    },
    {
        "name": "modify_recipe",
        "description": "Модифікує існуючий рецепт згідно з побажаннями: замінити інгредієнт, прибрати молоко, зробити веганським тощо.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe_id": {
                    "type": "integer",
                    "description": "ID рецепту для модифікації (або null якщо рецепт щойно згенерований)"
                },
                "changes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список змін, наприклад ['без молока', 'замінити масло на оливкову олію']"
                }
            },
            "required": ["changes"]
        }
    },
    {
        "name": "estimate_calories",
        "description": "Оцінює калорійність страви за списком інгредієнтів.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Інгредієнти страви"
                }
            },
            "required": ["ingredients"]
        }
    }
]