"""Runtime settings read from the environment and an optional .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    sec_user_agent: str = os.getenv(
        "SEC_USER_AGENT",
        "InvestmentOS research contact@example.com",
    )
    fred_api_key: str = os.getenv("FRED_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-5-5"
    # Thinking counts toward this limit. 16000 is the practical non-streaming ceiling.
    anthropic_max_tokens: int = int(os.getenv("ANTHROPIC_MAX_TOKENS") or 16000)
    # Empty uses the model's default. Not every model accepts an effort setting.
    anthropic_effort: str = os.getenv("ANTHROPIC_EFFORT", "")


settings = Settings()
