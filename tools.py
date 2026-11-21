import requests
from langchain_core.tools import tool
from langgraph.types import interrupt

DAILY_PLAN = []

@tool
def get_city_weather(city: str) -> dict:
    """Get current temperature and precipitation in any city (e.g., 'Tbilisi', 'Batumi', 'London', 'New York')."""
    geo_res = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=15,
    )
    geo_res.raise_for_status()
    results = geo_res.json().get("results")
    if not results:
        return {"error": f"City '{city}' not found."}
    
    lat = results[0]["latitude"]
    lon = results[0]["longitude"]
    resolved_name = results[0]["name"]

    weather_res = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": lat, "longitude": lon, "current": "temperature_2m,precipitation"},
        timeout=15,
    )
    weather_res.raise_for_status()
    data = weather_res.json()["current"]
    data["city"] = resolved_name
    return data

@tool
def search_exercises(keyword: str) -> list:
    """Search for exercises by muscle group, equipment, or name (e.g., 'squat', 'push', 'plank', 'abs', 'chest', 'body only')."""
    response = requests.get(
        "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json",
        timeout=15,
    )
    response.raise_for_status()
    all_exercises = response.json()
    
    kw = keyword.lower()
    matches = [
        f"{ex['name']} (Equipment: {ex.get('equipment') or 'none'}, Level: {ex.get('level')})"
        for ex in all_exercises
        if kw in ex["name"].lower()
        or kw in " ".join(ex.get("primaryMuscles", [])).lower()
        or kw in str(ex.get("equipment", "")).lower()
    ]
    return matches[:5] if matches else ["No exact matches found; try 'body only', 'chest', 'legs', or 'abdominals'."]

@tool
def search_healthy_recipes(ingredient: str) -> list:
    """Search for meal recipes by main ingredient in English (e.g., 'chicken', 'egg', 'salmon', 'oats', 'broccoli')."""
    response = requests.get(
        "https://www.themealdb.com/api/json/v1/1/filter.php",
        params={"i": ingredient},
        timeout=15,
    )
    response.raise_for_status()
    meals = response.json().get("meals")
    if not meals:
        return [f"No recipes found for {ingredient}."]
    return [m["strMeal"] for m in meals[:5]]

@tool
def add_to_plan(category: str, item: str) -> str:
    """Add a workout exercise or a meal to the user's daily plan. Category should be 'Workout' or 'Meal'."""
    entry = f"[{category}] {item}"
    DAILY_PLAN.append(entry)
    return f"Added to plan: {entry}"

@tool
def view_plan() -> list:
    """View all workouts and meals currently saved in the user's daily plan."""
    return DAILY_PLAN if DAILY_PLAN else ["The daily plan is currently empty."]

@tool
def remove_from_plan(item_keyword: str) -> str:
    """Remove a specific exercise, meal (e.g., breakfast/საუზმე, lunch/სადილი, dinner/ვახშამი), or all items from the daily plan. Always asks user confirmation before deleting."""
    kw = item_keyword.lower().strip()
    if not DAILY_PLAN:
        return "The daily plan is already empty."

    if kw in ["all", "everything", "ყველა", "ყველაფერი", "მთლიანი გეგმა", "დღევანდელი გეგმა"]:
        approved = interrupt("დარწმუნებული ხართ, რომ გსურთ მთლიანი დღევანდელი გეგმის წაშლა?")
        if approved:
            DAILY_PLAN.clear()
            return "მთლიანი დღევანდელი გეგმა წაიშალა."
        return "წაშლა გაუქმდა."

    synonyms = {
        "breakfast": ["breakfast", "საუზმე"],
        "საუზმე": ["breakfast", "საუზმე"],
        "lunch": ["lunch", "სადილი"],
        "სადილი": ["lunch", "სადილი"],
        "dinner": ["dinner", "ვახშამი"],
        "ვახშამი": ["dinner", "ვახშამი"],
        "workout": ["workout", "ვარჯიში", "წთ"],
        "ვარჯიში": ["workout", "ვარჯიში", "წთ"],
    }
    search_terms = synonyms.get(kw, [kw])
    matches = [x for x in DAILY_PLAN if any(term in x.lower() for term in search_terms)]

    if not matches:
        return f"გეგმაში ვერ მოიძებნა '{item_keyword}'."

    target = matches[0]
    approved = interrupt(f"ნამდვილად გსურთ წაშალოთ: '{target}'?")
    if approved:
        DAILY_PLAN.remove(target)
        return f"წაიშალა: '{target}'."
    else:
        return f"გაუქმდა. '{target}' დარჩა გეგმაში."

tools = [
    get_city_weather,
    search_exercises,
    search_healthy_recipes,
    add_to_plan,
    view_plan,
    remove_from_plan,
]
