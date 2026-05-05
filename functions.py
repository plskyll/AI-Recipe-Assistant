import json
from pathlib import Path

RECIPES_PATH = Path(__file__).parent / "recipes.json"

DAIRY_INGREDIENTS = {"молоко", "вершки", "масло", "сир", "йогурт", "кефір", "сметана"}

CALORIE_TABLE = {
    "яйця": 155, "сир": 350, "масло": 720, "молоко": 60,
    "курка": 165, "куряче філе": 165, "рис": 130, "морква": 35,
    "картопля": 77, "цибуля": 40, "томати": 18, "огірок": 15,
    "паста": 131, "гречка": 343, "вівсяні пластівці": 370,
    "банан": 89, "гриби": 22, "капуста": 25, "буряк": 43,
    "оливкова олія": 884, "олія": 900, "хліб": 265,
}

TAG_ALIASES = {
    "vegan": "веган",
    "vegetarian": "вегетаріанське",
    "вегетаріанський": "вегетаріанське",
    "gluten free": "без глютену",
    "gluten-free": "без глютену",
    "quick": "швидке",
    "breakfast": "сніданок",
    "lunch": "обід",
}

# База замін: що можна використати замість відсутнього інгредієнта
SUBSTITUTES: dict[str, list[dict]] = {
    "молоко": [
        {"substitute": "рослинне молоко (вівсяне, соєве, мигдальне)", "note": "1:1, підходить для каш і соусів"},
        {"substitute": "вода", "note": "якщо смак не критичний"},
        {"substitute": "кефір або йогурт", "note": "розбавити водою 1:1"},
    ],
    "масло": [
        {"substitute": "олія (соняшникова або оливкова)", "note": "75% від кількості масла"},
        {"substitute": "кокосова олія", "note": "1:1, дає легкий присмак"},
    ],
    "яйця": [
        {"substitute": "1 ст.л. льняного борошна + 3 ст.л. води", "note": "для випічки, дати набухнути 5 хв"},
        {"substitute": "50г несолодкого йогурту", "note": "для пухкості"},
        {"substitute": "половина банана (розім'ята)", "note": "для солодкої випічки"},
    ],
    "сир": [
        {"substitute": "тофу (твердий, натертий)", "note": "веганська заміна"},
        {"substitute": "пармезан або бринза", "note": "менша кількість через солоність"},
    ],
    "вершки": [
        {"substitute": "молоко + 1 ч.л. борошна", "note": "для загущення соусів"},
        {"substitute": "кокосові вершки", "note": "1:1, веганський варіант"},
    ],
    "куряче філе": [
        {"substitute": "індиче філе", "note": "1:1, схожий час приготування"},
        {"substitute": "тофу (твердий)", "note": "веганська заміна, маринувати 30 хв"},
        {"substitute": "нут (варений)", "note": "веганська заміна для рагу та супів"},
    ],
    "рис": [
        {"substitute": "гречка", "note": "інший смак, але така сама ситність"},
        {"substitute": "булгур або кускус", "note": "готується швидше"},
        {"substitute": "картопля (варена)", "note": "як гарнір"},
    ],
    "паста": [
        {"substitute": "рисова або гречана локшина", "note": "без глютену, варити менше"},
        {"substitute": "кабачок (соломкою)", "note": "без глютену, без варіння"},
    ],
    "цибуля": [
        {"substitute": "цибуля-порей", "note": "м'якший смак, 1:1"},
        {"substitute": "часник (менша кількість)", "note": "для аромату"},
        {"substitute": "пропустити", "note": "рецепт збережеться, смак буде менш насиченим"},
    ],
    "часник": [
        {"substitute": "часниковий порошок", "note": "¼ ч.л. = 1 зубчик"},
        {"substitute": "пропустити або замінити цибулею", "note": ""},
    ],
    "томати": [
        {"substitute": "томатна паста + вода (1:3)", "note": "для соусів і тушкування"},
        {"substitute": "болгарський перець", "note": "свіжий, для салатів"},
    ],
    "гриби": [
        {"substitute": "кабачок або баклажан", "note": "схожа текстура після смаження"},
        {"substitute": "сушені гриби (замочені)", "note": "більш насичений смак"},
    ],
}


def _load_recipes() -> list[dict]:
    with open(RECIPES_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_recipes_by_ingredients(ingredients: list[str]) -> list[dict]:
    recipes = _load_recipes()
    query = [i.strip().lower() for i in ingredients]

    scored = []
    for recipe in recipes:
        recipe_ings = [ri.lower() for ri in recipe.get("ingredients", [])]
        matches = sum(
            1 for q in query
            if any(q in ri or ri in q for ri in recipe_ings)
        )
        # частка інгредієнтів рецепту, яку має користувач
        coverage = matches / len(recipe_ings) if recipe_ings else 0
        if matches >= 2 or coverage >= 0.25:
            scored.append((matches, recipe))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:5]]


def filter_recipes(recipe_ids: list[int], constraints: list[str]) -> list[dict]:
    recipes = _load_recipes()
    if recipe_ids:
        recipes = [r for r in recipes if r.get("id") in recipe_ids]

    result = []
    for recipe in recipes:
        tags = recipe.get("tags", [])
        ings = [i.lower() for i in recipe.get("ingredients", [])]

        passed = True
        for raw in constraints:
            c = raw.strip().lower()
            c = TAG_ALIASES.get(c, c)

            if c == "без молока":
                if any(d in ing for d in DAIRY_INGREDIENTS for ing in ings):
                    passed = False
                    break
            elif c == "швидке":
                if recipe.get("time_minutes", 999) > 15:
                    passed = False
                    break
            elif c in ("веган", "вегетаріанське", "без глютену", "сніданок", "обід"):
                if c not in tags:
                    passed = False
                    break

        if passed:
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
        "_needs_generation": True,
    }


def modify_recipe(recipe_id: int, changes: list[str]) -> dict:
    recipe = next((r for r in _load_recipes() if r.get("id") == recipe_id), None)
    if not recipe:
        return {"error": f"Рецепт з id={recipe_id} не знайдено"}
    return {**recipe, "_modifications": changes, "_needs_modification": True}


def estimate_calories(ingredients: list[str]) -> dict:
    breakdown = {}
    total = 0
    for ing in ingredients:
        key = ing.strip().lower()
        for name, cal in CALORIE_TABLE.items():
            if name in key or key in name:
                breakdown[ing] = cal
                total += cal
                break
    return {"per_ingredient_kcal_per_100g": breakdown, "estimated_total_kcal": total}


def suggest_substitutes(ingredients: list[str]) -> dict:
    """Повертає варіанти заміни для кожного з переданих інгредієнтів."""
    result = {}
    not_found = []

    for ing in ingredients:
        key = ing.strip().lower()
        match = next(
            (k for k in SUBSTITUTES if k in key or key in k),
            None,
        )
        if match:
            result[ing] = SUBSTITUTES[match]
        else:
            not_found.append(ing)

    return {
        "substitutes": result,
        "no_substitutes_found": not_found,
    }