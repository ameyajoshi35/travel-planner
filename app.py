import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Inject Streamlit Cloud secrets into env vars (no-op locally when .env is present)
for _key in ["GROQ_API_KEY", "TAVILY_API_KEY"]:
    if not os.environ.get(_key) and _key in st.secrets:
        os.environ[_key] = st.secrets[_key]

import html as html_lib
from groq import RateLimitError
from travel_planner import orchestrator
from travel_planner import availability_agent
from travel_planner import booking_links as blinks
from travel_planner.agents import suggest_destinations
from travel_planner.india_data import STATE_NAMES, STATES, DEPARTURE_CITIES
from travel_planner.models import TripContext

st.set_page_config(page_title="India Travel Planner", page_icon="✈️", layout="wide")

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Poppins', sans-serif; }

.hero {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    border-radius: 24px; padding: 4rem 2rem;
    text-align: center; margin-bottom: 2rem; color: white;
}
.hero h1 {
    font-size: 3.2rem; font-weight: 800; margin: 0;
    background: linear-gradient(90deg, #f7971e, #ffd200);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.hero p { font-size: 1.15rem; color: rgba(255,255,255,0.75); margin: 0.6rem 0 0; }

[data-testid="stForm"] {
    background: white; border-radius: 20px;
    padding: 1rem 2rem 2rem; box-shadow: 0 20px 60px rgba(0,0,0,0.08);
}
[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%) !important;
    color: #1a1a2e !important; border: none !important;
    font-size: 1.1rem !important; font-weight: 700 !important;
    border-radius: 50px !important; padding: 0.85rem 2rem !important;
    box-shadow: 0 8px 25px rgba(247,151,30,0.4) !important;
    transition: all 0.3s !important; width: 100% !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 14px 35px rgba(247,151,30,0.5) !important;
}

.stat-card {
    border-radius: 16px; padding: 1.2rem 1rem;
    color: white; text-align: center; margin-bottom: 0.5rem;
}
.stat-card .icon { font-size: 1.6rem; }
.stat-card .label { font-size: 0.75rem; opacity: 0.8; margin: 2px 0; }
.stat-card .value { font-size: 1.1rem; font-weight: 700; }

.section-title {
    font-size: 1.5rem; font-weight: 700; color: #1a1a2e;
    margin: 2.5rem 0 1.2rem; padding-bottom: 0.4rem;
    border-bottom: 3px solid #f7971e; display: inline-block;
}

/* Destination card */
.dest-card {
    background: white; border-radius: 16px; padding: 1.4rem;
    box-shadow: 0 6px 20px rgba(0,0,0,0.07);
    border-top: 4px solid #f7971e; margin-bottom: 0.5rem;
}
.dest-card h3 { margin: 0 0 2px; color: #1a1a2e; font-size: 1.15rem; }
.dest-card .tagline { color: #764ba2; font-size: 0.85rem; margin: 0 0 10px; font-weight: 600; }
.dest-card .desc { color: #444; font-size: 0.88rem; line-height: 1.6; margin-bottom: 10px; }
.dest-card .history-block {
    background: #fdf6e3; border-left: 3px solid #f7971e;
    padding: 8px 12px; border-radius: 0 8px 8px 0;
    font-size: 0.83rem; color: #555; margin-bottom: 10px; font-style: italic;
}
.fact-tag {
    background: #eef2ff; color: #4338ca; border-radius: 20px;
    padding: 3px 10px; font-size: 0.75rem; font-weight: 500;
    display: inline-block; margin: 2px 2px 0 0;
}
.activity-tag {
    background: #ecfdf5; color: #065f46; border-radius: 20px;
    padding: 3px 10px; font-size: 0.75rem; font-weight: 500;
    display: inline-block; margin: 2px 2px 0 0;
}
.highlight-tag {
    background: #f3eeff; color: #5b21b6; border-radius: 20px;
    padding: 3px 10px; font-size: 0.75rem; font-weight: 500;
    display: inline-block; margin: 2px 2px 0 0;
}

/* Day card */
.day-card {
    background: white; border-radius: 16px; padding: 1.4rem 1.6rem;
    box-shadow: 0 4px 15px rgba(0,0,0,0.06);
    border-left: 5px solid #667eea; margin-bottom: 1rem;
}
.day-badge {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white; border-radius: 20px; padding: 3px 14px;
    font-size: 0.78rem; font-weight: 600; display: inline-block; margin-bottom: 6px;
}
.day-card h4 { margin: 4px 0 2px; color: #1a1a2e; font-size: 1.05rem; }
.day-card .day-loc { color: #888; font-size: 0.82rem; margin-bottom: 10px; }
.fun-highlight {
    background: linear-gradient(135deg, #ffecd2, #fcb69f);
    border-radius: 10px; padding: 8px 14px;
    font-size: 0.85rem; color: #7b341e; font-weight: 600; margin-bottom: 12px;
}
.time-section { margin: 8px 0; }
.time-label {
    font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; margin-bottom: 3px;
}
.time-content { font-size: 0.88rem; color: #444; line-height: 1.55; }
.stay-line { color: #667eea; font-size: 0.82rem; margin-top: 12px; font-weight: 500; }

/* Hotel card */
.hotel-card {
    background: white; border-radius: 16px; padding: 1.2rem;
    box-shadow: 0 4px 15px rgba(0,0,0,0.06);
    border-top: 4px solid #4facfe; margin-bottom: 0.5rem;
}
.hotel-card h4 { margin: 0 0 4px; color: #1a1a2e; font-size: 1rem; }
.hotel-card .hotel-meta { color: #888; font-size: 0.82rem; margin-bottom: 4px; }
.hotel-card .hotel-price { font-size: 1.3rem; font-weight: 700; color: #4facfe; }
.hotel-card .hotel-price span { font-size: 0.75rem; font-weight: 400; color: #aaa; }
.hotel-card .why-pick { font-size: 0.82rem; color: #555; margin-top: 6px; font-style: italic; }

.transport-card {
    background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
    border-radius: 16px; padding: 1.3rem 1.5rem;
    color: #333; font-size: 0.9rem; line-height: 1.6;
}
.transport-mode-card {
    background: white; border-radius: 16px; padding: 1.4rem;
    box-shadow: 0 4px 18px rgba(0,0,0,0.08);
    height: 100%; display: flex; flex-direction: column;
}
.transport-mode-icon { font-size: 2.2rem; margin-bottom: 0.4rem; }
.transport-mode-title {
    font-size: 1rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.6rem;
    padding-bottom: 0.4rem; border-bottom: 2px solid #f0f0f0;
}
.transport-cost { font-size: 1.5rem; font-weight: 800; margin: 0.5rem 0 0.3rem; }
.transport-detail { font-size: 0.82rem; color: #555; margin: 3px 0; line-height: 1.5; }
.transport-tip {
    font-size: 0.78rem; color: #667eea; margin-top: 10px;
    padding: 6px 10px; background: #f0f3ff; border-radius: 8px;
    font-style: italic; flex-shrink: 0;
}
.sources-label {
    font-size: 0.72rem; color: #999; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase; margin: 12px 0 5px;
}
.source-row { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 4px; }
.source-chip {
    display: inline-flex; align-items: center; gap: 4px;
    background: #f0f4ff; border: 1px solid #c7d2fe;
    border-radius: 20px; padding: 3px 11px;
    font-size: 0.73rem; color: #3730a3; font-weight: 500;
    text-decoration: none; white-space: nowrap;
    max-width: 240px; overflow: hidden; text-overflow: ellipsis;
}
.source-chip:hover { background: #e0e7ff; border-color: #818cf8; color: #1e1b4b; }

.hero-tagline-single {
    text-align: center;
    padding: 2.4rem 1.5rem 2rem;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 55%, #0f3460 100%);
    border-radius: 18px;
    margin-bottom: 1rem;
}
.hero-dest-name {
    font-size: 0.85rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.22em;
    color: #f7971e; margin-bottom: 0.5rem;
}
.hero-tagline-text {
    font-size: 2.3rem; font-weight: 800; font-style: italic;
    color: #fff; line-height: 1.2;
    text-shadow: 0 2px 12px rgba(0,0,0,0.4);
}
.dest-taglines-row {
    display: flex; gap: 12px; margin-bottom: 1rem; flex-wrap: wrap;
}
.dest-tag-card {
    flex: 1; min-width: 160px;
    background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
    border-radius: 14px; padding: 1.3rem 1rem; text-align: center;
    border-bottom: 3px solid #f7971e;
}
.dtc-name {
    font-size: 0.72rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.18em;
    color: #f7971e; margin-bottom: 0.35rem;
}
.dtc-line {
    font-size: 1rem; font-weight: 600; font-style: italic;
    color: #fff; line-height: 1.35;
}

.sugg-header {
    text-align: center; padding: 2rem 1rem 1.2rem;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
    border-radius: 18px; margin-bottom: 1.6rem; color: #fff;
}
.sugg-header h2 { margin: 0 0 6px; font-size: 1.7rem; font-weight: 800; }
.sugg-header p  { margin: 0; opacity: 0.8; font-size: 0.92rem; }

.sugg-card {
    border-radius: 18px; overflow: hidden; background: #fff;
    box-shadow: 0 4px 24px rgba(0,0,0,0.09);
    border: 2px solid #f0f0f0;
    margin-bottom: 1rem;
    transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}
.sugg-card:hover { transform: translateY(-4px); box-shadow: 0 10px 36px rgba(102,126,234,0.18); border-color: #667eea; }
.sugg-img { width: 100%; height: 210px; object-fit: cover; display: block; }
.sugg-body { padding: 1.1rem 1.3rem 0.8rem; }
.sugg-tagline-pill {
    display: inline-block;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff; font-size: 0.68rem; font-weight: 800;
    padding: 3px 10px; border-radius: 20px;
    text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 6px;
}
.sugg-name { font-size: 1.45rem; font-weight: 800; color: #1a1a2e; margin: 3px 0 8px; }
.sugg-desc { font-size: 0.85rem; color: #555; line-height: 1.58; margin-bottom: 10px; }
.sugg-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
.sugg-tag  { background: #f0f4ff; color: #3730a3; font-size: 0.70rem; font-weight: 600; padding: 3px 9px; border-radius: 20px; }
.sugg-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.sugg-pill {
    font-size: 0.76rem; font-weight: 600; padding: 4px 11px;
    border-radius: 20px; white-space: nowrap;
}
.sugg-pill-cost    { background: #ecfdf5; color: #065f46; }
.sugg-pill-budget  { background: #eff6ff; color: #1d4ed8; }
.sugg-pill-weather { background: #fff7ed; color: #c2410c; }
.sugg-pill-time    { background: #fdf4ff; color: #6b21a8; }
.sugg-bestfor { font-size: 0.78rem; color: #777; margin-bottom: 4px; }

.avail-card {
    border-radius: 14px; padding: 1.1rem 1.3rem; margin-bottom: 10px;
    border-left: 5px solid #ccc; background: #fafafa;
}
.avail-card.ok      { border-color: #22c55e; background: #f0fdf4; }
.avail-card.warning { border-color: #f59e0b; background: #fffbeb; }
.avail-card.error   { border-color: #ef4444; background: #fef2f2; }
.avail-icon { font-size: 1.4rem; float: left; margin-right: 10px; line-height: 1.2; }
.avail-title { font-weight: 700; font-size: 0.95rem; color: #1a1a2e; margin-bottom: 2px; }
.avail-status { font-size: 0.82rem; font-weight: 600; margin-bottom: 4px; }
.avail-status.ok      { color: #16a34a; }
.avail-status.warning { color: #d97706; }
.avail-status.error   { color: #dc2626; }
.avail-note { font-size: 0.8rem; color: #555; line-height: 1.45; margin: 0; }
.booking-summary-header {
    text-align: center; padding: 1.5rem 0 1rem;
    background: linear-gradient(135deg, #1a1a2e, #0f3460);
    border-radius: 16px; margin-bottom: 1.5rem;
    color: #fff;
}
.booking-confirm-btn {
    display: block; width: 100%; text-align: center;
    padding: 14px; border-radius: 12px; font-size: 1.05rem; font-weight: 800;
    text-decoration: none; color: #fff; cursor: pointer;
    background: linear-gradient(135deg, #22c55e, #16a34a);
    border: none; margin-top: 8px;
}
.booking-warn-btn {
    display: block; width: 100%; text-align: center;
    padding: 14px; border-radius: 12px; font-size: 1.05rem; font-weight: 800;
    text-decoration: none; color: #fff; cursor: pointer;
    background: linear-gradient(135deg, #f59e0b, #d97706);
    border: none; margin-top: 8px;
}
.book-all-section { background: #f8fafc; border-radius: 16px; padding: 1.5rem; margin-top: 1rem; }
.book-all-category { font-size: 0.78rem; font-weight: 800; text-transform: uppercase;
                     letter-spacing: 0.12em; color: #888; margin: 1rem 0 6px; }
.book-package-cta {
    text-align: center; padding: 1.4rem 1rem;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border-radius: 16px; margin: 1rem 0;
}
.book-package-cta h3 { color: #fff; margin: 0 0 4px; font-size: 1.1rem; font-weight: 700; }
.book-package-cta p  { color: rgba(255,255,255,0.82); margin: 0; font-size: 0.85rem; }

.book-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 6px 0; }
.book-btn {
    display: inline-block; padding: 5px 13px;
    border-radius: 20px; font-size: 0.76rem; font-weight: 700;
    text-decoration: none; color: #fff;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    transition: opacity 0.18s, transform 0.15s;
    white-space: nowrap;
}
.book-btn:hover { opacity: 0.82; transform: translateY(-1px); color: #fff; text-decoration: none; }
.book-label { font-size: 0.7rem; font-weight: 600; color: #888; text-transform: uppercase;
              letter-spacing: 0.06em; margin-bottom: 2px; }

.hotel-city-header {
    font-size: 1.05rem; font-weight: 700; color: #1a1a2e;
    margin: 1.2rem 0 0.6rem; padding: 0.5rem 0.8rem;
    background: linear-gradient(135deg, #f5f7fa, #e8ecf8);
    border-radius: 10px; border-left: 4px solid #667eea;
}
.hotel-type-badge {
    display: inline-block; font-size: 0.7rem; font-weight: 700;
    padding: 2px 8px; border-radius: 20px; margin-bottom: 5px;
}
.badge-budget { background: #ecfdf5; color: #065f46; }
.badge-midrange { background: #fff7ed; color: #9a3412; }
.badge-luxury { background: #fdf4ff; color: #6b21a8; }

.budget-bar-outer { background: #f0f0f0; border-radius: 10px; height: 10px; overflow: hidden; margin: 4px 0 10px; }
.budget-bar-inner { height: 100%; border-radius: 10px; }
.budget-row { display: flex; justify-content: space-between; font-size: 0.88rem; font-weight: 500; color: #333; margin-top: 6px; }
.budget-total-card {
    background: linear-gradient(135deg, #667eea, #764ba2);
    border-radius: 16px; padding: 1.2rem 1.5rem;
    color: white; text-align: right; margin-top: 1rem;
}
.budget-total-card .t-label { font-size: 0.82rem; opacity: 0.8; }
.budget-total-card .t-value { font-size: 2rem; font-weight: 800; }
.budget-total-card .t-note { font-size: 0.78rem; opacity: 0.7; }

.tip-item {
    background: linear-gradient(135deg, #ffecd2, #fcb69f);
    border-radius: 12px; padding: 0.8rem 1.2rem;
    margin-bottom: 0.6rem; color: #7b341e; font-size: 0.88rem;
}

[data-testid="stImage"] img {
    border-radius: 12px; transition: transform 0.3s ease;
}
[data-testid="stImage"] img:hover { transform: scale(1.02); }

.stButton > button {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    color: white !important; border: none !important;
    border-radius: 50px !important; font-weight: 600 !important;
    padding: 0.75rem 2rem !important; transition: all 0.3s !important;
    box-shadow: 0 6px 20px rgba(102,126,234,0.4) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 28px rgba(102,126,234,0.5) !important;
}

.search-anim { text-align: center; padding: 2.5rem 0 1rem; color: #1a1a2e; }
.search-anim .big-icon { font-size: 4rem; animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse {
    0%,100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.1); opacity: 0.7; }
}
.search-step {
    background: white; border-radius: 12px; padding: 0.65rem 1.2rem;
    margin: 0.3rem 0; color: #555; font-size: 0.88rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("page", "form"), ("plan", None), ("plan_text", None),
    ("all_images", []), ("by_dest", {}), ("trip_context", None),
    ("hotels_by_location", {}), ("sources", {}), ("transport", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── FORM PAGE ─────────────────────────────────────────────────────────────────
def show_form():
    st.markdown("""
    <div class="hero">
        <h1>✈️ India Travel Planner</h1>
        <p>From royal Rajasthan to pristine Kerala — discover your perfect Indian adventure</p>
    </div>
    """, unsafe_allow_html=True)

    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]

    with st.form("trip_form"):
        st.markdown("#### Where & When")

        c1, c2 = st.columns(2)
        with c1:
            state_options = ["— Suggest the best destination for me —"] + STATE_NAMES
            selected_state = st.selectbox("🗺️ State / Region *", state_options)
        with c2:
            from_city = st.selectbox(
                "🏠 Departing from *",
                ["— Select city —"] + DEPARTURE_CITIES,
            )

        # Destination field — shown only when a state is selected
        destination = None
        if selected_state != "— Suggest the best destination for me —":
            places = STATES.get(selected_state, [])
            place_options = ["— Suggest best place in this state —"] + places + ["Other (type below)"]
            chosen_place = st.selectbox(f"📍 Place in {selected_state}", place_options)
            if chosen_place == "Other (type below)":
                destination = st.text_input(
                    f"Type your destination in {selected_state}",
                    placeholder=f"Enter a specific place in {selected_state}, India",
                    max_chars=80,
                )
            elif chosen_place != "— Suggest best place in this state —":
                destination = chosen_place

        c3, c4, c5 = st.columns(3)
        with c3:
            travel_month = st.selectbox("📅 Travel month *", months, index=9)
        with c4:
            duration = st.number_input("⏱️ Duration (days) *", min_value=1, max_value=30, value=7)
        with c5:
            num_travelers = st.number_input("👥 Travelers *", min_value=1, max_value=20, value=2)

        st.markdown("#### Who's Coming")
        c6, c7 = st.columns([2, 1])
        with c6:
            traveler_type = st.radio("Traveler type *", ["solo", "couple", "family", "friends"], horizontal=True)
        with c7:
            has_kids = st.checkbox("👧 Traveling with kids")

        st.markdown("#### Budget & Vibe")
        budget = st.slider("💰 Total budget (₹)", min_value=5000, max_value=300000, value=50000, step=5000)
        st.caption(f"Selected: ₹{budget:,}")

        experience = st.multiselect(
            "🎭 What kind of experience?",
            ["nature", "heritage", "adventure", "beach", "religious", "offbeat"],
            default=["heritage", "nature"],
        )

        submitted = st.form_submit_button("🔍  Find My Perfect Trip", use_container_width=True)

    if submitted:
        if from_city == "— Select city —":
            st.error("Please select your departure city.")
            return
        # Sanitize free-text inputs (max 80 chars, strip tags)
        safe_dest = (destination or "").strip()[:80] if destination else None
        safe_from = from_city.strip()[:80]
        safe_state = selected_state if selected_state != "— Suggest the best destination for me —" else None

        # Destination string enriched with state context for agents
        full_dest = None
        if safe_dest:
            full_dest = f"{safe_dest}, {safe_state}" if safe_state else safe_dest

        st.session_state.trip_context = TripContext(
            destination=full_dest,
            state=safe_state,
            starting_city=safe_from,
            travel_month=travel_month,
            duration_days=int(duration),
            num_travelers=int(num_travelers),
            budget_total=int(budget),
            traveler_type=traveler_type,
            has_kids=has_kids,
            experience_type=experience,
            is_confirmed=True,
        )
        # No specific destination chosen → show suggestion cards first
        st.session_state.pop("suggestions", None)
        if full_dest is None:
            st.session_state.page = "suggestions"
        else:
            st.session_state.page = "searching"
        st.rerun()


# ── SUGGESTIONS PAGE ──────────────────────────────────────────────────────────
def show_suggestions():
    ctx: TripContext = st.session_state.trip_context
    state = ctx.state or "India"
    n     = ctx.num_travelers or 2

    st.markdown(f"""
    <div class="sugg-header">
        <h2>✨ Where in {state} should you go?</h2>
        <p>We've picked 3 places that match your travel style, budget, and travel month.
           Pick the one that excites you most — we'll build a full itinerary instantly.</p>
    </div>
    """, unsafe_allow_html=True)

    # Run suggester (cached in session so Back doesn't re-fetch)
    if "suggestions" not in st.session_state or not st.session_state.suggestions:
        with st.spinner(f"Finding the best places in {state} for you…"):
            try:
                dests = suggest_destinations(ctx)
            except Exception as e:
                st.error(f"Couldn't fetch suggestions ({type(e).__name__}). Please try again.")
                if st.button("← Back to form"):
                    st.session_state.page = "form"
                    st.rerun()
                return
        st.session_state.suggestions = dests
    else:
        dests = st.session_state.suggestions

    if not dests:
        st.warning("No suggestions found. Try changing your interests or travel month.")
        if st.button("← Back"):
            st.session_state.page = "form"
            st.rerun()
        return

    _e = html_lib.escape
    st.markdown(f"**{len(dests)} places to choose from** — pick the one that excites you most.")
    st.markdown("<br>", unsafe_allow_html=True)

    # Render in rows of 3
    for row_start in range(0, len(dests), 3):
        row_dests = dests[row_start: row_start + 3]
        cols = st.columns(3)

        for col, dest in zip(cols, row_dests):
            name       = dest.get("name", "")
            tagline    = _e(dest.get("tagline", ""))
            desc       = _e(dest.get("description", ""))
            highlights = dest.get("highlights", [])
            best_for   = _e(dest.get("best_for", ""))
            cost_pp    = _e(dest.get("approx_cost_per_person", ""))
            budget_fit = _e(dest.get("budget_fit", ""))
            weather    = _e(dest.get("weather_in_month", ""))
            travel_t   = _e(dest.get("travel_time_from_origin", ""))
            images     = dest.get("images", [])

            with col:
                if images:
                    st.image(images[0], use_container_width=True)
                else:
                    st.markdown('<div style="height:210px;background:#f0f4ff;border-radius:12px;"></div>',
                                unsafe_allow_html=True)

                tag_html = "".join(
                    f'<span class="sugg-tag">⚡ {_e(h)}</span>' for h in highlights[:3]
                )
                meta_html = ""
                if cost_pp:
                    meta_html += f'<span class="sugg-pill sugg-pill-cost">💰 {cost_pp}/person</span> '
                if budget_fit:
                    meta_html += f'<span class="sugg-pill sugg-pill-budget">{budget_fit}</span> '
                if weather:
                    meta_html += f'<br><span class="sugg-pill sugg-pill-weather">🌤 {weather}</span> '
                if travel_t:
                    meta_html += f'<span class="sugg-pill sugg-pill-time">🚂 {travel_t}</span>'

                st.markdown(f"""
                <div class="sugg-body">
                    <span class="sugg-tagline-pill">{tagline}</span>
                    <div class="sugg-name">{_e(name)}</div>
                    <p class="sugg-desc">{desc}</p>
                    <div class="sugg-tags">{tag_html}</div>
                    <p class="sugg-bestfor">👥 {best_for}</p>
                    <div class="sugg-meta" style="flex-wrap:wrap; gap:5px;">{meta_html}</div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(
                    f"Plan trip to {name} →",
                    key=f"pick_{name}",
                    use_container_width=True,
                    type="primary",
                ):
                    full_dest = f"{name}, {state}" if state != "India" else name
                    ctx.destination = full_dest
                    st.session_state.trip_context = ctx
                    for k in ["plan", "all_images", "by_dest", "hotels_by_location",
                              "sources", "transport", "availability", "booking_confirmed"]:
                        st.session_state.pop(k, None)
                    st.session_state.page = "searching"
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("← Change trip details"):
        st.session_state.page = "form"
        st.session_state.pop("suggestions", None)
        st.rerun()


# ── SEARCHING PAGE ────────────────────────────────────────────────────────────
def show_searching():
    ctx: TripContext = st.session_state.trip_context
    phase = "planning" if ctx.destination else "suggestion"
    dest_label = ctx.destination or "the perfect destination for you"

    st.markdown(f"""
    <div class="search-anim">
        <div class="big-icon">🔍</div>
        <h2>Planning your trip to {dest_label}…</h2>
        <p style="color:#666; font-size:0.95rem;">Searching travel guides, hotels, and hidden gems</p>
    </div>
    """, unsafe_allow_html=True)

    progress = st.progress(0)
    steps_box = st.container()
    img_preview = st.empty()

    # Clear any stale plan data from previous runs before we start
    for _k in ["plan", "plan_text", "all_images", "by_dest", "hotels_by_location", "sources"]:
        st.session_state[_k] = None if _k in ("plan", "plan_text") else ([] if _k == "all_images" else {})

    all_images: list = []
    by_dest: dict = {}
    hotels_by_location: dict = {}
    sources: dict = {}
    transport: dict = {}
    plan_data = None
    step = 0

    try:
        for event in orchestrator.run(ctx, phase):
            if event["type"] == "searching":
                step += 1
                progress.progress(min(step / 18, 0.95))
                with steps_box:
                    st.markdown(f'<div class="search-step">🔍 {event["query"]}</div>', unsafe_allow_html=True)

            elif event["type"] == "plan":
                plan_data = event["data"]

            elif event["type"] == "transport":
                transport = event

            elif event["type"] == "hotels":
                hotels_by_location = event["by_location"]

            elif event["type"] == "sources":
                sources = event["data"]

            elif event["type"] == "images":
                all_images = event["all"]
                by_dest = event["by_dest"]
                if all_images:
                    img_preview.image(all_images[:4], width=180)

    except RateLimitError:
        st.error(
            "⏳ Groq rate limit reached — the free tier allows a limited number of "
            "requests per minute. Please wait 30–60 seconds and try again."
        )
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            if st.button("🔄  Try Again", use_container_width=True):
                st.session_state.page = "searching"
                st.rerun()
        return
    except Exception as e:
        st.error(f"Something went wrong while building your plan ({type(e).__name__}). Please try again.")
        st.caption(f"Details: {str(e)[:300]}")
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            if st.button("🔄  Try Again", use_container_width=True):
                st.session_state.page = "searching"
                st.rerun()
        return

    progress.progress(1.0)
    st.session_state.plan = plan_data
    st.session_state.transport = transport
    st.session_state.all_images = all_images
    st.session_state.by_dest = by_dest
    st.session_state.hotels_by_location = hotels_by_location
    st.session_state.sources = sources
    st.session_state.page = "results"
    st.rerun()


# ── RESULTS PAGE ──────────────────────────────────────────────────────────────
def show_results():
    plan = st.session_state.plan
    transport: dict = st.session_state.get("transport", {})
    images: list = st.session_state.all_images
    by_dest: dict = st.session_state.by_dest
    hotels_by_location: dict = st.session_state.get("hotels_by_location", {})
    sources: dict = st.session_state.get("sources", {})
    ctx: TripContext = st.session_state.trip_context

    def _source_chips(items: list, label: str = "Sources") -> None:
        """Render a row of clickable source-chip links."""
        valid = [s for s in items if s.get("url", "").startswith("http")][:5]
        if not valid:
            return
        chips = "".join(
            f'<a class="source-chip" href="{s["url"]}" target="_blank" rel="noopener noreferrer">'
            f'🔗 {s["title"][:55]}{"…" if len(s["title"]) > 55 else ""}</a>'
            for s in valid
        )
        st.markdown(
            f'<p class="sources-label">📎 {label}</p><div class="source-row">{chips}</div>',
            unsafe_allow_html=True,
        )

    def _book_buttons(links: list, label: str = "Book now") -> None:
        """Render a row of booking-platform deep-link buttons."""
        if not links:
            return
        btns = "".join(
            f'<a class="book-btn" href="{lnk["url"]}" target="_blank" rel="noopener noreferrer">'
            f'{lnk["label"]}</a>'
            for lnk in links
        )
        st.markdown(
            f'<p class="book-label">{label}</p><div class="book-row">{btns}</div>',
            unsafe_allow_html=True,
        )

    if plan is None:
        st.error("Could not generate a plan. Please try again.")
        if st.button("← Back to form"):
            st.session_state.page = "form"
            st.rerun()
        return

    # ── Destination tagline(s) ────────────────────────────────────────────────
    dest_taglines = [
        (d.get("name", ""), d.get("tagline", ""))
        for d in (plan.get("destinations", []) if plan else [])
        if d.get("tagline")
    ]
    if dest_taglines:
        if len(dest_taglines) == 1:
            name, tagline = dest_taglines[0]
            st.markdown(f"""
            <div class="hero-tagline-single">
                <div class="hero-dest-name">✦ {name} ✦</div>
                <div class="hero-tagline-text">{tagline}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            cards = "".join(
                f'<div class="dest-tag-card">'
                f'<div class="dtc-name">✦ {name} ✦</div>'
                f'<div class="dtc-line">{tagline}</div>'
                f'</div>'
                for name, tagline in dest_taglines
            )
            st.markdown(f'<div class="dest-taglines-row">{cards}</div>', unsafe_allow_html=True)

    # ── Hero image ────────────────────────────────────────────────────────────
    if images:
        st.image(images[0], use_container_width=True)

    # ── Title & overview ──────────────────────────────────────────────────────
    title = plan.get("trip_title", "Your India Adventure") if plan else "Your India Trip"
    overview = plan.get("overview", "") if plan else ""

    st.markdown(f"""
    <div style="text-align:center; padding:1.5rem 0 0.5rem;">
        <h1 style="font-size:2.4rem; font-weight:800; color:#1a1a2e; margin:0;">{title}</h1>
        <p style="font-size:1rem; color:#555; max-width:700px; margin:0.7rem auto 0; line-height:1.65;">{overview}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Stat cards ────────────────────────────────────────────────────────────
    s1, s2, s3, s4 = st.columns(4)
    # html_lib.escape prevents XSS from user-supplied text in HTML context
    _e = html_lib.escape
    dest_label = _e(ctx.destination or (f"{ctx.state}" if ctx.state else "India"))
    for col, (icon, label, val), grad, tc in zip(
        [s1, s2, s3, s4],
        [("📍","From", _e(ctx.starting_city or "")),
         ("⏱️","Duration",f"{ctx.duration_days} days"),
         ("👥","Travelers",f"{ctx.num_travelers} ({_e(ctx.traveler_type or '')})"),
         ("💰","Budget",f"₹{ctx.budget_total:,}")],
        ["linear-gradient(135deg,#667eea,#764ba2)","linear-gradient(135deg,#f7971e,#ffd200)",
         "linear-gradient(135deg,#4facfe,#00f2fe)","linear-gradient(135deg,#43e97b,#38f9d7)"],
        ["white","#1a1a2e","white","#1a1a2e"],
    ):
        with col:
            st.markdown(f'<div class="stat-card" style="background:{grad}; color:{tc};"><div class="icon">{icon}</div><div class="label">{label}</div><div class="value">{val}</div></div>', unsafe_allow_html=True)

    plan_ok = bool(plan and (plan.get("destinations") or plan.get("itinerary")))

    if not plan_ok:
        if images:
            st.markdown('<div class="section-title">📸 Trip Photos</div>', unsafe_allow_html=True)
            gcols = st.columns(4)
            for i, url in enumerate(images[:8]):
                with gcols[i % 4]:
                    st.image(url, use_container_width=True)
        st.error(
            "We couldn't format the plan this time — the search data was collected "
            "successfully but the response couldn't be parsed. Please try again."
        )
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            if st.button("🔄  Try Again", use_container_width=True):
                for key in ["plan", "plan_text", "all_images", "by_dest",
                            "hotels_by_location", "sources", "availability"]:
                    st.session_state.pop(key, None)
                st.session_state.page = "searching"
                st.rerun()
    else:
        # ── Book Complete Package CTA ─────────────────────────────────────────
        st.markdown("""
        <div class="book-package-cta">
            <h3>🎯 Ready to lock this trip in?</h3>
            <p>We'll do a live availability check, then walk you through booking everything — flights, trains, hotels and vehicles — in one go.</p>
        </div>
        """, unsafe_allow_html=True)
        _, cta_col, _ = st.columns([1, 2, 1])
        with cta_col:
            if st.button("🔒 Book Complete Package", use_container_width=True, type="primary"):
                st.session_state.pop("availability", None)
                st.session_state.pop("booking_confirmed", None)
                st.session_state.page = "booking"
                st.rerun()

        # ── Destinations ──────────────────────────────────────────────────────
        destinations = plan.get("destinations", [])
        if destinations:
            st.markdown('<div class="section-title">📍 Places You\'ll Explore</div>', unsafe_allow_html=True)
            dcols = st.columns(min(len(destinations), 3))

            # Build a flat image pool per destination
            img_pool_flat = [img for imgs in by_dest.values() for img in imgs]
            if not img_pool_flat:
                img_pool_flat = images

            for i, dest in enumerate(destinations[:3]):
                dest_name = dest.get("name", "")
                dest_imgs = by_dest.get(dest_name, img_pool_flat[i*3:(i+1)*3])

                with dcols[i]:
                    if dest_imgs:
                        st.image(dest_imgs[0], use_container_width=True)

                    history_html = ""
                    if dest.get("history"):
                        history_html = f'<div class="history-block">📜 {dest["history"]}</div>'

                    facts_html = "".join(
                        f'<span class="fact-tag">⚡ {f}</span>'
                        for f in dest.get("unique_facts", [])[:3]
                    )
                    activities_html = "".join(
                        f'<span class="activity-tag">🎯 {a}</span>'
                        for a in dest.get("fun_activities", [])[:4]
                    )
                    highlights_html = "".join(
                        f'<span class="highlight-tag">✦ {h}</span>'
                        for h in dest.get("highlights", [])[:4]
                    )
                    cost_html = (f'<p style="color:#43e97b; font-weight:600; font-size:0.85rem; margin:8px 0 0;">💰 {dest["estimated_cost"]}</p>'
                                 if dest.get("estimated_cost") else "")

                    st.markdown(f"""
                    <div class="dest-card">
                        <h3>{dest_name}</h3>
                        <p class="tagline">{dest.get("tagline","")}</p>
                        <p class="desc">{dest.get("description","")}</p>
                        {history_html}
                        <div style="margin-bottom:6px;">{facts_html}</div>
                        <div style="margin-bottom:6px;">{activities_html}</div>
                        <div>{highlights_html}</div>
                        {cost_html}
                    </div>
                    """, unsafe_allow_html=True)

                    # Show extra destination images as a small gallery
                    if len(dest_imgs) > 1:
                        extra_cols = st.columns(len(dest_imgs[1:4]))
                        for j, extra_img in enumerate(dest_imgs[1:4]):
                            with extra_cols[j]:
                                st.image(extra_img, use_container_width=True)

        if sources.get("destinations"):
            _source_chips(sources["destinations"], "Destination info sourced from")

        # ── Photo gallery ─────────────────────────────────────────────────────
        gallery = [img for img in images if img not in [by_dest.get(d.get("name",""), [None])[0] for d in destinations]]
        if len(gallery) >= 4:
            st.markdown('<div class="section-title">📸 More from the Trip</div>', unsafe_allow_html=True)
            gcols = st.columns(4)
            for i, url in enumerate(gallery[:8]):
                with gcols[i % 4]:
                    st.image(url, use_container_width=True)

        # ── Itinerary ─────────────────────────────────────────────────────────
        itinerary = plan.get("itinerary", [])
        if itinerary:
            st.markdown('<div class="section-title">📅 Day-by-Day Itinerary</div>', unsafe_allow_html=True)

            for day in itinerary:
                fun_highlight = day.get("fun_highlight", "")
                fh_html = (f'<div class="fun-highlight">⭐ {fun_highlight}</div>' if fun_highlight else "")

                morning = day.get("morning", "")
                afternoon = day.get("afternoon", "")
                evening = day.get("evening", "")
                # Fallback: old-style activities list
                activities = day.get("activities", [])

                if morning or afternoon or evening:
                    time_html = ""
                    if morning:
                        time_html += f'<div class="time-section"><div class="time-label" style="color:#f7971e;">🌅 Morning</div><div class="time-content">{morning}</div></div>'
                    if afternoon:
                        time_html += f'<div class="time-section"><div class="time-label" style="color:#4facfe;">☀️ Afternoon</div><div class="time-content">{afternoon}</div></div>'
                    if evening:
                        time_html += f'<div class="time-section"><div class="time-label" style="color:#764ba2;">🌙 Evening</div><div class="time-content">{evening}</div></div>'
                else:
                    acts_html = "".join(f"<li>{a}</li>" for a in activities)
                    time_html = f'<ul style="color:#444; font-size:0.88rem; padding-left:18px; margin:0;">{acts_html}</ul>'

                stay_html = (f'<p class="stay-line">🏨 Tonight: {day["stay"]}</p>' if day.get("stay") else "")

                st.markdown(f"""
                <div class="day-card">
                    <span class="day-badge">Day {day.get("day","")}</span>
                    <h4>{day.get("title","")}</h4>
                    <p class="day-loc">📍 {day.get("location","")}</p>
                    {fh_html}
                    {time_html}
                    {stay_html}
                </div>
                """, unsafe_allow_html=True)

        # ── Transport — agent-powered mode cards ─────────────────────────────
        flight_data  = transport.get("flight",  {"options": [], "sources": []})
        train_data   = transport.get("train",   {"options": [], "sources": []})
        vehicle_data = transport.get("vehicle", {"options": [], "sources": []})

        if any([flight_data["options"], train_data["options"], vehicle_data["options"]]):
            st.markdown('<div class="section-title">🚀 Getting There</div>', unsafe_allow_html=True)

            def _agent_transport_col(col, icon, title, border_color, cost_color,
                                     agent_data: dict, cost_key: str, links_fn):
                options = agent_data.get("options", [])
                if not options:
                    return
                with col:
                    best = options[0]
                    details_html = "".join(
                        f'<p class="transport-detail"><b>{k.replace("_"," ").title()}:</b> {v}</p>'
                        for k, v in best.items()
                        if k not in {cost_key, "booking_tip"} and v
                    )
                    tip_html = (f'<div class="transport-tip">💡 {best["booking_tip"]}</div>'
                                if best.get("booking_tip") else "")
                    st.markdown(f"""
                    <div class="transport-mode-card" style="border-top:4px solid {border_color};">
                        <div class="transport-mode-icon">{icon}</div>
                        <div class="transport-mode-title">{title}</div>
                        <div class="transport-cost" style="color:{cost_color};">{best.get(cost_key,"")}</div>
                        {details_html}{tip_html}
                    </div>
                    """, unsafe_allow_html=True)

                    _book_buttons(links_fn(ctx), "Book now")

                    # Additional options
                    for opt in options[1:]:
                        alt_details = "".join(
                            f'<p class="transport-detail"><b>{k.replace("_"," ").title()}:</b> {v}</p>'
                            for k, v in opt.items()
                            if k not in {cost_key, "booking_tip"} and v
                        )
                        alt_tip = (f'<div class="transport-tip">💡 {opt["booking_tip"]}</div>'
                                   if opt.get("booking_tip") else "")
                        st.markdown(f"""
                        <div class="transport-mode-card" style="border-top:2px solid {border_color}; margin-top:8px; opacity:0.85;">
                            <div class="transport-mode-title" style="font-size:0.88rem;">Alternative</div>
                            <div class="transport-cost" style="color:{cost_color}; font-size:1.1rem;">{opt.get(cost_key,"")}</div>
                            {alt_details}{alt_tip}
                        </div>
                        """, unsafe_allow_html=True)

                    _source_chips(agent_data.get("sources", []), f"{title} sources")

            tc1, tc2, tc3 = st.columns(3)
            _agent_transport_col(tc1, "✈️", "Flight",         "#4facfe", "#4facfe", flight_data,  "cost_per_person", blinks.flight_links)
            _agent_transport_col(tc2, "🚂", "Train",          "#f7971e", "#f7971e", train_data,   "sleeper",         blinks.train_links)
            _agent_transport_col(tc3, "🚗", "Rented Vehicle", "#43e97b", "#43e97b", vehicle_data, "total_estimate",  blinks.vehicle_links)

        # ── Hotels by overnight-stay location ────────────────────────────────
        overnight_cities = list(dict.fromkeys(
            day.get("stay", day.get("location", "")).strip()
            for day in itinerary
            if day.get("stay") or day.get("location")
        ))

        # Merge with any hotels_by_location keys in case of slight name mismatch
        hotel_cities = list(hotels_by_location.keys()) if hotels_by_location else overnight_cities

        if hotel_cities:
            st.markdown('<div class="section-title">🏨 Where to Stay</div>', unsafe_allow_html=True)

            badge_class = {"Budget": "badge-budget", "Mid-range": "badge-midrange", "Luxury": "badge-luxury"}

            for city in hotel_cities:
                city_hotels = hotels_by_location.get(city, [])
                if not city_hotels:
                    continue
                st.markdown(f'<div class="hotel-city-header">📍 {city}</div>', unsafe_allow_html=True)
                hcols = st.columns(min(len(city_hotels), 3))
                for i, hotel in enumerate(city_hotels[:3]):
                    htype = hotel.get("type", "")
                    badge_cls = badge_class.get(htype, "badge-budget")
                    why_html = (f'<p class="why-pick">"{hotel["why_pick"]}"</p>'
                                if hotel.get("why_pick") else "")
                    rating_html = (f'<span style="color:#f7971e; font-weight:600; font-size:0.82rem;">★ {hotel["rating"]}</span>'
                                   if hotel.get("rating") else "")
                    with hcols[i]:
                        st.markdown(f"""
                        <div class="hotel-card">
                            <span class="hotel-type-badge {badge_cls}">{htype}</span>
                            <h4>{hotel.get("name","")}</h4>
                            <p class="hotel-meta">📍 {city} &nbsp; {rating_html}</p>
                            <div class="hotel-price">{hotel.get("price_per_night","")} <span>/ night</span></div>
                            {why_html}
                        </div>
                        """, unsafe_allow_html=True)
                        _book_buttons(blinks.hotel_links(ctx, city), "Check availability")
                _source_chips(sources.get("hotels", {}).get(city, []), f"Hotel sources — {city}")

        # ── Budget breakdown ──────────────────────────────────────────────────
        budget_data = plan.get("budget", {})
        if budget_data:
            total_est = sum(v for v in budget_data.values() if isinstance(v, (int, float)))
            st.markdown('<div class="section-title">💰 Budget Breakdown</div>', unsafe_allow_html=True)

            bar_colors = ["#667eea", "#f7971e", "#4facfe", "#43e97b"]
            labels = {"transport":"🚂 Transport","accommodation":"🏨 Accommodation",
                      "food":"🍛 Food & Dining","activities":"🎭 Activities"}
            for i, (key, label) in enumerate(labels.items()):
                val = budget_data.get(key, 0)
                if not isinstance(val, (int, float)):
                    continue
                pct = int(val / total_est * 100) if total_est > 0 else 0
                color = bar_colors[i % len(bar_colors)]
                st.markdown(f"""
                <div class="budget-row"><span>{label}</span><span style="color:{color}; font-weight:600;">₹{int(val):,}</span></div>
                <div class="budget-bar-outer"><div class="budget-bar-inner" style="width:{pct}%; background:{color};"></div></div>
                """, unsafe_allow_html=True)

            within = total_est <= ctx.budget_total
            st.markdown(f"""
            <div class="budget-total-card">
                <div class="t-label">Estimated Total</div>
                <div class="t-value">₹{int(total_est):,}</div>
                <div class="t-note">Your budget: ₹{ctx.budget_total:,} &nbsp;|&nbsp; {"✅ Within budget" if within else "⚠️ Slightly over — consider adjusting"}</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Tips ──────────────────────────────────────────────────────────────
        tips = plan.get("tips", [])
        if tips:
            st.markdown('<div class="section-title">💡 Travel Tips</div>', unsafe_allow_html=True)
            for tip in tips:
                st.markdown(f'<div class="tip-item">💡 {tip}</div>', unsafe_allow_html=True)

    # ── Plan another trip ─────────────────────────────────────────────────────
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if st.button("✈️  Plan Another Trip", use_container_width=True):
            for key in ["page", "plan", "all_images", "by_dest",
                        "trip_context", "hotels_by_location", "sources",
                        "availability", "booking_confirmed", "suggestions"]:
                st.session_state.pop(key, None)
            st.rerun()


# ── BOOKING CONFIRMATION PAGE ─────────────────────────────────────────────────
def show_booking():
    ctx: TripContext     = st.session_state.trip_context
    transport: dict      = st.session_state.get("transport", {})
    hotels: dict         = st.session_state.get("hotels_by_location", {})
    plan: dict           = st.session_state.get("plan", {})

    st.markdown("""
    <div class="booking-summary-header">
        <h2 style="margin:0 0 4px; font-size:1.6rem;">🔒 Complete Package Booking</h2>
        <p style="margin:0; opacity:0.82; font-size:0.92rem;">We're checking live availability for every part of your trip</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Run availability check (cached so clicking Confirm doesn't re-run) ──
    if "availability" not in st.session_state:
        with st.spinner("Checking live flight, train, hotel & vehicle availability…"):
            try:
                avail = availability_agent.check(ctx, transport, hotels)
            except Exception as e:
                avail = {
                    "overall": "some_changes",
                    "flight":  {"flag": "warning", "status": "Could not verify", "note": str(e)[:120]},
                    "train":   {"flag": "warning", "status": "Could not verify", "note": "Please check manually."},
                    "vehicle": {"flag": "warning", "status": "Could not verify", "note": "Please check manually."},
                    "hotels":  {c: {"flag": "warning", "status": "Could not verify", "note": "Please check manually."} for c in hotels},
                }
        st.session_state.availability = avail
    else:
        avail = st.session_state.availability

    overall = avail.get("overall", "some_changes")
    FLAG_ICON = {"ok": "✅", "warning": "⚠️", "error": "❌"}
    FLAG_LABEL = {"ok": "Available", "warning": "Check needed", "error": "Unavailable"}

    def _avail_card(title: str, component: dict) -> None:
        flag  = component.get("flag", "warning")
        icon  = FLAG_ICON.get(flag, "⚠️")
        label = FLAG_LABEL.get(flag, flag)
        status = component.get("status", "")
        note   = component.get("note", "")
        st.markdown(f"""
        <div class="avail-card {flag}">
            <span class="avail-icon">{icon}</span>
            <div class="avail-title">{title}</div>
            <div class="avail-status {flag}">{label} — {status}</div>
            <p class="avail-note">{note}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### Availability Status")

    # Flight
    flight_opts = transport.get("flight", {}).get("options", [])
    if flight_opts:
        best_f = flight_opts[0]
        _avail_card(
            f"✈️  Flight — {best_f.get('airlines','')}  {best_f.get('route','')} ({best_f.get('cost_per_person','?')}/person)",
            avail.get("flight", {"flag": "warning", "status": "Not checked", "note": ""}),
        )

    # Train
    train_opts = transport.get("train", {}).get("options", [])
    if train_opts:
        best_t = train_opts[0]
        _avail_card(
            f"🚂  Train — {best_t.get('name','')} {best_t.get('number','')} (3AC: {best_t.get('third_ac','?')})",
            avail.get("train", {"flag": "warning", "status": "Not checked", "note": ""}),
        )

    # Vehicle
    vehicle_opts = transport.get("vehicle", {}).get("options", [])
    if vehicle_opts:
        best_v = vehicle_opts[0]
        _avail_card(
            f"🚗  Vehicle — {best_v.get('vehicle_type','')} ({best_v.get('total_estimate','?')})",
            avail.get("vehicle", {"flag": "warning", "status": "Not checked", "note": ""}),
        )

    # Hotels per city
    avail_hotels = avail.get("hotels", {})
    for city, city_hotels in hotels.items():
        if city_hotels:
            h = city_hotels[0]
            hotel_avail = avail_hotels.get(city, {"flag": "warning", "status": "Not checked", "note": ""})
            _avail_card(
                f"🏨  {city} — {h.get('name','')} {h.get('type','')} ({h.get('price_per_night','?')}/night)",
                hotel_avail,
            )

    # ── Overall status banner ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    has_errors   = any(
        v.get("flag") == "error"
        for v in [avail.get("flight",{}), avail.get("train",{}), avail.get("vehicle",{})]
        + list(avail.get("hotels",{}).values())
    )
    has_warnings = overall != "all_clear"

    if overall == "all_clear":
        st.success("✅ All components look available! You're good to book.")
    elif has_errors:
        st.error("❌ One or more components appear unavailable. We recommend cancelling and replanning.")
    else:
        st.warning("⚠️ Some prices or availability may have changed. Review the details above before proceeding.")

    # ── Action buttons ────────────────────────────────────────────────────────
    if not st.session_state.get("booking_confirmed"):
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if st.button("← Back to Plan", use_container_width=True):
                st.session_state.page = "results"
                st.rerun()
        with bcol2:
            if has_errors:
                st.button("❌ Cannot Book — Replan", use_container_width=True, disabled=True)
            elif has_warnings:
                if st.button("⚠️ Proceed Anyway — Book All", use_container_width=True):
                    st.session_state.booking_confirmed = True
                    st.rerun()
            else:
                if st.button("✅ Confirm — Book All Now", use_container_width=True, type="primary"):
                    st.session_state.booking_confirmed = True
                    st.rerun()

    # ── Booking links (shown after confirmation) ──────────────────────────────
    if st.session_state.get("booking_confirmed"):
        st.markdown("---")
        st.markdown("""
        <div style="text-align:center; margin-bottom:1rem;">
            <h3 style="color:#1a1a2e;">🎉 You're confirmed! Open each link to complete your booking.</h3>
            <p style="color:#666; font-size:0.9rem;">📌 Tip: Book in order — Flights first, then Train, then Hotels. If any step fails, hold off on the others.</p>
        </div>
        """, unsafe_allow_html=True)

        dest = ctx.destination or ""
        n    = ctx.num_travelers or 2

        with st.container():
            # Flight links
            if flight_opts:
                st.markdown('<p class="book-all-category">Step 1 — Flights</p>', unsafe_allow_html=True)
                f_links = blinks.flight_links(ctx)
                cols = st.columns(len(f_links))
                for i, lnk in enumerate(f_links):
                    with cols[i]:
                        st.link_button(f"✈️ {lnk['label']}", lnk["url"], use_container_width=True)

            # Train links
            if train_opts:
                st.markdown('<p class="book-all-category">Step 2 — Train</p>', unsafe_allow_html=True)
                t_links = blinks.train_links(ctx)
                cols = st.columns(len(t_links))
                for i, lnk in enumerate(t_links):
                    with cols[i]:
                        st.link_button(f"🚂 {lnk['label']}", lnk["url"], use_container_width=True)

            # Hotel links per city
            for city in hotels:
                st.markdown(f'<p class="book-all-category">Step 3 — Hotel in {city}</p>', unsafe_allow_html=True)
                h_links = blinks.hotel_links(ctx, city)
                cols = st.columns(len(h_links))
                for i, lnk in enumerate(h_links):
                    with cols[i]:
                        st.link_button(f"🏨 {lnk['label']}", lnk["url"], use_container_width=True)

            # Vehicle links
            if vehicle_opts:
                st.markdown('<p class="book-all-category">Step 4 — Vehicle (Optional)</p>', unsafe_allow_html=True)
                v_links = blinks.vehicle_links(ctx)
                cols = st.columns(len(v_links))
                for i, lnk in enumerate(v_links):
                    with cols[i]:
                        st.link_button(f"🚗 {lnk['label']}", lnk["url"], use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        _, back_col, _ = st.columns([1, 2, 1])
        with back_col:
            if st.button("← Back to Plan Details", use_container_width=True):
                st.session_state.booking_confirmed = False
                st.session_state.page = "results"
                st.rerun()


# ── Router ────────────────────────────────────────────────────────────────────
if st.session_state.page == "form":
    show_form()
elif st.session_state.page == "suggestions":
    show_suggestions()
elif st.session_state.page == "searching":
    show_searching()
elif st.session_state.page == "results":
    show_results()
elif st.session_state.page == "booking":
    show_booking()
