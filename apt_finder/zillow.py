import time, sys, requests
from typing import List, Dict, Union, Optional

from .config import get_settings
settings = get_settings()

MAX_ZILLOW_RESULTS = 100                # <<<  ADD / CONFIRM this line

ZILLOW_EP = "/propertyExtendedSearch"
ZILLOW_HOSTS = [
    "zillow-com1.p.rapidapi.com",
    "zillow-com.p.rapidapi.com",
    "zillow.p.rapidapi.com",
]

def _clean_zillow_url(detail_url: Optional[str]) -> Optional[str]:
    """
    • Prefix with https://www.zillow.com if it's just a path.
    • Return None if the link isn’t a Zillow URL (used for filtering).
    """
    if not detail_url:
        return None
    if detail_url.startswith("/"):
        detail_url = "https://www.zillow.com" + detail_url
    if "zillow.com" not in detail_url:         # <— Zillow-only guard
        return None
    return detail_url


def _headers(host: str) -> Dict[str, str]:
    return {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": host,
    }


def _params(coords: str, page: int, rent_min: int, rent_max: int) -> Dict[str, Union[str, int]]:
    return {
        "coordinates": coords,          # "lon lat,diameter"
        "status_type": "ForRent",
        "rentMin": rent_min,
        "rentMax": rent_max,
        "page": page,
    }


def pull(coords: str, rent_min: int, rent_max: int) -> List[Dict]:
    """
    Return a list of Zillow listings, capped at 100 rows for performance.
    """
    for host in ZILLOW_HOSTS:
        page, out = 1, []
        try:
            while True:
                r = requests.get(
                    f"https://{host}{ZILLOW_EP}",
                    headers=_headers(host),
                    params=_params(coords, page, rent_min, rent_max),
                    timeout=20,
                )
                r.raise_for_status()
                batch = r.json().get("props", [])
                if not batch:
                    break
                out += batch
                if len(out) >= MAX_ZILLOW_RESULTS:          # ← stop early
                    out = out[:MAX_ZILLOW_RESULTS]
                    break
                page += 1
            return out
        except requests.HTTPError:
            continue
    return []
