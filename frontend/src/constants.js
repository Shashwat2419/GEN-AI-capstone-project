export const VIBES = ["Beach", "Mountains", "Cultural", "Urban"];
export const BUDGETS = ["Budget", "Moderate", "Luxury"];
export const PARTIES = { Solo: 1, Couple: 2, Family: 4, Friends: 4 };
export const PACES = ["Relaxed", "Moderate", "Fast-Paced"];
export const INTERESTS = ["Food", "Adventure", "History", "Nightlife"];
export const DIETS = ["No preference", "Vegetarian", "Vegan", "Halal", "Gluten-free"];
export const MAX_DAYS = 10;
export const PROVIDERS = ["Demo", "Gemini", "Groq"];
export const DEFAULT_MODELS = { Gemini: "gemini-2.0-flash", Groq: "llama-3.3-70b-versatile" };
export const DEMO_CITIES = ["Jaipur", "Goa", "Manali", "Paris", "Bangkok"];
export const SLOT_ICONS = {
  "Morning Sightseeing": "🌅",
  "Lunch Recommendation": "🍽️",
  "Afternoon Leisure": "🌴",
  "Evening Dining & Entertainment": "🌙",
};
export const SWAP_SUGGESTIONS = [
  "Swap museum for outdoor market",
  "Find vegetarian lunch spot",
  "Something more adventurous",
  "Add a nightlife option",
];

export function defaultPrefs() {
  const d = new Date(Date.now() + 21 * 86400000);
  return {
    destination: "",
    vibe: "Cultural",
    days: 4,
    start_date: d.toISOString().slice(0, 10),
    budget: "Moderate",
    party: "Couple",
    pace: "Moderate",
    interests: ["Food", "History"],
    diet: "No preference",
  };
}
