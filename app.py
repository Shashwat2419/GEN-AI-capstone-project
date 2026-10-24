"""Personalized Travel Itinerary Planner - Skill Wallet Capstone Project 4.

Run locally:   streamlit run app.py
"""
import copy
import json
from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

from core import storage
from core.config import (
    APP_NAME, BUDGETS, DEFAULT_MODELS, DIETS, INTERESTS, MAX_DAYS, PACES, PARTIES,
    PROVIDER_DEMO, PROVIDERS, SLOT_ICONS, SWAP_SUGGESTIONS, VIBES,
)
from core.llm import LLMError
from core.pdf_export import build_pdf
from core.planner import (
    PlannerError, budget_summary, day_cost_local, day_transit_km, generate_itinerary,
    money_str, regenerate_day, swap_activity,
)
from core.recommender import recommend
from core.styles import CSS, HERO

st.set_page_config(page_title=APP_NAME, page_icon="🧭", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# State helpers
# --------------------------------------------------------------------------- #
def init_state():
    defaults = {"itinerary": None, "recs": None, "undo": [], "flash": None, "trip_id": None}
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)


def flash(msg):
    st.session_state["flash"] = msg


def pick_city(city):
    """Button callback - widget state may be changed safely inside callbacks."""
    st.session_state["destination"] = city
    flash("%s selected. Open the Itinerary tab and press Generate." % city)


def _secret(name):
    try:
        return st.secrets.get(name, "")
    except Exception:  # no secrets file configured
        return ""


def sidebar_llm():
    """Render the AI settings and return the active LLM config."""
    st.sidebar.markdown("## ⚙️ AI Settings")
    provider = st.sidebar.selectbox("AI provider", PROVIDERS, key="provider")
    llm = {"provider": PROVIDER_DEMO, "api_key": "", "model": ""}
    if provider == PROVIDER_DEMO:
        st.sidebar.info("Demo mode uses built-in data for Jaipur, Goa, Manali, Paris and Bangkok. "
                        "Add a Gemini or Groq key to plan any destination.")
        return llm
    key = st.sidebar.text_input("%s API key" % provider, type="password", key="api_key",
                                help="Kept only in this browser session. Never written to disk.")
    key = key or _secret("%s_API_KEY" % provider.upper())
    model = st.sidebar.text_input("Model", value=DEFAULT_MODELS[provider], key="model_%s" % provider)
    if not key:
        st.sidebar.warning("No key yet - running in demo mode.")
        return llm
    st.sidebar.success("%s connected" % provider)
    return {"provider": provider, "api_key": key, "model": model.strip() or DEFAULT_MODELS[provider]}


def sidebar_fx(itin):
    if not itin:
        return
    fx = itin["fx"]
    st.sidebar.markdown("## 💱 Exchange rates")
    st.sidebar.caption("Approximate - edit to match today's rate.")
    if fx["local"] != "USD":
        fx["per_usd"] = st.sidebar.number_input("1 USD = ? %s" % fx["local"], min_value=0.0001,
                                                value=float(fx["per_usd"]), format="%.4f")
    fx["inr_per_usd"] = st.sidebar.number_input("1 USD = ? INR", min_value=1.0,
                                                value=float(fx["inr_per_usd"]), format="%.2f")


# --------------------------------------------------------------------------- #
# Preferences form
# --------------------------------------------------------------------------- #
def preferences_form():
    with st.container(border=True):
        st.markdown("### 🎒 Trip preferences")
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.text_input("Destination (leave blank if undecided)", key="destination",
                      placeholder="e.g. Jaipur, Paris, Bangkok...")
        c2.selectbox("Open-ended vibe", VIBES, key="vibe",
                     help="Used by the Smart Destination Recommender.")
        c3.slider("Trip duration (days)", 1, MAX_DAYS, 4, key="days")
        c4, c5, c6, c7 = st.columns(4)
        c4.date_input("Travel start date", value=date.today() + timedelta(days=21),
                      min_value=date.today(), key="start_date")
        c5.selectbox("Budget level", BUDGETS, index=1, key="budget")
        c6.selectbox("Travel party", list(PARTIES), index=1, key="party")
        c7.selectbox("Pace", PACES, index=1, key="pace")
        c8, c9 = st.columns([2, 1])
        c8.multiselect("Interests", INTERESTS, default=["Food", "History"], key="interests")
        c9.selectbox("Dietary needs", DIETS, key="diet")


