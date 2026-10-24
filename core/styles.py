"""Wanderlust-inspired CSS injected into Streamlit."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
:root { --teal:#0F766E; --teal-d:#115E59; --sunset:#F97316; --sand:#FFF7ED; --mist:#F0FDFA; --ink:#1F2937; }
html, body, [class*="css"] { font-family:'Poppins', sans-serif; }
.stApp { background: linear-gradient(180deg, #F0FDFA 0%, #FFFFFF 38%, #FFF7ED 100%); color: var(--ink); }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0F766E 0%, #115E59 100%); }
[data-testid="stSidebar"] * { color: #F0FDFA !important; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] [data-baseweb="select"] * { color: #1F2937 !important; }
.hero { background: linear-gradient(120deg, #0F766E 0%, #14B8A6 55%, #F97316 130%); border-radius: 22px;
        padding: 28px 34px; color: white; box-shadow: 0 10px 30px rgba(15,118,110,.25); margin-bottom: 18px; }
.hero h1 { font-family:'Playfair Display', serif; font-size: 2.2rem; margin: 0 0 4px 0; color: white; }
.hero p { margin: 0; opacity: .95; font-size: 1.02rem; }
.badge { display:inline-block; padding: 3px 11px; border-radius: 999px; background: rgba(15,118,110,.1);
         color: var(--teal-d); font-size: .75rem; font-weight: 600; margin: 2px 4px 2px 0; }
.badge.warm { background: rgba(249,115,22,.12); color: #C2410C; }
.card { background: white; border-radius: 18px; padding: 18px 20px; box-shadow: 0 4px 18px rgba(0,0,0,.07);
        border: 1px solid #E5E7EB; margin-bottom: 12px; }
.card h3 { margin: 0 0 4px 0; color: var(--teal-d); font-family:'Playfair Display', serif; }
.rec-score { float:right; background: var(--sunset); color:white; padding: 4px 12px; border-radius: 999px;
             font-weight:700; font-size:.85rem; }
.slot-label { font-weight: 600; color: var(--teal-d); margin: 14px 0 6px 0; font-size: 1.0rem;
              border-left: 4px solid var(--sunset); padding-left: 10px; }
.act { background: white; border-radius: 14px; padding: 12px 16px; margin-bottom: 8px;
       border: 1px solid #E5E7EB; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.act b { color: var(--ink); font-size: 1.0rem; }
.act .meta { color: #6B7280; font-size: .82rem; }
.act .cost { color: #C2410C; font-weight: 600; font-size: .85rem; margin-top: 4px; }
.stButton > button, .stDownloadButton > button { border-radius: 999px; font-weight: 600; border: none;
        background: linear-gradient(90deg, #0F766E, #14B8A6); color: white; padding: .5rem 1.3rem; }
.stButton > button:hover, .stDownloadButton > button:hover { background: linear-gradient(90deg, #F97316, #FB923C); color: white; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { background: white; border-radius: 12px 12px 0 0; padding: 8px 18px; font-weight: 600; }
.stTabs [aria-selected="true"] { background: var(--teal) !important; color: white !important; }
[data-testid="stMetric"] { background: white; border-radius: 14px; padding: 10px 14px; border: 1px solid #E5E7EB; }
</style>
"""

HERO = """
<div class="hero">
  <h1>🧭 Personalized Travel Itinerary Planner</h1>
  <p>Day-by-day plans that cluster nearby attractions, so you spend your trip exploring - not commuting.</p>
</div>
"""
