# apt_finder/ranking.py
import json
import time
from typing import List, Dict

from openai import OpenAI, OpenAIError, RateLimitError

from .config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)

MAX_LISTINGS = 20           # send at most 20 rows to OpenAI


def _openai_rank(payload: str) -> List[Dict]:
    """Low-level call wrapped so we can retry cleanly."""
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
                    "places_cnt, nearest_poi, nearest_poi_dist_mi, and rank."
                ),
            },
            {"role": "user", "content": payload},
        ],
        timeout=30,
    ).choices[0].message.content


def rank_listings(listings: List[Dict]) -> List[Dict]:
    """
    Return the LLM-ranked listings, merging back original fields.
    Falls back gracefully on OpenAI rate limits.
    """
    # 1 · trim to the first N rows to stay under token limits
    trimmed = listings[:MAX_LISTINGS]
    payload = json.dumps(trimmed, ensure_ascii=False)

    try:
        ranked_json = _openai_rank(payload)

    except RateLimitError:
        time.sleep(2)                 # simple back-off
        ranked_json = _openai_rank(payload)

    except OpenAIError as e:
        raise RuntimeError(f"OpenAI API failed: {e}") from e

    ranked = json.loads(ranked_json)

    # 2 · merge ranked fields back onto the original listing dicts
    by_addr = {l["address"]: l for l in trimmed}
    return [{**by_addr.get(r["address"], {}), **r} for r in ranked]