def collect_prefs():
    ss = st.session_state
    start = ss.start_date
    return {
        "destination": ss.destination.strip(), "vibe": ss.vibe, "days": int(ss.days),
        "start_date": start, "budget": ss.budget, "party": ss.party,
        "party_size": PARTIES[ss.party], "pace": ss.pace, "interests": list(ss.interests),
        "diet": ss.diet, "month_name": start.strftime("%B"),
    }


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def badges(tags, warm=False):
    cls = "badge warm" if warm else "badge"
    return "".join('<span class="%s">%s</span>' % (cls, escape(str(t))) for t in tags)


def activity_card(item, fx, party_size):
    return (
        '<div class="act"><b>%s</b> <span class="meta">- %s</span><br>'
        '<span class="meta">%s</span><br>%s'
        '<div class="cost">%s <span class="meta">(%d traveller%s, ~%s h)</span></div></div>'
    ) % (escape(item["name"]), escape(item["area"]), escape(item["description"]),
         badges(item["tags"][:4]), escape(money_str(item["cost_local"] * party_size, fx)),
         party_size, "" if party_size == 1 else "s", ("%g" % item["duration_hrs"]))


def render_day(day, itin):
    p, fx = itin["prefs"], itin["fx"]
    st.caption("📅 %s  |  🚶 about %.1f km between stops  |  💰 %s" % (
        day["date"], day_transit_km(day), money_str(day_cost_local(day, p["party_size"]), fx)))
    left, right = st.columns([3, 2])
    with left:
        for slot in day["slots"]:
            st.markdown('<div class="slot-label">%s %s</div>' % (SLOT_ICONS.get(slot["slot"], "📍"), slot["slot"]),
                        unsafe_allow_html=True)
            for it in slot["items"]:
                st.markdown(activity_card(it, fx, p["party_size"]), unsafe_allow_html=True)
    with right:
        pts = [i for s in day["slots"] for i in s["items"]]
        st.map(pd.DataFrame([{"lat": i["lat"], "lon": i["lon"]} for i in pts]), zoom=11)
        st.caption("Stops this day: " + " → ".join(i["name"] for i in pts))


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
def tab_recommender(prefs, llm):
    st.markdown("#### Not sure where to go?")
    st.write("Pick a vibe, budget, travel date and interests above - we'll match your top 3 destinations.")
    if st.button("✨ Recommend destinations", key="btn_rec"):
        with st.spinner("Matching destinations..."):
            try:
                st.session_state["recs"] = recommend(prefs, llm)
            except (PlannerError, LLMError) as exc:
                st.error(str(exc))
            except Exception as exc:  # never crash the UI
                st.error("Unexpected error: %s" % exc)
    recs = st.session_state["recs"]
    if not recs:
        return
    cols = st.columns(len(recs))
    for col, r in zip(cols, recs):
        with col:
            st.markdown(
                '<div class="card"><span class="rec-score">%d%% match</span><h3>%s</h3>'
                '<div class="meta">%s</div><p>%s</p>%s<p style="margin-top:8px">🌤️ %s<br>💵 ~USD %d per person/day</p></div>'
                % (r["match"], escape(r["city"]), escape(r["country"]), escape(r["why"]),
                   badges(r["tags"], warm=True), escape(r["weather"]), int(r["daily_usd"])),
                unsafe_allow_html=True)
            st.button("Plan this trip", key="plan_%s" % r["city"], on_click=pick_city, args=(r["city"],))


