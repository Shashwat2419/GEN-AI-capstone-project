"""Framework-independent glue between the HTTP layer and the planning engine."""
import copy
import os
from datetime import date
from typing import Any, Dict, List

from core.config import PARTIES, PROVIDER_DEMO, PROVIDER_GEMINI, PROVIDER_GROQ, DEFAULT_MODELS
from core.planner import (
    budget_summary, day_cost_local, day_transit_km, generate_itinerary, regenerate_day, swap_activity,
)
from core.recommender import recommend

ENV_KEYS = {PROVIDER_GEMINI: "GEMINI_API_KEY", PROVIDER_GROQ: "GROQ_API_KEY"}


def resolve_llm(provider: str, api_key: str = "", model: str = "") -> Dict:
    """Return the llm dict used by the planner; falls back to demo mode without a key."""
    if provider not in ENV_KEYS:
        return {"provider": PROVIDER_DEMO, "api_key": "", "model": ""}
    key = (api_key or "").strip() or os.environ.get(ENV_KEYS[provider], "")
    if not key:
        return {"provider": PROVIDER_DEMO, "api_key": "", "model": ""}
    return {"provider": provider, "api_key": key, "model": (model or "").strip() or DEFAULT_MODELS[provider]}


def build_prefs(raw: Dict) -> Dict:
    """Turn the validated request body into the prefs dict the engine expects."""
    start = raw["start_date"]
    if isinstance(start, str):
        start = date.fromisoformat(start)
    return {
        "destination": (raw.get("destination") or "").strip(), "vibe": raw["vibe"], "days": int(raw["days"]),
        "start_date": start, "budget": raw["budget"], "party": raw["party"],
        "party_size": PARTIES[raw["party"]], "pace": raw["pace"],
        "interests": list(raw.get("interests") or []), "diet": raw.get("diet", "No preference"),
        "month_name": start.strftime("%B"),
    }


def analytics(itin: Dict) -> Dict:
    """Numbers the UI shows: totals, per-day cost/transit and the cumulative table."""
    size = itin["prefs"]["party_size"]
    summary = budget_summary(itin)
    summary["days"] = [{"day": d["day"], "cost_local": round(day_cost_local(d, size), 2),
                        "transit_km": round(day_transit_km(d), 2)} for d in itin["days"]]
    summary["transit_km"] = round(summary["transit_km"], 2)
    return summary


def with_analytics(itin: Dict) -> Dict:
    return {"itinerary": itin, "analytics": analytics(itin)}


def do_recommend(raw_prefs: Dict, llm: Dict) -> List[Dict]:
    return recommend(build_prefs(raw_prefs), llm)


def do_generate(raw_prefs: Dict, llm: Dict) -> Dict:
    return with_analytics(generate_itinerary(build_prefs(raw_prefs), llm))


def do_swap(itin: Dict, day_idx: int, slot: str, item_idx: int, instruction: str, llm: Dict) -> Dict:
    itin = copy.deepcopy(itin)
    _check_indexes(itin, day_idx, slot, item_idx)
    res = swap_activity(itin, day_idx, slot, item_idx, instruction, llm)
    out = with_analytics(itin)
    out["old"], out["new"] = res["old"], res["new"]
    return out


def do_regenerate(itin: Dict, day_idx: int, instruction: str, llm: Dict) -> Dict:
    itin = copy.deepcopy(itin)
    _check_indexes(itin, day_idx)
    regenerate_day(itin, day_idx, instruction, llm)
    return with_analytics(itin)


def _check_indexes(itin: Dict, day_idx: int, slot: str = None, item_idx: int = 0) -> None:
    from core.planner import PlannerError
    if not 0 <= day_idx < len(itin.get("days", [])):
        raise PlannerError("That day does not exist in this itinerary.")
    if slot is not None:
        match = [s for s in itin["days"][day_idx]["slots"] if s["slot"] == slot]
        if not match or not 0 <= item_idx < len(match[0]["items"]):
            raise PlannerError("That activity does not exist in this itinerary.")


def validate_itinerary(itin: Any) -> Dict:
    """Light structural check for itineraries sent back by the browser."""
    from core.planner import PlannerError
    try:
        assert isinstance(itin, dict)
        assert itin["destination"] and itin["days"] and itin["fx"]["per_usd"] > 0
        for d in itin["days"]:
            for s in d["slots"]:
                for i in s["items"]:
                    float(i["lat"]), float(i["lon"]), float(i["cost_local"])
        itin["prefs"]["party_size"]
    except (AssertionError, KeyError, TypeError, ValueError):
        raise PlannerError("The itinerary data is incomplete or corrupted. Please generate it again.")
    itin.setdefault("reserve", {"attractions": [], "lunch": [], "dinner": []})
    itin.setdefault("catalog", {"lunch": [], "dinner": []})
    return itin
