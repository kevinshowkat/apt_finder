"""
apt_finder.ranking
------------------
LLM-based stack-ranking with automatic fallback:

• Sends at most MAX_LISTINGS listings to OpenAI to stay under token limits.
• Retries up to MAX_RETRIES on any OpenAI error (rate-limit, transient, etc.)
  with exponential back-off (1 s · 2ⁿ).
• If the API still fails, falls back to a deterministic local sort so
  the UI never crashes.
"""

from __future__ import annotations

import json
import time
from typing import Dict, List

from openai import OpenAI, OpenAIError, RateLimitError

from .config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)

MAX_LISTINGS = 20          # protect token quota
MAX_RETRIES = 3            # OpenAI attempts (1 original + 2 retries)
BACKOFF_S = 1              # initial sleep on error


def _call_openai(payload: str) -> str:
    """Single API invocation. Returns raw JSON string from the model."""
    return client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a meticulous real-estate analyst. "
                    "Stack-rank the supplied rental listings from best to worst. "
                    "Weight highest-to-lowest:\n"
                    "1. Larger radius_bonus (9 %, 7 %, 5 %).\n"
                    "2. Greater places_cnt.\n\n"
                    "Return JSON only with address, listing, radius_bonus, "
                    "places_cnt, nearest_poi, nearest_poi_dist_mi, rank."
                ),
            },
            {"role": "user", "content": payload},
        ],
        timeout=30,
    ).choices[0].message.content


def _fallback_sort(listings: List[Dict]) -> List[Dict]:
    """Deterministic rank when OpenAI is unavailable."""
    ranked = sorted(
        listings,
        key=lambda x: (-x.get("radius_bonus", 0), -x.get("places_cnt", 0)),
    )
    for idx, row in enumerate(ranked, 1):
        row["rank"] = idx
    return ranked


def rank_listings(listings: List[Dict]) -> List[Dict]:
    """
    Public helper used by ui/app.py.
    Always returns a ranked list—never raises OpenAI errors.
    """
    short_list = listings[:MAX_LISTINGS]
    payload = json.dumps(short_list, ensure_ascii=False)

    backoff = BACKOFF_S
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ranked_json = _call_openai(payload)
            ranked = json.loads(ranked_json)
            break  # ✅ success; exit retry-loop
        except (RateLimitError, OpenAIError) as e:
            if attempt == MAX_RETRIES:
                # Log and degrade gracefully
                print(f"[WARN] OpenAI error after {attempt} attempts → {e}")
                ranked = _fallback_sort(short_list)
                break
            time.sleep(backoff)
            backoff *= 2  # exponential back-off

    # merge OpenAI results with original fields (price, distance, etc.)
    by_addr = {l["address"]: l for l in short_list}
    return [{**by_addr.get(r["address"], {}), **r} for r in ranked]
