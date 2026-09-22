"""Verify the DeepSeek request/response path without a live network.

We monkeypatch ``urllib.request.urlopen`` (the stdlib fallback the provider uses
when httpx is absent) so the REAL ``_post``/``_parse``/``_extract_answer`` code
runs against canned DeepSeek-shaped responses. This proves the wire contract:
request headers/payload, usage-token capture (incl. cached tokens), cost math,
JSON extraction, fenced-JSON, plain-text fallback, and HTTP-error handling.
"""
import io
import json
import unittest
import urllib.error
import urllib.request

from tests.conftest_helpers import _TMP  # noqa: F401  (sets SQUAD_AI_HOME)
from app.providers.base_provider import AIRequest
from app.providers.deepseek_provider import DeepSeekProvider, SYSTEM_RULES


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


def _canned(content: str, *, prompt=120, completion=15, cached=0) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "prompt_cache_hit_tokens": cached,
        },
    }


class _FakeHttpxResp:
    def __init__(self, obj, status=200):
        self._obj = obj
        self.status_code = status
        self.text = json.dumps(obj)

    def json(self):
        return self._obj


class _Patched:
    """Capture the outgoing request and return a canned body.

    Intercepts BOTH transports the provider may use — httpx (when installed) and
    the stdlib urllib fallback — so the test is independent of which is present.
    ``status`` >= 400 exercises the HTTP-error path.
    """

    def __init__(self, response_obj=None, status=200):
        self.response_obj = response_obj
        self.status = status
        self.captured = {}
        self._orig_urlopen = None
        self._httpx = None
        self._orig_httpx_post = None

    def __enter__(self):
        # stdlib fallback
        self._orig_urlopen = urllib.request.urlopen

        def fake_urlopen(req, timeout=None):
            self.captured["url"] = req.full_url
            self.captured["headers"] = dict(req.header_items())
            self.captured["body"] = json.loads(req.data.decode("utf-8"))
            body = json.dumps(self.response_obj).encode("utf-8")
            if self.status >= 400:
                raise urllib.error.HTTPError(
                    req.full_url, self.status, "Error", None, io.BytesIO(body))
            return _FakeResp(body)

        urllib.request.urlopen = fake_urlopen

        # httpx (preferred path when installed)
        try:
            import httpx  # type: ignore

            self._httpx = httpx
            self._orig_httpx_post = httpx.post

            def fake_post(url, headers=None, content=None, timeout=None):
                self.captured["url"] = url
                self.captured["headers"] = dict(headers or {})
                self.captured["body"] = json.loads(content.decode("utf-8"))
                return _FakeHttpxResp(self.response_obj, self.status)

            httpx.post = fake_post
        except ImportError:
            pass
        return self

    def __exit__(self, *a):
        urllib.request.urlopen = self._orig_urlopen
        if self._httpx is not None:
            self._httpx.post = self._orig_httpx_post
        return False


REQ = AIRequest(system=SYSTEM_RULES, question="Which best describes you?",
                options=["Full time", "Part time", "Retired"],
                profile_context="- employment: full time",
                max_output_tokens=120)


class TestRequestShape(unittest.TestCase):
    def test_payload_and_headers(self):
        prov = DeepSeekProvider(api_key="sk-test-key")
        with _Patched(_canned('{"answer":"Full time","option_index":0,'
                              '"confidence":0.94}')) as p:
            prov.answer(REQ)
        # Auth header carries the key; system prompt is FIRST (cache-friendly).
        self.assertEqual(p.captured["headers"].get("Authorization"),
                         "Bearer sk-test-key")
        body = p.captured["body"]
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(body["messages"][0]["content"], SYSTEM_RULES)
        self.assertEqual(body["temperature"], 0.1)
        self.assertEqual(body["max_tokens"], 120)
        # Options are numbered in the user message.
        self.assertIn("0. Full time", body["messages"][1]["content"])


class TestResponseParsing(unittest.TestCase):
    def setUp(self):
        self.prov = DeepSeekProvider(api_key="sk-test-key")

    def test_plain_json(self):
        with _Patched(_canned('{"answer":"Full time","option_index":0,'
                              '"confidence":0.94}', cached=64)):
            r = self.prov.answer(REQ)
        self.assertTrue(r.success)
        self.assertEqual(r.answer, "Full time")
        self.assertEqual(r.selected_option_index, 0)
        self.assertAlmostEqual(r.confidence, 0.94)
        self.assertEqual(r.input_tokens, 120)
        self.assertEqual(r.output_tokens, 15)
        self.assertEqual(r.cached_tokens, 64)

    def test_fenced_json(self):
        with _Patched(_canned('```json\n{"answer":"Retired",'
                              '"option_index":2,"confidence":0.8}\n```')):
            r = self.prov.answer(REQ)
        self.assertEqual(r.answer, "Retired")
        self.assertEqual(r.selected_option_index, 2)

    def test_string_index_and_bad_confidence_coerced(self):
        with _Patched(_canned('{"answer":"Part time","option_index":"1",'
                              '"confidence":"high"}')):
            r = self.prov.answer(REQ)
        self.assertEqual(r.selected_option_index, 1)  # "1" -> 1
        self.assertEqual(r.confidence, 0.8)            # "high" -> default

    def test_plain_text_fallback(self):
        with _Patched(_canned("Full time")):
            r = self.prov.answer(REQ)
        self.assertEqual(r.answer, "Full time")
        self.assertIsNone(r.selected_option_index)

    def test_http_error_is_reported_not_raised(self):
        with _Patched({"error": {"message": "invalid key"}}, status=401):
            r = self.prov.answer(REQ)
        self.assertFalse(r.success)
        self.assertIn("401", r.error)
        self.assertEqual(r.answer, "")


class TestCost(unittest.TestCase):
    def test_cached_tokens_are_cheaper(self):
        prov = DeepSeekProvider(api_key="sk-test-key")
        full = prov.estimate_cost(1000, 100, cached_tokens=0)
        cached = prov.estimate_cost(1000, 100, cached_tokens=1000)
        self.assertGreater(full, cached)  # cache hits reduce cost
        self.assertGreater(cached, 0)


class TestNoKey(unittest.TestCase):
    def test_missing_key_fails_gracefully(self):
        prov = DeepSeekProvider(api_key=None)
        r = prov.answer(REQ)
        self.assertFalse(r.success)
        self.assertIn("key", r.error.lower())


if __name__ == "__main__":
    unittest.main()
