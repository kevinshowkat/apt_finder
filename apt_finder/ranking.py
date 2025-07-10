"""
apt_finder.ranking
------------------
LLM-based stack-ranking with graceful degradation.

• Sends at most MAX_LISTINGS rows to OpenAI.
• Retries on *any* OpenAIError up to MAX_RETRIES with exponential back-off.
• If the response isn't valid JSON or the API keeps failing, falls back to a
  deterministic local sort so the UI never crashes.
"""

from __future__ import annotations

import json
import time
from typing import Dict, List

from openai import OpenAI, OpenAIError, RateLimitError

from .config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)

MAX_LISTINGS = 20
MAX_RETRIES = 3
BACKOFF_S = 1


def _call_openai(payload: str) -> str:
    """Single API call—returns raw JSON string (or junk)."""
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
                    "Return *JSON only* with address, listing, radius_bonus, "
                    "places_cnt, nearest_poi, nearest_poi_dist_mi, rank."
                ),
            },
            {"role": "user", "content": payload},
        ],
        timeout=30,
    ).choices[0].message.content


def _fallback_sort(rows: List[Dict]) -> List[Dict]:
    ranked = sorted(
        rows, key=lambda x: (-x.get("radius_bonus", 0), -x.get("places_cnt", 0))
    )
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return ranked


def rank_listings(listings: List[Dict]) -> List[Dict]:
    trimmed = listings[:MAX_LISTINGS]
    payload = json.dumps(trimmed, ensure_ascii=False)

    backoff = BACKOFF_S
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw_json = _call_openai(payload)
            ranked = json.loads(raw_json)            # ← may raise JSONDecodeError
            break  # success
        except json.JSONDecodeError:
            print(f"[WARN] OpenAI responded with invalid JSON on attempt {attempt}")
            # don't retry—go straight to fallback
            ranked = _fallback_sort(trimmed)
            break
        except (OpenAIError, RateLimitError) as e:
            if attempt == MAX_RETRIES:
                print(f"[WARN] OpenAI failed after {attempt} tries: {e}")
                ranked = _fallback_sort(trimmed)
                break
            time.sleep(backoff)
            backoff *= 2

    by_addr = {l["address"]: l for l in trimmed}
    return [{**by_addr.get(r["address"], {}), **r} for r in ranked]
