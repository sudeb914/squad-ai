"""DeepSeek provider (OpenAI-compatible chat completions).

Uses ``httpx`` if installed, otherwise falls back to stdlib ``urllib`` so the
app has no hard networking dependency. Requests are deliberately tiny: a static
system prompt first (to benefit from provider-side prompt caching), then only
the relevant profile/reference context and the current question/options. Output
is requested as compact JSON.
"""
from __future__ import annotations

import json
import re
import time
from typing import Optional

from .base_provider import AIRequest, BaseAIProvider, ProviderResponse
from ..utils.config import CONFIG
from ..utils.logging import get_logger, redact

log = get_logger("deepseek")

# Static system rules kept identical across calls => cache-friendly.
SYSTEM_RULES = (
    "You answer survey questions on behalf of a user. Rules:\n"
    "1. If the provided profile/reference data explicitly states an answer, use "
    "that exact fact. Do not override a stated fact with assumptions, "
    "stereotypes, statistics, or inferred preferences.\n"
    "2. Do not fabricate personal facts not present in the provided context.\n"
    "3. If options are given, you MUST pick exactly one of them verbatim "
    "(unless told multi-select) and return its zero-based index in "
    "option_index. NEVER invent an answer that is not in the list, and never "
    "output a word like 'best'/'good' unless it is one of the given options.\n"
    "4. Always give a definitive best answer on behalf of the user, using their "
    "profile, reference data and instructions. Prefer a concrete answer over "
    "saying 'not specified'; when unsure, choose the single most likely option "
    "that fits the user's profile. Be positive and decisive.\n"
    "5. Be extremely concise. Respond ONLY with compact JSON of the form "
    '{"answer": "...", "option_index": <int or null>, "confidence": <0..1>}. '
    "No explanation, no extra text."
)


class DeepSeekProvider(BaseAIProvider):
    name = "deepseek"

    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key
        self.model = CONFIG.provider.model
        self.base_url = CONFIG.provider.base_url.rstrip("/")

    # -- public -----------------------------------------------------------
    def answer(self, request: AIRequest) -> ProviderResponse:
        if not self.api_key:
            return ProviderResponse(
                answer="", selected_option_index=None, confidence=0.0,
                raw_text="", success=False,
                error="DeepSeek API key is not configured.")
        user = self._build_user_message(request)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_RULES},
                {"role": "user", "content": user},
            ],
            "temperature": CONFIG.provider.temperature,
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        start = time.time()
        try:
            data = self._post("/chat/completions", payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("DeepSeek request failed: %s", redact(str(exc)))
            return ProviderResponse(
                answer="", selected_option_index=None, confidence=0.0,
                raw_text="", success=False, error=str(exc),
                latency_ms=int((time.time() - start) * 1000))
        latency = int((time.time() - start) * 1000)
        return self._parse(data, latency)

    def test_connection(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "No API key configured."
        try:
            self._post("/chat/completions", {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            })
            return True, "Connection OK."
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def estimate_cost(self, input_tokens: int, output_tokens: int,
                      cached_tokens: int = 0) -> float:
        p = CONFIG.provider
        billed_input = max(0, input_tokens - cached_tokens)
        return round(
            billed_input / 1e6 * p.price_input_per_m
            + cached_tokens / 1e6 * p.price_input_cached_per_m
            + output_tokens / 1e6 * p.price_output_per_m, 6)

    # -- internals --------------------------------------------------------
    @staticmethod
    def _build_user_message(r: AIRequest) -> str:
        parts = []
        if r.instructions:
            parts.append(f"INSTRUCTIONS:\n{r.instructions}")
        if r.profile_context:
            parts.append(f"PROFILE:\n{r.profile_context}")
        if r.reference_context:
            parts.append(f"REFERENCE:\n{r.reference_context}")
        if r.recent_context:
            parts.append(f"RECENT:\n{r.recent_context}")
        parts.append(f"QUESTION:\n{r.question}")
        if r.options:
            opts = "\n".join(f"{i}. {o}" for i, o in enumerate(r.options))
            parts.append(f"OPTIONS:\n{opts}")
        return "\n\n".join(parts)

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = CONFIG.provider.request_timeout_s
        body = json.dumps(payload).encode("utf-8")
        try:
            import httpx  # type: ignore
        except ImportError:
            httpx = None  # type: ignore

        if httpx is not None:
            resp = httpx.post(url, headers=headers, content=body,
                              timeout=timeout)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"HTTP {resp.status_code}: {self._short(resp.text)}")
            return resp.json()

        # stdlib fallback — capture the error body for a useful message.
        import urllib.error
        import urllib.request

        req = urllib.request.Request(url, data=body, headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = self._short(exc.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}"
                               ) from exc

    @staticmethod
    def _short(text: str, limit: int = 200) -> str:
        text = (text or "").strip().replace("\n", " ")
        return text[:limit]

    def _parse(self, data: dict, latency_ms: int) -> ProviderResponse:
        usage = data.get("usage", {}) or {}
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        cached = int(
            (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            or usage.get("prompt_cache_hit_tokens", 0))
        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            content = ""
        answer, idx, conf = self._extract_answer(content)
        return ProviderResponse(
            answer=answer, selected_option_index=idx, confidence=conf,
            raw_text=content, input_tokens=input_tokens,
            output_tokens=output_tokens, cached_tokens=cached,
            latency_ms=latency_ms, success=bool(answer),
            error=None if answer else "Empty/invalid provider response")

    @staticmethod
    def _extract_answer(content: str):
        if not content:
            return "", None, 0.0
        text = _strip_code_fence(content)
        try:
            obj = json.loads(text)
            if not isinstance(obj, dict):
                raise ValueError("not an object")
            return (str(obj.get("answer", "")).strip(),
                    _coerce_index(obj.get("option_index")),
                    _clamp_conf(obj.get("confidence", 0.8)))
        except (json.JSONDecodeError, ValueError, TypeError):
            # Not JSON: use raw text as the answer with moderate confidence.
            return content.strip(), None, 0.7


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding ```json ... ``` fence if the model added one."""
    t = text.strip()
    if not t.startswith("```"):
        return t
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    return m.group(1).strip() if m else t.strip("`").strip()


def _coerce_index(value):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _clamp_conf(value) -> float:
    try:
        c = float(value)
    except (ValueError, TypeError):
        return 0.8
    return max(0.0, min(1.0, c))
