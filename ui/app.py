# ── import path shim: lets Streamlit Cloud find the sibling package ────────────
import sys, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
# ───────────────────────────────────────────────────────────────────────────────

import streamlit as st                    # ← make sure this line is present
import pandas as pd
from typing import List, Optional

from apt_finder.config import get_settings
from apt_finder.zillow import MAX_ZILLOW_RESULTS
from apt_finder.zillow import pull as pull_zillow
from apt_finder.enrich import enrich_props
from apt_finder.ranking import rank_listings

cfg = get_settings()
st.set_page_config(page_title="Apartment Finder", layout="wide", page_icon="🏠")

# -------- password gate --------
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state.auth:
    pw = st.text_input("🔒 Enter password", type="password")
    if pw and pw == cfg.app_password:
        st.session_state.auth = True
        (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()
    elif pw:
        st.error("Wrong password")
    st.stop()

# -------- sidebar controls --------
st.sidebar.header("Search settings")
radius = st.sidebar.slider("Radius (miles)", 0.0, 3.0, cfg.radius_mi, 0.25)
rent_min, rent_max = st.sidebar.slider(
    "Budget ($/month)", 500, 8000, (cfg.min_rent, cfg.max_rent), 100
)

# NEW: multiselect for Places types
place_options = [
    "bar",
    "restaurant",
    "cafe",
    "bakery",
    "gym",
    "park",
    "night_club",
    "movie_theater",
]
sel_types: List[str] = st.sidebar.multiselect(
    "Places you care living close to",
    place_options,
    default=cfg.default_place_types,
    help="Pick one or more Google Places categories",
)

run_btn = st.sidebar.button("🔍  Search now")

st.title("🏠 Apartment Finder near 345 N Maple 👀")
st.markdown(
    f"Showing rentals within **{radius} mi** of the office "
    f"({cfg.office_lat:.4f}, {cfg.office_lon:.4f})."
)

# ---------- run search ----------
if run_btn:
    cfg = get_settings()                # reuse cached settings

    # nice vertical card with live updates
    with st.status("Starting search…", expanded=True) as status:
        # 1 · Zillow pull
        status.update(label="Pulling Zillow listings…")
        coords = f"{cfg.office_lon} {cfg.office_lat},{radius * 2}"
        raw = pull_zillow(coords, rent_min, rent_max)
        status.write(f"• Pulled **{len(raw)} / {MAX_ZILLOW_RESULTS}** Zillow listings")

        # 2 · Enrich + filter
        status.update(label="Enriching with Google Places + filters…")
        enriched = enrich_props(
            raw,
            (cfg.office_lat, cfg.office_lon),
            radius,
            rent_min,
            rent_max,
            sel_types,
        )
        status.write(
            f"• After radius / price + POI enrichment → **{len(enriched)}** candidates"
        )

        if not enriched:
            status.update(state="error", label="No listings after enrichment.")
            st.warning("No listings matched your criteria.")
            st.stop()

        # 3 · Ranking
        status.update(label="Ranking with OpenAI o3…")
        df = pd.DataFrame(rank_listings(enriched)).sort_values("rank")
        status.write("• Ranking complete")
        status.update(state="complete", label="Done! 🎉")

    # ---------- UI render ----------
    # (map, table, CSV)  — unchanged from before
    map_df = df[["latitude", "longitude"]].dropna()
    st.subheader("Map view")
    if map_df.empty:
        st.info("No listings have valid coordinates to plot on a map.")
    else:
        st.map(map_df)

    st.subheader("Results")
    show_cols = [
        "rank",
        "address",
        "price",
        "distance",
        "radius_bonus",
        "places_cnt",
        "nearest_poi",
        "nearest_poi_dist_mi",
        "listing",
    ]
    st.dataframe(
        df[show_cols].set_index("rank"),
        use_container_width=True,
        column_config={
            "listing": st.column_config.LinkColumn(
                label="Listing",
                display_text="open",   # text shown to users
            )
        },
    )

    csv = df.to_csv(index=False).encode()
    st.download_button(
        "📥 Download CSV", data=csv, file_name="apartments.csv", mime="text/csv"
    )
else:
    st.info("Adjust settings and press **Search now** ⬆️")

