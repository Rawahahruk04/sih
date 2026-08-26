"""Runtime configuration. Secrets come from the environment, never from code."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIPI_", env_file=".env", extra="ignore", case_sensitive=False
    )

    database_url: str = "postgresql+psycopg://aipi:aipi@localhost:5432/aipi"

    amadeus_client_id: str = ""
    amadeus_client_secret: str = ""
    amadeus_env: str = "test"

    # Duffel. A `duffel_test_` token is TEST mode: real API, simulated inventory.
    # `live_mode` on the response is the only trustworthy indicator — never infer
    # it from the token prefix alone.
    duffel_token: str = ""
    duffel_version: str = "v2"
    duffel_base_url: str = "https://api.duffel.com"
    duffel_timeout_s: float = 60.0
    #: Fares must be quoted in the index currency. Converting a foreign-currency
    #: quote would inject exchange-rate movement into what has to be a pure price
    #: movement, so a mismatch is a hard error rather than a conversion.
    index_currency: str = "INR"

    capture_slot_ist: str = "06:30"
    capture_tolerance_min: int = 45

    # --- index parameters (versioned: changing these needs a new weight_version)
    base_period_days: int = Field(
        14, description="Base is the GEOMETRIC MEAN of the first N days, never a single day."
    )
    geks_window_days: int = Field(25, description="Rolling GEKS window length.")
    min_matched_items: int = Field(2, description="Minimum matched items for a valid bilateral.")
    min_n_for_trim: int = Field(8, description="Below this cell size, outlier trimming is skipped.")
    mad_trim_k: float = Field(3.5, description="log-MAD trimming threshold.")

    @property
    def amadeus_base_url(self) -> str:
        return (
            "https://api.amadeus.com"
            if self.amadeus_env == "production"
            else "https://test.api.amadeus.com"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
