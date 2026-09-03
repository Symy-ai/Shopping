import pytest

from app.config import load_settings


def test_supabase_provider_requires_url_and_key(monkeypatch):
    monkeypatch.setenv("SYMY_CART_PROVIDER", "supabase")
    monkeypatch.delenv("SYMY_SUPABASE_URL", raising=False)
    monkeypatch.delenv("SYMY_SUPABASE_KEY", raising=False)
    with pytest.raises(ValueError, match="SYMY_SUPABASE_URL and SYMY_SUPABASE_KEY"):
        load_settings()
