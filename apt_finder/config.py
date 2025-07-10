from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field, PositiveInt, confloat

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


class Settings(BaseSettings):
    # Office location & defaults
    office_lat: confloat(ge=-90, le=90) = 34.0683
    office_lon: confloat(ge=-180, le=180) = -118.4023
    radius_mi: confloat(gt=0) = 2.0

    # Default rent range
    min_rent: PositiveInt = 2100
    max_rent: PositiveInt = 3000

    # API keys / secrets
    rapidapi_key: str
    openai_api_key: str
    places_api_key: str
    app_password: str

    # POI defaults
    default_place_types: list[str] = ["bakery"]       # <— NEW
    google_places_radius_m: PositiveInt = 800

    openai_model: str = "o3"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
