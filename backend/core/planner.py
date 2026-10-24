"""Itinerary engine.

Pipeline
--------
1. A *pool* of real places (attractions, lunch spots, dinner/entertainment) is
   produced by the LLM, or loaded from offline demo data.
2. ``build_days`` runs **balanced geographic clustering** (k-means with
   capacity limits) so each day's attractions sit close together, orders them
   with a nearest-neighbour route and picks meals near where you will be.
3. Costs, running budget totals and transit distance are computed locally,
   so the numbers always add up regardless of what the model says.
"""
import copy
import math
import random
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from core import demo_data
from core.config import (
    DAILY_BUDGET_USD, DEFAULT_INR_PER_USD, DEFAULT_RATES_PER_USD, DEMO_BUDGET_FACTOR,
    PACE_COUNTS, PROVIDER_DEMO, SLOT_AFTERNOON, SLOT_EVENING, SLOT_LUNCH, SLOT_MORNING,
)
from core.llm import LLMError, ask_json


class PlannerError(Exception):
    """User-facing planning problem (bad input, not enough places, ...)."""


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _dist(a: Dict, b: Dict) -> float:
    return haversine(a["lat"], a["lon"], b["lat"], b["lon"])


def _centroid(items: List[Dict]) -> Dict:
    return {"lat": sum(i["lat"] for i in items) / len(items),
            "lon": sum(i["lon"] for i in items) / len(items)}


def balanced_clusters(items: List[Dict], k: int, iterations: int = 12) -> List[List[Dict]]:
    """Split ``items`` into ``k`` geographic clusters of (near-)equal size.

    Farthest-point initialisation + k-means where each cluster has a capacity
    of ceil(n / k); points are assigned greedily by increasing distance.
    """
    if k <= 1:
        return [list(items)]
    n = len(items)
    cap = int(math.ceil(n / float(k)))
    centre = _centroid(items)
    first = max(items, key=lambda i: _dist(i, centre))
    centers = [{"lat": first["lat"], "lon": first["lon"]}]
    while len(centers) < k:
        nxt = max(items, key=lambda i: min(_dist(i, c) for c in centers))
        centers.append({"lat": nxt["lat"], "lon": nxt["lon"]})

    clusters: List[List[Dict]] = [[] for _ in range(k)]
    for _ in range(iterations):
        pairs = sorted(
            ((_dist(it, centers[ci]), idx, ci) for idx, it in enumerate(items) for ci in range(k)),
            key=lambda t: t[0],
        )
        clusters = [[] for _ in range(k)]
        placed = set()
        for _, idx, ci in pairs:
            if idx in placed or len(clusters[ci]) >= cap:
                continue
            clusters[ci].append(items[idx])
            placed.add(idx)
        new_centers = [_centroid(c) if c else centers[i] for i, c in enumerate(clusters)]
        moved = max(haversine(a["lat"], a["lon"], b["lat"], b["lon"])
                    for a, b in zip(centers, new_centers))
        centers = new_centers
        if moved < 0.01:
            break
    return [c for c in clusters if c]


def nearest_neighbour_order(items: List[Dict], start: Optional[Dict] = None) -> List[Dict]:
    """Order items into a short walking/driving chain (greedy nearest neighbour)."""
    remaining = list(items)
    if not remaining:
        return []
    if start is None:
        centre = _centroid(remaining)
        current = min(remaining, key=lambda i: _dist(i, centre))
        remaining.remove(current)
    else:
        current = min(remaining, key=lambda i: _dist(i, start))
        remaining.remove(current)
    ordered = [current]
    while remaining:
        current = min(remaining, key=lambda i: _dist(i, current))
        remaining.remove(current)
        ordered.append(current)
    return ordered


# --------------------------------------------------------------------------- #
# Item normalisation / scoring
# --------------------------------------------------------------------------- #
def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def normalise_item(raw: Dict, default_type: str = "sight") -> Optional[Dict]:
    """Coerce an LLM/demo dict into the app's activity schema (None if unusable)."""
    if not isinstance(raw, dict) or not raw.get("name"):
        return None
    lat, lon = raw.get("lat"), raw.get("lon")
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split()
    return {
        "name": str(raw["name"]).strip(),
        "area": str(raw.get("area") or "").strip(),
        "lat": lat, "lon": lon,
        "type": str(raw.get("type") or default_type).lower(),
        "description": str(raw.get("description") or "").strip(),
        "cost_local": max(0.0, _num(raw.get("cost_local"))),
        "duration_hrs": max(0.25, _num(raw.get("duration_hrs"), 1.5)),
        "tags": [str(t).lower() for t in tags][:6],
    }


