# 🧭 Personalized Travel Itinerary Planner
Skill Wallet Capstone Project 4 - AI-powered, day-by-day trip planning in Streamlit.

## Features
| Tab | What it does |
|-----|--------------|
| 🌍 Destination Recommender | Top 3 cities for your vibe, budget, travel month and interests (with match %, weather and highlight tags) |
| 🗺️ Day-by-Day Itinerary | 4 sequential slots per day, **geographic clustering** (balanced k-means + nearest-neighbour routing), per-activity costs in local currency / USD / INR, running budget tracker, route map |
| 🎨 Vibe Customization | "Swap museum for outdoor market", "Find vegetarian lunch spot", regenerate a single day, undo |
| 🧳 Trips & PDF Export | SQLite trip history (save / load / delete) and a one-click offline PDF guide with emergency contacts + checklist |

Works in **Demo mode** with no key (Jaipur, Goa, Manali, Paris, Bangkok). Add a Gemini or Groq key in the sidebar to plan any destination.

## Run in VS Code
1. Install Python 3.9+ and the VS Code *Python* extension.
2. Open this folder in VS Code (`File > Open Folder`).
3. Terminal > New Terminal, then:
   ```bash
   python -m venv .venv
   # Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. Press **Ctrl+Shift+P > Python: Select Interpreter** and choose `.venv`. Press **F5** to debug (launch config included).

## API keys
- Gemini: https://aistudio.google.com/apikey - Groq: https://console.groq.com/keys
- Paste into the sidebar, or create `.streamlit/secrets.toml` (git-ignored):
  ```toml
  GEMINI_API_KEY = "your-key"
  GROQ_API_KEY = "your-key"
  ```
- Model names change over time; edit the **Model** box in the sidebar if one is retired.

## Deploy on Streamlit Community Cloud
Push to GitHub > share.streamlit.io > New app > main file `app.py` > add keys under *Settings > Secrets*.
(SQLite data is ephemeral on the free tier; swap `core/storage.py` for Supabase later without changing the UI.)

## Project layout
```
app.py                 Streamlit UI (4 tabs)
core/config.py         options, slots, defaults
core/llm.py            Gemini / Groq REST client + JSON parsing
core/planner.py        clustering, itinerary build, costs, swap, regenerate
core/recommender.py    destination matching
core/storage.py        SQLite persistence
core/pdf_export.py     ReportLab PDF guide
core/demo_data.py      offline data (approximate coordinates / prices)
core/styles.py         wanderlust CSS
```

## Notes
- Exchange rates are static approximations - editable in the sidebar.
- PDFs use currency codes (INR, USD...) because built-in PDF fonts lack the rupee glyph.
- Always verify prices, hours and emergency numbers before travelling.
