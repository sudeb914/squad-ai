"""Shared implementation for OpenAI-compatible chat providers.

Both DeepSeek and AgentRouter speak the OpenAI ``/chat/completions`` protocol,
so all the real work lives here once and each provider is a thin subclass that
supplies its own config object (base URL, model, temperature, pricing, token
caps). This keeps a single answer-processing path — the answer engine only ever
talks to :class:`~app.providers.base_provider.BaseAIProvider`.

Requests are deliberately tiny: a static system prompt first (prompt-cache
friendly), then only the relevant profile/reference context and the current
question/options. Exactly one network call is made per answer — there is no
retry/verification loop here.
"""
from __future__ import annotations

import json
import re
import time
from typing import Optional

from .base_provider import AIRequest, BaseAIProvider, ProviderResponse
from ..utils.logging import get_logger, redact

log = get_logger("provider")

# Static system rules kept identical across calls => provider-side cache-friendly
# and extremely compact (survey answer only, no explanations).
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


class OpenAICompatibleProvider(BaseAIProvider):
    """Base for any provider exposing an OpenAI-compatible chat endpoint.

    ``cfg`` is a config dataclass (see ``utils.config``) providing ``model``,
    ``base_url``, ``temperature``, ``request_timeout_s``, the pricing fields and
    the token caps. Subclasses just pass the right cfg + a ``name``.
    """

    def __init__(self, api_key: Optional[str], cfg, name: str) -> None:
        self.api_key = api_key
        self.cfg = cfg
        self.name = name
        self.model = cfg.model
        self.base_url = cfg.base_url.rstrip("/")
        # exposed so the answer engine can size the output cap per active provider
        self.max_output_tokens = cfg.max_output_tokens
        self.max_output_tokens_simple = cfg.max_output_tokens_simple

    # -- public -----------------------------------------------------------
    def answer(self, request: AIRequest) -> ProviderResponse:
        if not self.api_key:
            return ProviderResponse(
                answer="", selected_option_index=None, confidence=0.0,
                raw_text="", success=False,
                error=f"{self.name} API key is not configured.")
        user = self._build_user_message(request)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_RULES},
                {"role": "user", "content": user},
            ],
            "temperature": self.cfg.temperature,
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        start = time.time()
        try:
            data = self._post("/chat/completions", payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s request failed: %s", self.name, redact(str(exc)))
            return ProviderResponse(
                answer="", selected_option_index=None, confidence=0.0,
                raw_text="", success=False, error=str(exc),
                latency_ms=int((time.time() - start) * 1000))
        latency = int((time.time() - start) * 1000)
        return self._parse(data, latency)

    def test_connection(self) -> tuple[bool, str]:
        """Smallest practical request (1 token) with friendly error mapping."""
        if not self.api_key:
            return False, "No API key configured."
        try:
            self._post("/chat/completions", {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            })
            return True, f"Connected. Model: {self.model}"
        except Exception as exc:  # noqa: BLE001
            return False, self._friendly_error(str(exc))

    def estimate_cost(self, input_tokens: int, output_tokens: int,
                      cached_tokens: int = 0) -> float:
        c = self.cfg
        billed_input = max(0, input_tokens - cached_tokens)
        return round(
            billed_input / 1e6 * c.price_input_per_m
            + cached_tokens / 1e6 * c.price_input_cached_per_m
            + output_tokens / 1e6 * c.price_output_per_m, 6)

    # -- internals --------------------------------------------------------
    @staticmethod
    def _friendly_error(msg: str) -> str:
        """Map raw transport errors to a clear, key-safe message."""
        low = msg.lower()
        if "http 401" in low or "unauthorized" in low or "invalid key" in low \
                or "authentication" in low:
            return "Authentication failed — check the API key."
        if "http 402" in low or "insufficient" in low or "balance" in low \
                or "quota" in low:
            return "Insufficient balance/quota on the account."
        if "http 404" in low or "model" in low and "not" in low:
            return "Model not found — check the model name and Base URL."
        if "http 429" in low or "rate limit" in low:
            return "Rate limit reached — try again shortly."
        if "http 5" in low or "server error" in low:
            return "Provider server error — try again later."
        if any(k in low for k in ("name or service", "getaddrinfo", "dns",
                                  "failed to resolve", "connection", "timed out",
                                  "timeout", "network")):
            return "Network error — check the Base URL and your connection."
        # Never surface anything that could contain a key; keep it short.
        return f"Connection failed: {msg[:160]}"

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
        # Some routers (e.g. AgentRouter) gate access by client User-Agent and
        # reject a generic one with "unauthorized client" before checking the
        # key. Send the configured client id when the provider defines one.
        ua = getattr(self.cfg, "user_agent", "")
        if ua:
            headers["User-Agent"] = ua
        timeout = self.cfg.request_timeout_s
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
        content = ""
        try:
            msg = data["choices"][0]["message"]
            # Some models leave `content` empty and put the text in
            # `reasoning_content`; some return content as a list of parts.
            raw = msg.get("content") or msg.get("reasoning_content") or ""
            if isinstance(raw, list):
                raw = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in raw)
            content = (raw or "").strip()
        except (KeyError, IndexError, AttributeError, TypeError):
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
