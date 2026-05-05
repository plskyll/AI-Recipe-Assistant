import json
from pathlib import Path

RECIPES_PATH = Path(__file__).parent / "recipes.json"

def _load_recipes() -> list[dict]:
    with open(RECIPES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_recipes_by_ingredients(ingredients: list[str]) -> list[dict]:
    recipes = _load_recipes()
    ingredients_lower = [i.strip().lower() for i in ingredients]

    scored = []
    for recipe in recipes:
        recipe_ingredients = [ri.lower() for ri in recipe.get("ingredients", [])]
        matches = sum(
            1 for ing in ingredients_lower
            if any(ing in ri or ri in ing for ri in recipe_ingredients)
        )
        if matches > 0:
            scored.append((matches, recipe))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:5]]

def filter_recipes(recipe_ids: list[int], constraints: list[str]) -> list[dict]:
    recipes = _load_recipes()
    if recipe_ids:
        recipes = [r for r in recipes if r.get("id") in recipe_ids]

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
        "без молока": "",
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
                    for ri in recipe.get("ingredients", [])
                )
                if has_dairy:
                    passes = False
                    break
            elif c in constraint_map and constraint_map[c]:
                tag = constraint_map[c]
                if c == "швидке" and recipe.get("time_minutes", 999) > 15:
                    passes = False
                    break
                elif c != "швидке" and tag not in recipe.get("tags", []):
                    passes = False
                    break

        if passes:
            result.append(recipe)

    return result

def generate_recipe(ingredients: list[str]) -> dict:
    return {
        "id": 0,
        "name": "Новий рецепт",
        "ingredients": ingredients,
        "steps": [],
        "tags": [],
        "time_minutes": 0,
        "calories_per_serving": 0,
        "servings": 0,
        "_needs_generation": True
    }

def modify_recipe(recipe_id: int, changes: list[str]) -> dict:
    recipes = _load_recipes()
    recipe = next((r for r in recipes if r.get("id") == recipe_id), None)

    if not recipe:
        return {"error": "Recipe not found"}

    modified = dict(recipe)
    modified["_modifications"] = changes
    modified["_needs_modification"] = True
    return modified

def estimate_calories(ingredients: list[str]) -> dict:
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
        "estimated_total_raw": total_estimate
    }