from pathlib import Path
from typing import List, Optional
from datetime import timedelta
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscoveryLimits(BaseModel):
    max_candidates_per_hashtag: int = 100
    max_accounts_per_anchor: int = 200


class ScoringThresholds(BaseModel):
    match_overall: float = 0.75
    maybe_overall: float = 0.50


class AppConfig(BaseSettings):
    # Seed Data
    seed_hashtags: List[str] = ["dctech", "dmvtech", "washingtondc"]
    anchor_handles: List[str] = ["capitalweather.bsky.social"]

    # Limits
    discovery_limits: DiscoveryLimits = DiscoveryLimits()
    fetch_posts_limit: int = 50

    # TTLs (hours)
    ttl_profile_hours: int = 24
    ttl_posts_hours: int = 6
    ttl_llm_hours: int = 168  # 1 week

    # Storage
    db_path: Path = Path("dctech.db")

    # LLM (OpenRouter / OpenAI-compatible)
    openrouter_api_key: str = Field(..., validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        "https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
    )
    openrouter_model: str = Field(
        "google/gemini-3-flash-preview",
        validation_alias="OPENROUTER_MODEL",
    )

    # LLM
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4-turbo-preview"

    # Scoring
    scoring_thresholds: ScoringThresholds = ScoringThresholds()

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    @property
    def min_interval_profile_refresh(self) -> timedelta:
        return timedelta(hours=self.ttl_profile_hours)

    @property
    def min_interval_posts_refresh(self) -> timedelta:
        return timedelta(hours=self.ttl_posts_hours)

    @property
    def min_interval_llm_refresh(self) -> timedelta:
        return timedelta(hours=self.ttl_llm_hours)


settings = AppConfig()
