"""LLM adapters. GroqLLM = real (free tier). MockLLM = offline extractive answerer used by tests/eval/dev;
with vulnerable=True it SIMULATES a gullible model that obeys instructions hidden in context,
so defences can be measured without a network. Real-model numbers must come from GroqLLM."""
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request

from . import config
from .search import tokenize

GROQ_BASE = "https://api.groq.com/openai/v1"


class LLMError(Exception):
    """Provider problem with a message that is safe to show to the user (never contains secrets)."""


class GroqLLM:
    name = "groq"

    def __init__(self, api_key: str, model: str, timeout: int = 40):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def _request(self, path: str, body: dict | None = None, timeout: int | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            GROQ_BASE + path, data=data, method="POST" if body is not None else "GET",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "User-Agent": "vaultgraph/0.2"})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise LLMError(_http_message(e.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise LLMError("Could not reach the Groq API (network error or timeout).") from None
        except ValueError:
            raise LLMError("Groq returned an unreadable response.") from None

    def complete(self, system: str, user: str) -> str:
        body = {"model": self.model, "temperature": 0, "max_tokens": 1024,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"  # reasoning models: keep latency and token use small
        out = self._request("/chat/completions", body)
        try:
            text = (out["choices"][0]["message"].get("content") or "").strip()
        except (KeyError, IndexError, AttributeError):
            raise LLMError("Groq returned an unexpected response shape.") from None
        if not text:
            raise LLMError("The model returned an empty answer. Try again or choose another GROQ_MODEL.")
        return text

    def list_models(self) -> list[str]:
        return [m.get("id", "") for m in self._request("/models", None, timeout=8).get("data", [])]


def _http_message(code: int) -> str:
    return {
        400: "Groq rejected the request (400). The configured GROQ_MODEL may not support these parameters.",
        401: "The Groq API key is invalid or revoked (401). Check GROQ_API_KEY.",
        403: "Groq denied access (403). The key may lack access to this model.",
        404: "The configured GROQ_MODEL was not found (404). It may have been retired; see /status for available models.",
        413: "The request was too large for the model.",
        429: "Groq rate limit reached (429). Free-tier limits apply; wait a moment and retry.",
    }.get(code, f"Groq returned an error (HTTP {code}).")


def _loose(text: str) -> str:
    """What a capable model 'understands': drops invisible chars, re-joins l e t t e r - s p a c e d words."""
    t = "".join(c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf")
    return re.sub(r"\b(?:[A-Za-z] ){2,}[A-Za-z]\b", lambda m: m.group(0).replace(" ", ""), t)


# Directive phrasings the SIMULATED gullible model obeys. Real models obey far more phrasings than any list.
_OBEY = re.compile(
    r"(ignore (all |any )?(the )?(previous|prior) instructions"
    r"|forget (everything|all) (you were told|you have been told|above)"
    r"|pay no attention to (the )?(previous|prior|above) (guidance|instructions|text))")


class MockLLM:
    name = "mock"
    model = "offline-extractive"

    def __init__(self, vulnerable: bool = False):
        self.vulnerable = vulnerable

    def complete(self, system: str, user: str) -> str:
        m = re.search(r"<context[^>]*>(.*?)</context[^>]*>", user, re.S)
        ctx = m.group(1) if m else ""
        if self.vulnerable:
            loose = _loose(ctx)
            low = loose.lower()
            if _OBEY.search(low):
                if re.search(r"reveal (your |the )?system prompt", low):
                    return system
                r = re.search(r"reply with:\s*(\S+)", loose, re.I)
                if r:
                    return r.group(1)
                img = re.search(r"!\[[^\]]*\]\([^)]*\)", loose)
                if img:
                    return "Here is the answer. " + img.group(0)
        q = re.search(r"Question:\s*(.*)$", user, re.S)
        qtok = set(tokenize(q.group(1) if q else ""))
        cands = []
        for line in ctx.splitlines():
            lm = re.match(r"\s*\[c(\d+)\]\s*(.*)", line)
            if lm:
                for s in re.split(r"(?<=[.!?])\s+", lm.group(2)):
                    cands.append((len(qtok & set(tokenize(s))), s, lm.group(1)))
            fm = re.match(r"\s*- (.*?) \(evidence c(\d+)\)", line)
            if fm:
                cands.append((len(qtok & set(tokenize(fm.group(1)))), fm.group(1), fm.group(2)))
        cands = [c for c in sorted(cands, key=lambda x: -x[0]) if c[0] > 0][:2]
        if not cands:
            return "I don't know based on the provided context."
        return " ".join(f"{s.rstrip('.')} [c{cid}]." for _, s, cid in cands)


def get_llm():
    p = config.LLM_PROVIDER
    if p == "mock":
        return MockLLM(vulnerable=False)
    if p == "groq" and not config.GROQ_API_KEY:
        raise LLMError("LLM_PROVIDER=groq but GROQ_API_KEY is not set on the server.")
    if config.GROQ_API_KEY and p in ("auto", "groq"):
        return GroqLLM(config.GROQ_API_KEY, config.GROQ_MODEL)
    return MockLLM(vulnerable=False)


_health: dict = {"at": 0.0, "value": None}
_lock = threading.Lock()


def llm_status(check: bool = True) -> dict:
    """Provider summary for /status. Groq availability is verified against Groq's live model list (cached 5 min)."""
    p = config.LLM_PROVIDER
    if p == "mock" or (p == "auto" and not config.GROQ_API_KEY):
        return {"provider": "mock", "model": MockLLM.model, "configured": p == "mock" or bool(config.GROQ_API_KEY),
                "healthy": True, "detail": "Offline extractive mock (no API key configured)." if p == "auto" else "Forced mock mode."}
    base = {"provider": "groq", "model": config.GROQ_MODEL, "configured": bool(config.GROQ_API_KEY)}
    if not config.GROQ_API_KEY:
        return {**base, "healthy": False, "detail": "GROQ_API_KEY is not set on the server."}
    if not check:
        return {**base, "healthy": None, "detail": "Not checked."}
    with _lock:
        if _health["value"] is not None and time.monotonic() - _health["at"] < 300 and _health["value"]["model"] == config.GROQ_MODEL:
            return _health["value"]
        try:
            models = GroqLLM(config.GROQ_API_KEY, config.GROQ_MODEL).list_models()
            ok = config.GROQ_MODEL in models
            val = {**base, "healthy": ok, "detail": "Groq reachable; model available." if ok else
                   f"Groq reachable, but model '{config.GROQ_MODEL}' is not in the live model list. "
                   f"Set GROQ_MODEL to one of: {', '.join(sorted(m for m in models if 'whisper' not in m and 'guard' not in m)[:8])}"}
        except LLMError as e:
            val = {**base, "healthy": False, "detail": str(e)}
        _health.update(at=time.monotonic(), value=val)
        return val
