"""Frozen runtime configuration loaded once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Settings:
    catalog_provider: Literal["stub", "remote"]
    catalog_base_url: str
    cart_provider: Literal["stub", "supabase"]
    supabase_url: str
    supabase_key: str
    llm_base_url: str
    llm_key: str
    llm_model: str
    cart_memory: str
    image_proxy_base: str


def load_settings() -> Settings:
    """Build an immutable settings object without service-level fallback state."""
    cart_provider = os.getenv("SYMY_CART_PROVIDER", "stub")
    supabase_url = os.getenv("SYMY_SUPABASE_URL", "")
    supabase_key = os.getenv("SYMY_SUPABASE_KEY", "")
    if cart_provider == "supabase" and (not supabase_url or not supabase_key):
        raise ValueError("SYMY_CART_PROVIDER=supabase requires SYMY_SUPABASE_URL and SYMY_SUPABASE_KEY")
    return Settings(
        catalog_provider=os.getenv("SYMY_CATALOG_PROVIDER", "stub"),  # type: ignore[arg-type]
        catalog_base_url=os.getenv("SYMY_CATALOG_BASE_URL", ""),
        cart_provider=cart_provider,  # type: ignore[arg-type]
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        llm_base_url=os.getenv("SYMY_LLM_BASE_URL", ""),
        llm_key=os.getenv("SYMY_LLM_KEY", ""),
        llm_model=os.getenv("SYMY_LLM_MODEL", ""),
        cart_memory=os.getenv("SYMY_CART_MEMORY", "/tmp/cart.json"),
        image_proxy_base=os.getenv("SYMY_IMAGE_PROXY_BASE", ""),
    )