def _interest_score(item: Dict, interests: List[str]) -> int:
    wanted = set()
    for i in interests:
        wanted.add(i.lower())
        if i == "History":
            wanted.update(["heritage", "fort", "temple", "church", "museum"])
        elif i == "Adventure":
            wanted.update(["hike", "water-sports", "paragliding", "outdoor"])
        elif i == "Food":
            wanted.update(["street-food", "market"])
    return sum(1 for t in item["tags"] if t in wanted)


_STOP = {"swap", "for", "a", "an", "the", "find", "me", "to", "with", "add", "something", "more",
         "option", "spot", "place", "and", "or", "instead", "of", "some", "please", "want", "i"}


def _tokens(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z\-]+", text.lower()) if w not in _STOP and len(w) > 2]


def _instruction_score(item: Dict, instruction: str) -> float:
    """Reward items matching the wanted words; penalise 'swap X for Y' X words."""
    if not instruction:
        return 0.0
    text = instruction.lower()
    neg: List[str] = []
    pos_text = text
    m = re.search(r"swap\s+(.+?)\s+for\s+(.+)", text)
    if m:
        neg, pos_text = _tokens(m.group(1)), m.group(2)
    haystack_name = (item["name"] + " " + item["description"]).lower()
    score = 0.0
    for w in _tokens(pos_text):
        stem = w.rstrip("s")
        if any(stem in t for t in item["tags"]):
            score += 2
        elif stem in haystack_name:
            score += 1
    for w in neg:
        stem = w.rstrip("s")
        if any(stem in t for t in item["tags"]):
            score -= 3
    return score


# --------------------------------------------------------------------------- #
# Pools (LLM or demo)
# --------------------------------------------------------------------------- #
def _demo_lookup(destination: str) -> Dict:
    key = destination.strip().lower()
    for name, data in demo_data.DEMO_CITIES.items():
        if key and (key == name.lower() or key in name.lower() or name.lower() in key):
            return dict(data, destination=name)
    raise PlannerError(
        "Demo mode only includes: %s. Pick one of those, or add a Gemini/Groq key in the "
        "sidebar to plan any destination." % ", ".join(demo_data.DEMO_CITIES))


def demo_pool(destination: str, prefs: Dict) -> Dict:
    data = _demo_lookup(destination)
    factor = DEMO_BUDGET_FACTOR.get(prefs.get("budget", "Moderate"), 1.0)
    pool = {k: data[k] for k in ("destination", "country", "currency", "usd_to_local",
                                 "summary", "tips", "emergency")}
    for key in ("attractions", "lunch", "dinner"):
        pool[key] = [dict(i, cost_local=round(i["cost_local"] * factor, 2)) for i in data[key]]
    return pool


def _pool_prompt(prefs: Dict, destination: str, days: int, exclude: List[str], instruction: str) -> str:
    cm, ca = PACE_COUNTS[prefs["pace"]]
    n_att = days * (cm + ca) + (2 if days == 1 else 4)
    n_meal = days + 2
    lines = [
        "Plan a %d-day trip to %s." % (days, destination),
        "Travellers: %s (%d people). Budget level: %s. Pace: %s." % (
            prefs["party"], prefs["party_size"], prefs["budget"], prefs["pace"]),
        "Interests: %s. Dietary needs: %s. Travel month: %s." % (
            ", ".join(prefs["interests"]) or "general sightseeing", prefs["diet"], prefs["month_name"]),
    ]
    if instruction:
        lines.append("Special request from the traveller: %s" % instruction)
    if exclude:
        lines.append("Do NOT include these places (already planned): %s." % "; ".join(exclude))
    lines.append("""
Return ONE JSON object with exactly these keys:
 "destination": city name, "country": country,
 "currency": ISO 4217 code of the local currency,
 "usd_to_local": approximate local-currency units per 1 USD (number),
 "summary": two sentences about the trip,
 "tips": array of 4 short practical tips,
 "emergency": {"police": "", "ambulance": "", "fire": "", "tourist_helpline": "", "embassy_note": ""} (local numbers as strings, "" if unsure),
 "attractions": array of %d objects (sights and leisure activities, most relevant first),
 "lunch": array of %d casual midday restaurants,
 "dinner": array of %d dinner venues or evening entertainment options.
Every item in those arrays has: "name", "area" (neighbourhood), "lat", "lon" (decimal degrees),
 "description" (max 20 words), "cost_local" (per person, local currency, number, 0 if free),
 "duration_hrs" (number), "tags" (2-4 lowercase words, e.g. outdoor, museum, market, vegetarian, history, nightlife, adventure, food)
 and, for attractions only, "type": "sight" (best in the morning) or "leisure" (relaxed afternoon activity).
Rules: only real, currently operating places in or very near %s; no duplicates; keep the budget level in mind
for prices; respect dietary needs for lunch and dinner (flag with the matching tag such as vegetarian).""" % (
        n_att, n_meal, n_meal, destination))
    return "\n".join(lines)


