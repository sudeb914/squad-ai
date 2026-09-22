"""Live DeepSeek verification (requires a real API key + internet).

Run this on your own machine to confirm the end-to-end AI fallback path against
the real API. It uses the key stored via the app's secure credential manager
(``python -m app.cli key set sk-...``), or one passed on the command line.

    python -m scripts.verify_deepseek                # uses stored key
    python -m scripts.verify_deepseek sk-your-key    # uses given key

It performs exactly TWO calls (a 1-token connection ping + one real answer) so
it costs a fraction of a cent, and prints tokens / cost / latency.
"""
from __future__ import annotations

import sys

from app.providers.base_provider import AIRequest
from app.providers.deepseek_provider import SYSTEM_RULES, DeepSeekProvider
from app.security.credential_manager import CredentialManager
from app.utils.config import CONFIG


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    key = argv[0] if argv else CredentialManager().get_key(CONFIG.provider.name)
    if not key:
        print("❌ No API key. Pass one, or run: python -m app.cli key set sk-...")
        return 1

    prov = DeepSeekProvider(api_key=key)

    print("1) Testing connection…")
    ok, msg = prov.test_connection()
    print(f"   {'✅' if ok else '❌'} {msg}")
    if not ok:
        return 2

    print("2) Answering a sample survey question…")
    req = AIRequest(
        system=SYSTEM_RULES,
        question="Which best describes your current employment?",
        options=["Working full time", "Working part time", "Not employed",
                 "Retired"],
        profile_context="- employment_status: Full-time employed",
        max_output_tokens=CONFIG.provider.max_output_tokens_simple)
    r = prov.answer(req)
    if not r.success:
        print(f"   ❌ {r.error}")
        return 3

    cost = prov.estimate_cost(r.input_tokens, r.output_tokens, r.cached_tokens)
    print(f"   ✅ answer = {r.answer!r}  (option_index={r.selected_option_index})")
    print(f"      tokens: in={r.input_tokens} out={r.output_tokens} "
          f"cached={r.cached_tokens}")
    print(f"      est. cost = ${cost:.6f}   latency = {r.latency_ms} ms")
    print("\n✅ Live DeepSeek path verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