def tab_itinerary(prefs, llm):
    if st.button("🗺️ Generate optimized itinerary", key="btn_gen"):
        with st.spinner("Clustering attractions and building your days..."):
            try:
                st.session_state["itinerary"] = generate_itinerary(prefs, llm)
                st.session_state["undo"] = []
                st.session_state["trip_id"] = None
                st.rerun()
            except (PlannerError, LLMError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error("Unexpected error while planning: %s" % exc)
    itin = st.session_state["itinerary"]
    if not itin:
        st.info("Set your preferences, then press **Generate**. Tip: use Tab 1 if you have no destination yet.")
        return
    p, fx = itin["prefs"], itin["fx"]
    summ = budget_summary(itin)
    st.markdown("### %s, %s" % (itin["destination"], itin["country"]))
    st.write(itin["summary"])
    for w in itin.get("warnings", []):
        st.warning(w)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Days / travellers", "%d / %d" % (len(itin["days"]), p["party_size"]))
    m2.metric("Estimated total", "%s %s" % (fx["local"], "{:,.0f}".format(summ["total_local"])),
              "USD {:,.0f} | INR {:,.0f}".format(summ["total_usd"], summ["total_inr"]), delta_color="off")
    m3.metric("%s budget target" % p["budget"], "USD {:,.0f}".format(summ["target_usd"]),
              "INR {:,.0f}".format(summ["target_inr"]), delta_color="off")
    m4.metric("Total transit", "%.1f km" % summ["transit_km"], "clustered by area", delta_color="off")
    used = summ["total_usd"] / summ["target_usd"] if summ["target_usd"] else 0
    st.progress(min(1.0, used), text="Budget used: %d%% of target%s" % (
        round(used * 100), " - over budget" if used > 1 else ""))

    for idx, day in enumerate(itin["days"]):
        with st.expander("Day %d - %s" % (day["day"], day["theme"]), expanded=(idx == 0)):
            render_day(day, itin)

    st.markdown("#### 📈 Running budget tracker")
    st.dataframe(summ["rows"], hide_index=True)
    st.line_chart({"Cumulative USD": [r["Cumulative (USD)"] for r in summ["rows"]]})
    if itin.get("tips"):
        st.markdown("#### 💡 Local tips")
        for t in itin["tips"]:
            st.markdown("- " + t)
    st.caption("Mode: %s. Costs are estimates per traveller multiplied by party size; "
               "confirm opening hours and prices before visiting." % itin["mode"])


def tab_customize(llm):
    itin = st.session_state["itinerary"]
    if not itin:
        st.info("Generate an itinerary first (Tab 2), then come back to customize it.")
        return
    st.markdown("#### Change one slot - or rebuild one day - without touching the rest of your plan")
    c1, c2, c3 = st.columns(3)
    day_idx = c1.selectbox("Day", range(len(itin["days"])), format_func=lambda i: "Day %d - %s" % (
        itin["days"][i]["day"], itin["days"][i]["theme"]), key="sw_day")
    day = itin["days"][day_idx]
    slot_names = [s["slot"] for s in day["slots"]]
    slot_name = c2.selectbox("Time slot", slot_names, key="sw_slot")
    slot = next(s for s in day["slots"] if s["slot"] == slot_name)
    item_idx = c3.selectbox("Activity", range(len(slot["items"])),
                            format_func=lambda i: slot["items"][i]["name"], key="sw_item")

    st.markdown("**Quick vibes**")
    chips = st.columns(len(SWAP_SUGGESTIONS))
    for col, text in zip(chips, SWAP_SUGGESTIONS):
        col.button(text, key="chip_" + text,
                   on_click=lambda t=text: st.session_state.__setitem__("sw_text", t))
    instruction = st.text_input("Or describe what you want", key="sw_text",
                                placeholder="e.g. Swap museum for outdoor market")

    b1, b2, b3 = st.columns(3)
    if b1.button("🔄 Swap this activity", key="btn_swap"):
        snapshot = copy.deepcopy(itin)
        try:
            with st.spinner("Finding a better fit..."):
                res = swap_activity(itin, day_idx, slot_name, item_idx, instruction, llm)
            st.session_state["undo"].append(snapshot)
            flash("Swapped %s → %s" % (res["old"]["name"], res["new"]["name"]))
            st.rerun()
        except (PlannerError, LLMError) as exc:
            st.session_state["itinerary"] = snapshot
            st.error(str(exc))
    if b2.button("♻️ Regenerate whole day", key="btn_regen"):
        snapshot = copy.deepcopy(itin)
        try:
            with st.spinner("Rebuilding Day %d..." % day["day"]):
                regenerate_day(itin, day_idx, instruction, llm)
            st.session_state["undo"].append(snapshot)
            flash("Day %d regenerated - other days untouched." % day["day"])
            st.rerun()
        except (PlannerError, LLMError) as exc:
            st.session_state["itinerary"] = snapshot
            st.error(str(exc))
    if b3.button("↩️ Undo last change", key="btn_undo", disabled=not st.session_state["undo"]):
        st.session_state["itinerary"] = st.session_state["undo"].pop()
        flash("Reverted the last change.")
        st.rerun()

    st.markdown("---")
    st.markdown("**Current plan for Day %d**" % day["day"])
    render_day(day, itin)


def tab_trips():
    itin = st.session_state["itinerary"]
    st.markdown("#### 💾 Save the current plan")
    if itin:
        default = "%s - %d days" % (itin["destination"], len(itin["days"]))
        name = st.text_input("Trip name", value=default, key="trip_name_%s" % default)
        s1, s2, s3 = st.columns([1, 1, 2])
        try:
            if s1.button("Save as new trip", key="btn_save"):
                st.session_state["trip_id"] = storage.save_trip(name.strip() or default, itin)
                flash("Trip saved to your history.")
                st.rerun()
            if st.session_state["trip_id"] and s2.button("Update saved trip", key="btn_update"):
                storage.save_trip(name.strip() or default, itin, st.session_state["trip_id"])
                flash("Saved trip updated.")
                st.rerun()
        except storage.StorageError as exc:
            st.error(str(exc))
        try:
            s3.download_button("📄 Export offline PDF guide", data=build_pdf(itin),
                               file_name="%s_itinerary.pdf" % itin["destination"].replace(" ", "_"),
                               mime="application/pdf", key="dl_pdf_current")
        except Exception as exc:
            st.error("Could not build the PDF: %s" % exc)
    else:
        st.info("No active itinerary yet - generate one in Tab 2.")

    st.markdown("#### 🗂️ Trip history")
    try:
        trips = storage.list_trips()
    except storage.StorageError as exc:
        st.error(str(exc))
        return
    if not trips:
        st.caption("No saved trips yet.")
    for t in trips:
        with st.expander("%s  -  %s (%d days)  |  updated %s" % (t["name"], t["destination"], t["num_days"], t["updated_at"])):
            try:
                saved = storage.load_trip(t["id"])
            except storage.StorageError as exc:
                st.error(str(exc))
                continue
            st.write(saved.get("summary", ""))
            for d in saved["days"]:
                st.markdown("**Day %d - %s:** %s" % (d["day"], d["theme"], " → ".join(
                    i["name"] for s in d["slots"] for i in s["items"])))
            a, b, c, d_ = st.columns(4)
            if a.button("Load into planner", key="load_%d" % t["id"]):
                st.session_state["itinerary"] = saved
                st.session_state["trip_id"] = t["id"]
                st.session_state["undo"] = []
                flash("Loaded '%s'. See Tabs 2 and 3." % t["name"])
                st.rerun()
            try:
                b.download_button("PDF", data=build_pdf(saved), file_name="trip_%d.pdf" % t["id"],
                                  mime="application/pdf", key="pdf_%d" % t["id"])
            except Exception as exc:
                b.error("PDF failed: %s" % exc)
            c.download_button("JSON", data=json.dumps(saved, indent=2), file_name="trip_%d.json" % t["id"],
                              mime="application/json", key="json_%d" % t["id"])
            if d_.button("Delete", key="del_%d" % t["id"]):
                try:
                    storage.delete_trip(t["id"])
                    if st.session_state["trip_id"] == t["id"]:
                        st.session_state["trip_id"] = None
                    flash("Trip deleted.")
                    st.rerun()
                except storage.StorageError as exc:
                    st.error(str(exc))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    init_state()
    llm = sidebar_llm()
    sidebar_fx(st.session_state["itinerary"])
    st.markdown(HERO, unsafe_allow_html=True)
    if st.session_state["flash"]:
        st.toast(st.session_state["flash"])
        st.session_state["flash"] = None
    preferences_form()
    prefs = collect_prefs()
    t1, t2, t3, t4 = st.tabs(["🌍 Destination Recommender", "🗺️ Day-by-Day Itinerary",
                              "🎨 Vibe Customization", "🧳 Trips & PDF Export"])
    with t1:
        tab_recommender(prefs, llm)
    with t2:
        tab_itinerary(prefs, llm)
    with t3:
        tab_customize(llm)
    with t4:
        tab_trips()


main()