def _clean_pool(raw: Any) -> Dict:
    if not isinstance(raw, dict):
        raise PlannerError("The AI reply had an unexpected structure. Please try again.")
    pool = {
        "destination": str(raw.get("destination") or "").strip(),
        "country": str(raw.get("country") or "").strip(),
        "currency": str(raw.get("currency") or "USD").upper()[:3],
        "usd_to_local": _num(raw.get("usd_to_local"), 0.0),
        "summary": str(raw.get("summary") or "").strip(),
        "tips": [str(t) for t in (raw.get("tips") or [])][:6],
        "emergency": raw.get("emergency") if isinstance(raw.get("emergency"), dict) else {},
    }
    for key, default in (("attractions", "sight"), ("lunch", "meal"), ("dinner", "meal")):
        items = [normalise_item(i, default) for i in (raw.get(key) or [])]
        seen, unique = set(), []
        for it in items:
            if it and it["name"].lower() not in seen:
                seen.add(it["name"].lower())
                unique.append(it)
        pool[key] = unique
    return pool


def get_pool(prefs: Dict, llm: Dict, destination: str, days: int,
             exclude: Optional[List[str]] = None, instruction: str = "") -> Dict:
    if llm["provider"] == PROVIDER_DEMO:
        return demo_pool(destination, prefs)
    prompt = _pool_prompt(prefs, destination, days, exclude or [], instruction)
    try:
        raw = ask_json(llm["provider"], llm["api_key"], llm["model"], prompt)
    except LLMError as exc:
        raise PlannerError(str(exc))
    return _clean_pool(raw)


# --------------------------------------------------------------------------- #
# Building days
# --------------------------------------------------------------------------- #
def _pick_meal(candidates: List[Dict], near: Dict, used: set, diet: str,
               nightlife_bonus: bool = False) -> Optional[Dict]:
    """Choose a meal venue close to ``near``; prefer unused venues unless one is far away."""
    if not candidates:
        return None
    pool = candidates
    if diet and diet != "No preference":
        wanted = diet.lower()
        matching = [c for c in pool if any(wanted in t or t in wanted for t in c["tags"])]
        if diet in ("Vegan", "Vegetarian"):
            matching = matching or [c for c in pool if "vegetarian" in c["tags"] or "vegan" in c["tags"]]
        pool = matching or pool

    def score(c: Dict) -> float:
        bonus = 3.0 if nightlife_bonus and "nightlife" in c["tags"] else 0.0
        return _dist(c, near) - bonus

    best_any = min(pool, key=score)
    fresh = [c for c in pool if c["name"] not in used]
    if not fresh:
        return best_any
    best_fresh = min(fresh, key=score)
    # repeat a favourite rather than send people across town for a new restaurant
    return best_any if score(best_fresh) > score(best_any) + 4.0 else best_fresh


def _slot(name: str, items: List[Dict]) -> Dict:
    return {"slot": name, "items": items}


