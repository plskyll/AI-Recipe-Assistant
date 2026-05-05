import os
import google.generativeai as genai
from functions import (
    get_recipes_by_ingredients,
    filter_recipes,
    generate_recipe,
    modify_recipe,
    estimate_calories
)

SYSTEM_PROMPT = """Ти — кулінарний асистент. Твоя задача — допомагати користувачам знаходити рецепти, 
генерувати нові та адаптувати існуючі. Відповідай українською мовою.
1. Якщо користувач перераховує інгредієнти — спочатку виклич get_recipes_by_ingredients
2. Якщо є дієтичні обмеження — виклич filter_recipes
3. Якщо база даних не повернула підходящих рецептів — виклич generate_recipe
4. Якщо користувач хоче змінити рецепт — виклич modify_recipe
5. Якщо запитують про калорії — виклич estimate_calories
Не вигадуй рецепти без виклику функцій."""

TOOL_DEFINITIONS = [
    {
        "function_declarations": [
            {
                "name": "get_recipes_by_ingredients",
                "description": "Searches for recipes using the provided list of ingredients.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "ingredients": {"type": "ARRAY", "items": {"type": "STRING"}}
                    },
                    "required": ["ingredients"]
                }
            },
            {
                "name": "filter_recipes",
                "description": "Filters recipes based on constraints like vegan, gluten free, quick, etc.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "recipe_ids": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                        "constraints": {"type": "ARRAY", "items": {"type": "STRING"}}
                    },
                    "required": ["constraints"]
                }
            },
            {
                "name": "generate_recipe",
                "description": "Generates a new recipe template from available ingredients.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "ingredients": {"type": "ARRAY", "items": {"type": "STRING"}}
                    },
                    "required": ["ingredients"]
                }
            },
            {
                "name": "modify_recipe",
                "description": "Modifies an existing recipe according to user changes.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "recipe_id": {"type": "INTEGER"},
                        "changes": {"type": "ARRAY", "items": {"type": "STRING"}}
                    },
                    "required": ["recipe_id", "changes"]
                }
            },
            {
                "name": "estimate_calories",
                "description": "Estimates the total calories of a dish based on its ingredients.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "ingredients": {"type": "ARRAY", "items": {"type": "STRING"}}
                    },
                    "required": ["ingredients"]
                }
            }
        ]
    }
]

def _dispatch_tool(tool_call, context: dict) -> dict:
    name = tool_call.name
    args = dict(tool_call.args)

    if name == "get_recipes_by_ingredients":
        res = get_recipes_by_ingredients(list(args.get("ingredients", [])))
        context["last_recipes"] = res
        return {"found": len(res), "recipes": res}

    if name == "filter_recipes":
        res = filter_recipes(list(args.get("recipe_ids", [])), list(args.get("constraints", [])))
        context["last_recipes"] = res
        return {"found": len(res), "recipes": res}

    if name == "generate_recipe":
        return {"template": generate_recipe(list(args.get("ingredients", [])))}

    if name == "modify_recipe":
        return {"modified_template": modify_recipe(int(args.get("recipe_id", 0)), list(args.get("changes", [])))}

    if name == "estimate_calories":
        return estimate_calories(list(args.get("ingredients", [])))

    return {"error": "Unknown tool"}

def run_agent(user_message: str, history: list, context: dict) -> tuple[str, list]:
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        tools=TOOL_DEFINITIONS,
        system_instruction=SYSTEM_PROMPT
    )

    chat = model.start_chat(history=history)

    try:
        response = chat.send_message(user_message)

        while response.parts and getattr(response.parts[0], "function_call", None):
            fc = response.parts[0].function_call
            tool_result = _dispatch_tool(fc, context)

            response = chat.send_message(
                {"function_response": {"name": fc.name, "response": tool_result}}
            )

        return response.text, chat.history
    except Exception as e:
        return f"Internal API error: {str(e)}", history