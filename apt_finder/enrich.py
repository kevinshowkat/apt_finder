import requests, re
from typing import Dict, List, Tuple, Union, Optional
from geopy.distance import geodesic

from .config import get_settings
from .zillow import _clean_zillow_url      # ← ADD THIS

settings = get_settings()
BAR_RADIUS_M = settings.google_places_radius_m

UNIT_RE = re.compile(
    r"^(?P<street>.+?)\s*[#, ]\s*(?:apt|unit|suite|ste|#)\s*"
    r"(?P<unit>[A-Za-z0-9\-]+)\s*(?P<rest>,.*)$",
    re.I,
)


def _price_ok(v, lo: int, hi: int) -> bool:
    try:
        p = int(str(v).split()[0].replace("$", "").replace(",", ""))
    except Exception:
        return False
    return lo <= p <= hi


def _radius_bonus(distance: float) -> int:
    if distance <= 0.5:
        return 9
    if distance <= 1.5:
        return 7
    if distance <= 2.0:
        return 5
    return 0


def nearby_pois(lat: float, lon: float, place_types: list[str]) -> Dict[str, Union[int, str, float]]:
    """
    One call to Google Places NearbySearch using multiple `types=` filters joined by '|'.
    Returns dict with places_cnt, nearest_poi, nearest_poi_dist_mi.
    """
    type_param = "|".join(place_types)
    params = {
        "key": settings.places_api_key,
        "location": f"{lat},{lon}",
        "radius": BAR_RADIUS_M,
        "type": type_param,
    }
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            raise RuntimeError(data.get("status"))
        results = data.get("results", [])
    except Exception as e:
        print(f"[WARN] Places API error @({lat:.4f},{lon:.4f}): {e}")
        return {"places_cnt": None, "nearest_poi": None, "nearest_poi_dist_mi": None}

    cnt = len(results)
    if not results:
        return {"places_cnt": 0, "nearest_poi": None, "nearest_poi_dist_mi": None}

    first = results[0]
    name = first.get("name")
    ploc = first.get("geometry", {}).get("location", {})
    dist = geodesic((lat, lon), (ploc.get("lat"), ploc.get("lng"))).miles

    return {
        "places_cnt": cnt,
        "nearest_poi": name,
        "nearest_poi_dist_mi": round(dist, 2),
    }


def enrich_props(
    props: List[Dict],
    centre: Tuple[float, float],
    radius_mi: float,
    min_rent: int,
    max_rent: int,
    place_types: list[str],
) -> List[Dict]:
    good = []
    for p in props:
        lat, lon = p.get("latitude"), p.get("longitude")
        if not lat or not lon:
            continue
        dist = round(geodesic((lat, lon), centre).miles, 3)
        if dist > radius_mi:
            continue
        if not _price_ok(p.get("price"), min_rent, max_rent):
            continue

        poi_info = nearby_pois(lat, lon, place_types)

        listing_url = _clean_zillow_url(p.get("detailUrl"))
        if listing_url is None:        # skip non-Zillow listings
            continue

        enriched = {
            "address": p.get("address"),
            "price": p.get("price"),
            "latitude": lat,
            "longitude": lon,
            "distance": dist,
            "radius_bonus": _radius_bonus(dist),
            "listing": listing_url,
            **poi_info,
        }
        good.append(enriched)
    return good
