import json
import os
import anthropic
from functions import (
    get_recipes_by_ingredients,
    filter_recipes,
    generate_recipe,
    modify_recipe,
    estimate_calories,
    TOOL_DEFINITIONS,
    _load_recipes,
)


SYSTEM_PROMPT = """Ти — кулінарний асистент. Твоя задача — допомагати користувачам знаходити рецепти, 
генерувати нові та адаптувати існуючі. Відповідай українською мовою.

Правила роботи з інструментами:
1. Якщо користувач перераховує інгредієнти — спочатку виклич get_recipes_by_ingredients
2. Якщо є дієтичні обмеження (веган, без глютену тощо) — виклич filter_recipes
3. Якщо база даних не повернула підходящих рецептів — виклич generate_recipe
4. Якщо користувач хоче змінити рецепт — виклич modify_recipe
5. Якщо запитують про калорії — виклич estimate_calories

Формат відповіді після отримання даних від інструментів:
- Назва страви (жирним або великими літерами)
- Час приготування та кількість порцій
- Список інгредієнтів
- Покрокові інструкції
- Якщо є — пропозиції щодо замін або варіацій

Не вигадуй рецепти без виклику функцій. Якщо база порожня — використай generate_recipe."""


def _dispatch_tool(tool_name: str, tool_input: dict, conversation_context: dict) -> str:
    """Виконує виклик відповідної функції та повертає результат у вигляді рядка."""

    if tool_name == "get_recipes_by_ingredients":
        recipes = get_recipes_by_ingredients(tool_input["ingredients"])
        conversation_context["last_recipes"] = recipes
        if not recipes:
            return json.dumps({"found": 0, "recipes": [], "message": "Рецептів не знайдено в базі"}, ensure_ascii=False)
        return json.dumps({"found": len(recipes), "recipes": recipes}, ensure_ascii=False)

    elif tool_name == "filter_recipes":
        all_recipes = _load_recipes()
        recipe_ids = tool_input.get("recipe_ids", [])

        if recipe_ids:
            source = [r for r in all_recipes if r["id"] in recipe_ids]
        elif "last_recipes" in conversation_context:
            source = conversation_context["last_recipes"]
        else:
            source = all_recipes

        filtered = filter_recipes(source, tool_input["constraints"])
        conversation_context["last_recipes"] = filtered
        return json.dumps({"found": len(filtered), "recipes": filtered}, ensure_ascii=False)

    elif tool_name == "generate_recipe":
        template = generate_recipe(tool_input["ingredients"])
        return json.dumps({"template": template, "message": "Згенеруй повноцінний рецепт на основі цих інгредієнтів"}, ensure_ascii=False)

    elif tool_name == "modify_recipe":
        all_recipes = _load_recipes()
        recipe_id = tool_input.get("recipe_id")

        if recipe_id:
            recipe = next((r for r in all_recipes if r["id"] == recipe_id), None)
        elif "last_recipes" in conversation_context and conversation_context["last_recipes"]:
            recipe = conversation_context["last_recipes"][0]
        else:
            recipe = None

        if not recipe:
            return json.dumps({"error": "Рецепт не знайдено"}, ensure_ascii=False)

        modified = modify_recipe(recipe, tool_input["changes"])
        return json.dumps({"original": recipe, "modifications": tool_input["changes"], "modified_template": modified}, ensure_ascii=False)

    elif tool_name == "estimate_calories":
        result = estimate_calories(tool_input["ingredients"])
        return json.dumps(result, ensure_ascii=False)

    return json.dumps({"error": f"Невідома функція: {tool_name}"}, ensure_ascii=False)


def run_agent(user_message: str, history: list[dict], context: dict) -> tuple[str, list[dict]]:
    """
    Запускає агентний цикл: LLM → виклик функцій → LLM → відповідь.
    Повертає фінальний текст відповіді та оновлену історію.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    messages = history + [{"role": "user", "content": user_message}]

    for _ in range(5):  # максимум 5 ітерацій щоб уникнути нескінченного циклу
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages
        )

        # Збираємо текстові блоки та виклики функцій
        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        # Якщо функцій немає — це фінальна відповідь
        if not tool_calls:
            final_text = " ".join(text_parts).strip()
            messages.append({"role": "assistant", "content": response.content})
            return final_text, messages

        # Виконуємо всі виклики і формуємо результати
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for call in tool_calls:
            result = _dispatch_tool(call.name, call.input, context)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": result
            })

        messages.append({"role": "user", "content": tool_results})

    return "Не вдалося обробити запит. Спробуйте переформулювати.", messages
