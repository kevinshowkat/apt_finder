import json
from typing import List, Dict

from openai import OpenAI
from .config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)


def rank_listings(listings: List[Dict]) -> List[Dict]:
    """
    Ask OpenAI o3 to rank listings, highest first.
    """
    system_msg = (
        "You are a meticulous real‑estate analyst. "
        "Stack‑rank the supplied rental listings from best to worst. "
        "Weight highest‑to‑lowest:\n"
        "1. Larger radius_bonus (9 %, 7 %, 5 %).\n"
        "2. Greater bars_cnt.\n\n"
        "Return JSON only.  Each element must contain "
        "address, listing, radius_bonus, bars_cnt, nearest_bar, "
        "nearest_bar_dist_mi, and rank."
    )
    user_msg = json.dumps(listings, ensure_ascii=False)

    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    )
    ranked = json.loads(resp.choices[0].message.content)

    # Merge back remaining fields (price, distance, etc.)
    by_addr = {l["address"]: l for l in listings}
    return [{**by_addr.get(r["address"], {}), **r} for r in ranked]
