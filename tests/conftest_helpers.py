"""Shared test helpers: temp-dir Services and a call-counting fake provider."""
from __future__ import annotations

import os
import tempfile

# Ensure all app data goes to an isolated temp dir BEFORE importing app modules.
_TMP = tempfile.mkdtemp(prefix="squadai_test_")
os.environ["SQUAD_AI_HOME"] = _TMP

from app.services import Services  # noqa: E402
from app.providers.base_provider import (  # noqa: E402
    AIRequest, BaseAIProvider, ProviderResponse)


class FakeProvider(BaseAIProvider):
    name = "deepseek"
    model = "fake-model"

    def __init__(self, answer="Fake Answer", option_index=None, confidence=0.9):
        self.calls = 0
        self._answer = answer
        self._idx = option_index
        self._conf = confidence

    def answer(self, request: AIRequest) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(
            answer=self._answer, selected_option_index=self._idx,
            confidence=self._conf, raw_text="{}", input_tokens=120,
            output_tokens=15, cached_tokens=0, latency_ms=42, success=True)

    def test_connection(self):
        return True, "ok"

    def estimate_cost(self, i, o, c=0):
        return 0.0001


def make_services(profile: dict | None = None):
    """Fresh Services on a unique temp DB, with the AI provider faked."""
    db_path = tempfile.mktemp(prefix="squadai_", suffix=".sqlite3", dir=_TMP)
    # No default seeding in tests — keep the profile/reference deterministic.
    svc = Services(db_path=db_path, seed_defaults=False)
    fake = FakeProvider()
    svc.engine.provider_factory = lambda: fake
    svc._fake = fake  # type: ignore[attr-defined]
    if profile:
        for k, v in profile.items():
            svc.profile.upsert(k, str(v))
    return svc, fake
