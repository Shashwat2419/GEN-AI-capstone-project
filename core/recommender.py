"""Tab 1 logic: recommend the top 3 destinations for travellers with no fixed city."""
from typing import Any, Dict, List

from core import demo_data
from core.config import PROVIDER_DEMO
from core.llm import LLMError, ask_json
from core.planner import PlannerError


def _demo_recommendations(prefs: Dict) -> List[Dict]:
    month = prefs["start_date"].month
    scored = []
    for d in demo_data.DEMO_DESTINATIONS:
        score, reasons = 0, []
        if prefs["vibe"] == d["vibes"][0]:
            score += 4
            reasons.append("perfect %s vibe" % prefs["vibe"].lower())
        elif prefs["vibe"] in d["vibes"]:
            score += 2
            reasons.append("good %s options" % prefs["vibe"].lower())
        if month in d["months"]:
            score += 3
            reasons.append("great weather in your travel month")
        if prefs["budget"] in d["budgets"]:
            score += 2
            reasons.append("fits a %s budget" % prefs["budget"].lower())
        hits = [i for i in prefs["interests"] if i in d["tags"]]
        score += len(hits)
        if hits:
            reasons.append("matches " + ", ".join(h.lower() for h in hits))
        scored.append((score, d, reasons))
    scored.sort(key=lambda t: -t[0])
    top_possible = 4 + 3 + 2 + max(1, len(prefs["interests"]))
    out = []
    for score, d, reasons in scored[:3]:
        out.append({
            "city": d["city"], "country": d["country"],
            "match": min(99, int(round(100.0 * score / top_possible))),
            "why": d["why"] + (" Why it fits: " + "; ".join(reasons) + "." if reasons else ""),
            "tags": d["tags"][:4] + [d["vibes"][0]],
            "weather": d["weather"], "daily_usd": d["daily_usd"],
        })
    return out


def _prompt(prefs: Dict) -> str:
    return (
        "Recommend the 3 best destinations for this traveller.\n"
        "Vibe: %s. Budget level: %s. Party: %s. Pace: %s. Interests: %s. "
        "Trip length: %d days. Travel month: %s.\n"
        "Return ONE JSON object: {\"recommendations\": [3 objects]} where each object has: "
        "\"city\", \"country\", \"match\" (integer 0-100), \"why\" (max 30 words), "
        "\"tags\" (3-5 short highlight tags), \"weather\" (what the weather is like that month), "
        "\"daily_usd\" (approx food+activities per person per day in USD, number). "
        "Prefer cities that are well suited to the month and budget."
    ) % (prefs["vibe"], prefs["budget"], prefs["party"], prefs["pace"],
         ", ".join(prefs["interests"]) or "general", prefs["days"], prefs["month_name"])


def recommend(prefs: Dict, llm: Dict) -> List[Dict]:
    if llm["provider"] == PROVIDER_DEMO:
        return _demo_recommendations(prefs)
    try:
        raw: Any = ask_json(llm["provider"], llm["api_key"], llm["model"], _prompt(prefs))
    except LLMError as exc:
        raise PlannerError(str(exc))
    items = raw.get("recommendations") if isinstance(raw, dict) else raw
    recs = []
    for r in (items or [])[:3]:
        if isinstance(r, dict) and r.get("city"):
            recs.append({
                "city": str(r["city"]), "country": str(r.get("country", "")),
                "match": int(min(100, max(0, float(r.get("match") or 80)))),
                "why": str(r.get("why", "")), "tags": [str(t) for t in (r.get("tags") or [])][:5],
                "weather": str(r.get("weather", "")),
                "daily_usd": float(r.get("daily_usd") or 0),
            })
    if not recs:
        raise PlannerError("The AI did not return any recommendations. Please try again.")
    return recs
