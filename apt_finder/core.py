import pandas as pd
from typing import Optional, List

from .config import get_settings
from .zillow import pull as pull_zillow
from .enrich import enrich_props
from .ranking import rank_listings


def search_and_rank(
    radius_mi: Optional[float] = None,
    min_rent: Optional[int] = None,
    max_rent: Optional[int] = None,
    place_types: Optional[List[str]] = None,
) -> pd.DataFrame:
    cfg = get_settings()
    radius_mi = radius_mi or cfg.radius_mi
    min_rent = min_rent or cfg.min_rent
    max_rent = max_rent or cfg.max_rent
    place_types = place_types or cfg.default_place_types

    coords = f"{cfg.office_lon} {cfg.office_lat},{radius_mi * 2}"
    raw = pull_zillow(coords, min_rent, max_rent)

    enriched = enrich_props(
        raw,
        (cfg.office_lat, cfg.office_lon),
        radius_mi,
        min_rent,
        max_rent,
        place_types,
    )
    if not enriched:
        return pd.DataFrame()

    rank_input = enriched[:20]
    ranked = rank_listings(rank_input)
    return pd.DataFrame(ranked).sort_values("rank")
