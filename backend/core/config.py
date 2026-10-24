"""Central configuration: option lists, defaults and tunables."""

APP_NAME = "Personalized Travel Itinerary Planner"
APP_TAGLINE = "Skill Wallet Capstone Project 4 - AI trip planning without the transit fatigue"

VIBES = ["Beach", "Mountains", "Cultural", "Urban"]
BUDGETS = ["Budget", "Moderate", "Luxury"]
PARTIES = {"Solo": 1, "Couple": 2, "Family": 4, "Friends": 4}  # name -> travellers
PACES = ["Relaxed", "Moderate", "Fast-Paced"]
INTERESTS = ["Food", "Adventure", "History", "Nightlife"]
DIETS = ["No preference", "Vegetarian", "Vegan", "Halal", "Gluten-free"]

MAX_DAYS = 10

# The four sequential time slots every day is built from.
SLOT_MORNING = "Morning Sightseeing"
SLOT_LUNCH = "Lunch Recommendation"
SLOT_AFTERNOON = "Afternoon Leisure"
SLOT_EVENING = "Evening Dining & Entertainment"
SLOTS = [SLOT_MORNING, SLOT_LUNCH, SLOT_AFTERNOON, SLOT_EVENING]
SLOT_ICONS = {
    SLOT_MORNING: "🌅",
    SLOT_LUNCH: "🍽️",
    SLOT_AFTERNOON: "🌴",
    SLOT_EVENING: "🌙",
}

# (morning attractions, afternoon attractions) per day for each pace.
PACE_COUNTS = {"Relaxed": (1, 1), "Moderate": (2, 1), "Fast-Paced": (2, 2)}

# Rough per-person, per-day budget (food + activities) in USD, used for the
# budget tracker target.  Lodging and flights are NOT included.
DAILY_BUDGET_USD = {"Budget": 40, "Moderate": 100, "Luxury": 250}

# Demo-mode price scaling so the budget selector visibly changes the plan.
DEMO_BUDGET_FACTOR = {"Budget": 0.7, "Moderate": 1.0, "Luxury": 1.8}

# Approximate units of currency per 1 USD.  These are static estimates and can
# be overridden by the user in the sidebar.
DEFAULT_RATES_PER_USD = {
    "USD": 1.0, "INR": 88.0, "EUR": 0.92, "GBP": 0.78, "THB": 35.0,
    "JPY": 150.0, "AED": 3.67, "SGD": 1.32, "IDR": 16000.0, "AUD": 1.52,
    "CAD": 1.37, "CHF": 0.88, "MYR": 4.5, "VND": 25000.0, "LKR": 300.0,
    "NPR": 140.0, "TRY": 34.0, "MXN": 18.0,
}
DEFAULT_INR_PER_USD = DEFAULT_RATES_PER_USD["INR"]

# LLM providers
PROVIDER_DEMO = "Demo mode (no key)"
PROVIDER_GEMINI = "Gemini"
PROVIDER_GROQ = "Groq"
PROVIDERS = [PROVIDER_DEMO, PROVIDER_GEMINI, PROVIDER_GROQ]
# Model names change over time - the sidebar lets users edit them.
DEFAULT_MODELS = {
    PROVIDER_GEMINI: "gemini-2.0-flash",
    PROVIDER_GROQ: "llama-3.3-70b-versatile",
}

SWAP_SUGGESTIONS = [
    "Swap museum for outdoor market",
    "Find vegetarian lunch spot",
    "Something more adventurous",
    "Add a nightlife option",
]