def build_days(pool: Dict, prefs: Dict, n_days: int, instruction: str = "",
               jitter: float = 0.0) -> List[Dict]:
    """Cluster attractions into days and assemble the four time slots."""
    cm, ca = PACE_COUNTS[prefs["pace"]]
    per_day = cm + ca
    attractions = pool["attractions"]
    if len(attractions) < per_day:
        raise PlannerError("Not enough places were found to fill a day. Try another pace or destination.")
    rng = random.Random()
    n_days = min(n_days, len(attractions) // per_day)

    scored = sorted(
        attractions,
        key=lambda i: -(_interest_score(i, prefs["interests"]) + 3 * _instruction_score(i, instruction)
                        + (rng.random() * jitter if jitter else 0.0)))
    if n_days == 1:  # compact pick: best item as seed + its nearest neighbours
        seed = scored[0]
        rest = sorted(scored[1:], key=lambda i: _dist(i, seed))[:per_day - 1]
        chosen_groups = [[seed] + rest]
    else:
        chosen = scored[:n_days * per_day]
        groups = balanced_clusters(chosen, n_days)
        # order the clusters so consecutive days are neighbours (west -> east sweep)
        groups.sort(key=lambda g: _centroid(g)["lon"])
        ordered, remaining = [groups[0]], groups[1:]
        while remaining:
            last = _centroid(ordered[-1])
            nxt = min(remaining, key=lambda g: _dist(_centroid(g), last))
            remaining.remove(nxt)
            ordered.append(nxt)
        chosen_groups = ordered

    used_lunch, used_dinner = set(), set()
    city_centre = _centroid(attractions)
    days = []
    for group in chosen_groups:
        group = sorted(group, key=lambda i: (i["type"] == "leisure"))  # sights first
        morning = nearest_neighbour_order(group[:cm], city_centre)
        afternoon = nearest_neighbour_order(group[cm:cm + ca], morning[-1] if morning else None)
        lunch = _pick_meal(pool["lunch"], morning[-1], used_lunch, prefs["diet"])
        end_point = afternoon[-1] if afternoon else morning[-1]
        dinner = _pick_meal(pool["dinner"], end_point, used_dinner, prefs["diet"],
                            nightlife_bonus="Nightlife" in prefs["interests"])
        slots = [_slot(SLOT_MORNING, morning)]
        if lunch:
            used_lunch.add(lunch["name"])
            slots.append(_slot(SLOT_LUNCH, [lunch]))
        slots.append(_slot(SLOT_AFTERNOON, afternoon))
        if dinner:
            used_dinner.add(dinner["name"])
            slots.append(_slot(SLOT_EVENING, [dinner]))
        areas = [i["area"] for i in group if i["area"]]
        theme = max(set(areas), key=areas.count) if areas else "City highlights"
        days.append({"theme": theme, "slots": slots})
    return days


def _assign_dates(days: List[Dict], start_iso: str) -> None:
    try:
        start = date.fromisoformat(start_iso)
    except (TypeError, ValueError):
        start = date.today()
    for idx, day in enumerate(days):
        day["day"] = idx + 1
        day["date"] = (start + timedelta(days=idx)).isoformat()


def _used_names(days: List[Dict]) -> set:
    return {i["name"] for d in days for s in d["slots"] for i in s["items"]}


def _slot_category(slot_name: str) -> str:
    return {SLOT_LUNCH: "lunch", SLOT_EVENING: "dinner"}.get(slot_name, "attractions")


def _reserve_from(pool: Dict, days: List[Dict]) -> Dict:
    used = _used_names(days)
    return {k: [i for i in pool[k] if i["name"] not in used] for k in ("attractions", "lunch", "dinner")}


def make_serialisable_prefs(prefs: Dict) -> Dict:
    out = dict(prefs)
    d = out.get("start_date")
    out["start_date"] = d.isoformat() if hasattr(d, "isoformat") else str(d)
    return out


def _fx(pool: Dict) -> Dict:
    cur = pool["currency"]
    per_usd = DEFAULT_RATES_PER_USD.get(cur) or pool.get("usd_to_local") or 1.0
    return {"local": cur, "per_usd": float(per_usd), "inr_per_usd": DEFAULT_INR_PER_USD}


def generate_itinerary(prefs: Dict, llm: Dict) -> Dict:
    destination = (prefs.get("destination") or "").strip()
    if not destination:
        raise PlannerError("Enter a destination (or use Tab 1 to get recommendations first).")
    pool = get_pool(prefs, llm, destination, prefs["days"])
    days = build_days(pool, prefs, prefs["days"])
    warnings = []
    if len(days) < prefs["days"]:
        warnings.append(
            "Only %d of %d requested days could be filled with distinct places at a %s pace. "
            "Choose a slower pace or use AI mode for longer trips." % (len(days), prefs["days"], prefs["pace"]))
    sp = make_serialisable_prefs(prefs)
    _assign_dates(days, sp["start_date"])
    return {
        "destination": pool["destination"] or destination,
        "country": pool["country"], "currency": pool["currency"],
        "summary": pool["summary"], "tips": pool["tips"], "emergency": pool["emergency"],
        "fx": _fx(pool), "prefs": sp, "days": days,
        "reserve": _reserve_from(pool, days), "catalog": {k: pool[k] for k in ("lunch", "dinner")},
        "warnings": warnings,
        "mode": "Demo" if llm["provider"] == PROVIDER_DEMO else llm["provider"],
    }


# --------------------------------------------------------------------------- #
# Costs & routes
# --------------------------------------------------------------------------- #
def day_cost_local(day: Dict, party_size: int) -> float:
    return sum(i["cost_local"] for s in day["slots"] for i in s["items"]) * party_size


def day_transit_km(day: Dict) -> float:
    pts = [i for s in day["slots"] for i in s["items"]]
    return sum(_dist(a, b) for a, b in zip(pts, pts[1:]))


def to_usd_inr(amount_local: float, fx: Dict) -> Dict:
    usd = amount_local / fx["per_usd"] if fx["per_usd"] else 0.0
    return {"local": amount_local, "usd": usd, "inr": usd * fx["inr_per_usd"]}


def fmt_num(x: float) -> str:
    return "{:,.0f}".format(x) if abs(x) >= 100 else "{:,.1f}".format(x)


def money_str(amount_local: float, fx: Dict) -> str:
    if amount_local <= 0:
        return "Free"
    m = to_usd_inr(amount_local, fx)
    return "%s %s  |  USD %s  |  INR %s" % (fx["local"], fmt_num(m["local"]), fmt_num(m["usd"]), fmt_num(m["inr"]))


def budget_summary(itin: Dict) -> Dict:
    """Per-day and cumulative totals plus the target for the chosen budget level."""
    p, fx = itin["prefs"], itin["fx"]
    rows, running = [], 0.0
    for d in itin["days"]:
        cost = day_cost_local(d, p["party_size"])
        running += cost
        conv = to_usd_inr(running, fx)
        rows.append({"Day": d["day"], "Day cost (%s)" % fx["local"]: round(cost, 1),
                     "Cumulative (%s)" % fx["local"]: round(running, 1),
                     "Cumulative (USD)": round(conv["usd"], 1), "Cumulative (INR)": round(conv["inr"])})
    target_usd = DAILY_BUDGET_USD[p["budget"]] * p["party_size"] * len(itin["days"])
    return {"rows": rows, "total_local": running, "total_usd": to_usd_inr(running, fx)["usd"],
            "total_inr": to_usd_inr(running, fx)["inr"], "target_usd": target_usd,
            "target_inr": target_usd * fx["inr_per_usd"],
            "transit_km": sum(day_transit_km(d) for d in itin["days"])}


# --------------------------------------------------------------------------- #
# Editing: swap one slot, regenerate one day
# --------------------------------------------------------------------------- #
def _llm_swap_prompt(itin: Dict, day: Dict, slot_name: str, old: Dict, instruction: str) -> str:
    others = [i["name"] for s in day["slots"] for i in s["items"]]
    all_used = sorted(_used_names(itin["days"]))
    centre = _centroid([i for s in day["slots"] for i in s["items"]])
    p = itin["prefs"]
    return (
        "In a %s trip, replace ONE activity. Slot: %s. Current activity: %s.\n"
        "Traveller request: %s\n"
        "Constraints: stay within about 5 km of (%.4f, %.4f); budget level %s; dietary needs %s; "
        "do NOT reuse any of: %s. Currently planned today: %s.\n"
        "Return ONE JSON object with keys name, area, lat, lon, description (max 20 words), "
        "cost_local (per person, %s, number), duration_hrs, tags (2-4 lowercase words), type (sight or leisure). "
        "Must be a real, currently operating place."
    ) % (itin["destination"], slot_name, old["name"], instruction, centre["lat"], centre["lon"],
         p["budget"], p["diet"], "; ".join(all_used), "; ".join(others), itin["fx"]["local"])


def swap_activity(itin: Dict, day_idx: int, slot_name: str, item_idx: int,
                  instruction: str, llm: Dict) -> Dict:
    """Replace one activity in-place; every other day and slot is untouched."""
    instruction = instruction.strip()
    if not instruction:
        raise PlannerError("Describe what you want instead (e.g. 'Find vegetarian lunch spot').")
    day = itin["days"][day_idx]
    slot = next(s for s in day["slots"] if s["slot"] == slot_name)
    old = slot["items"][item_idx]
    cat = _slot_category(slot_name)
    new_item = None

    if llm["provider"] != PROVIDER_DEMO:
        try:
            raw = ask_json(llm["provider"], llm["api_key"], llm["model"],
                           _llm_swap_prompt(itin, day, slot_name, old, instruction))
            new_item = normalise_item(raw, "meal" if cat != "attractions" else "sight")
        except LLMError as exc:
            raise PlannerError(str(exc))
        if new_item is None:
            raise PlannerError("The AI did not return a usable replacement. Please try again.")
    else:
        centre = _centroid([i for s in day["slots"] for i in s["items"]])
        here = {i["name"] for s in day["slots"] for i in s["items"]}
        # (item, location-in-plan or None if it comes from the unused reserve)
        cands = [(c, None) for c in itin["reserve"].get(cat, []) if c["name"] not in here]
        if cat != "attractions":  # meals may repeat a favourite venue
            known = {c["name"] for c, _ in cands}
            cands += [(c, None) for c in itin.get("catalog", {}).get(cat, [])
                      if c["name"] not in here and c["name"] not in known]
        else:  # attractions can be exchanged with another day (keeps every stop unique)
            for di, other in enumerate(itin["days"]):
                if di == day_idx:
                    continue
                for os_ in other["slots"]:
                    if _slot_category(os_["slot"]) == "attractions":
                        for oi, it in enumerate(os_["items"]):
                            cands.append((it, (os_, oi)))
        if not cands:
            raise PlannerError("No more alternatives are available in demo mode for this slot. "
                               "Add an API key for unlimited swaps.")
        best, where = max(cands, key=lambda t: (
            _instruction_score(t[0], instruction) - 0.3 * _dist(t[0], centre) + (0.25 if t[1] is None else 0)))
        new_item = copy.deepcopy(best)
        if where is not None:           # exchange: the other day receives the item we replace
            where[0]["items"][where[1]] = old
        else:                           # take from reserve, return the old item to it
            itin["reserve"][cat] = [c for c in itin["reserve"].get(cat, []) if c["name"] != best["name"]]
            if old["name"] not in {c["name"] for c in itin["reserve"][cat]}:
                itin["reserve"][cat].append(old)

    slot["items"][item_idx] = new_item
    return {"old": old, "new": new_item}


def regenerate_day(itin: Dict, day_idx: int, instruction: str, llm: Dict) -> None:
    """Rebuild a single day using fresh places; other days stay exactly as they are."""
    prefs = dict(itin["prefs"])
    prefs["start_date"] = itin["prefs"]["start_date"]
    old_day = itin["days"][day_idx]
    other_names = _used_names([d for i, d in enumerate(itin["days"]) if i != day_idx])

    if llm["provider"] == PROVIDER_DEMO:
        pool = {"attractions": list(itin["reserve"]["attractions"]),
                "lunch": list(itin["reserve"]["lunch"]),
                "dinner": list(itin["reserve"]["dinner"])}
        for s in old_day["slots"]:  # yesterday's picks become candidates again
            pool[_slot_category(s["slot"])].extend(s["items"])
        for k in pool:
            seen, uniq = set(), []
            for i in pool[k]:
                if i["name"] not in seen and i["name"] not in other_names:
                    seen.add(i["name"])
                    uniq.append(i)
            pool[k] = uniq
    else:
        pool = get_pool(prefs, llm, itin["destination"], 1,
                        exclude=sorted(other_names), instruction=instruction)
    new_days = build_days(pool, prefs, 1, instruction=instruction, jitter=1.5)
    new_day = new_days[0]
    new_day.update({"day": old_day["day"], "date": old_day["date"]})
    itin["days"][day_idx] = new_day

    known = {k: list(itin["reserve"][k]) for k in itin["reserve"]}
    for s in old_day["slots"]:
        known[_slot_category(s["slot"])].extend(s["items"])
    for k in known:
        known[k].extend(pool.get(k, []))
    used = _used_names(itin["days"])
    for k in known:
        seen, uniq = set(), []
        for i in known[k]:
            if i["name"] not in used and i["name"] not in seen:
                seen.add(i["name"])
                uniq.append(i)
        itin["reserve"][k] = uniq
