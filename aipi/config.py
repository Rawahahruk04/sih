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
