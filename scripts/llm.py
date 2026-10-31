#!/usr/bin/env python3
"""Minimal LLM client: OLLAMA | GEMINI | OPENAI | ANTHROPIC via plain HTTP."""
from __future__ import annotations
import json, os, time, urllib.request, urllib.error
from pathlib import Path

def _load_dotenv():
    env = Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_dotenv()

class LLMError(RuntimeError):
    pass

def complete(prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower().strip()
    if provider == "ollama":
        return _with_retry(lambda: _ollama(prompt, system, temperature))
    if provider == "gemini":
        return _with_retry(lambda: _gemini(prompt, system, temperature))
    if provider == "openai":
        return _with_retry(lambda: _openai_compatible(
            prompt, system, temperature,
            base=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            key=os.environ["OPENAI_API_KEY"],
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini")))
    if provider == "anthropic":
        return _with_retry(lambda: _anthropic(prompt, system, temperature))
    raise LLMError(f"Unknown LLM_PROVIDER={provider}")

def _with_retry(fn, attempts: int = 3):
    delay = 2.0
    last = None
    for i in range(attempts):
        try:
            return fn()
        except LLMError as e:
            last = e
            msg = str(e).lower()
            retryable = any(x in msg for x in (
                "429", "rate", "quota", "resource_exhausted", "503", "500",
                "timeout", "temporarily", "unavailable",
            ))
            if not retryable or i == attempts - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 60.0)
    raise last  # pragma: no cover

def _post(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        # strip query string so key never appears in errors
        safe_url = url.split("?")[0]
        raise LLMError(f"HTTP {e.code} from {safe_url}: {body[:500]}") from e
    except Exception as e:
        raise LLMError(f"request failed: {e}") from e

def _ollama(prompt, system, temperature):
    """Local Ollama or Ollama Cloud.

    Local:  OLLAMA_HOST=http://127.0.0.1:11434 (default), no key.
    Cloud:  OLLAMA_HOST=https://ollama.com and OLLAMA_API_KEY=... (Bearer).
    """
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:3b")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {}
    api_key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    out = _post(f"{host}/api/chat", payload, headers)
    msg = out.get("message") or {}
    content = msg.get("content") or ""
    # Some cloud reasoning models put scratchpad in `thinking` / `reasoning`.
    # Prefer content; callers may strip leftover fences.
    if not content and msg.get("thinking"):
        content = msg.get("thinking")
    return content

def _gemini(prompt, system, temperature):
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    text = prompt if not system else f"{system}\n\n{prompt}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"temperature": temperature},
    }
    out = _post(url, payload, {})
    cands = out.get("candidates") or []
    if not cands:
        raise LLMError(f"Gemini empty candidates: {json.dumps(out)[:400]}")
    parts = cands[0].get("content", {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts)

def _openai_compatible(prompt, system, temperature, base, key, model):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    out = _post(f"{base.rstrip('/')}/chat/completions",
                {"model": model, "messages": messages, "temperature": temperature},
                {"Authorization": f"Bearer {key}"})
    return out["choices"][0]["message"]["content"]

def _anthropic(prompt, system, temperature):
    key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    payload = {
        "model": model, "max_tokens": 4096, "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    out = _post("https://api.anthropic.com/v1/messages", payload, {
        "x-api-key": key, "anthropic-version": "2023-06-01",
    })
    return "".join(p.get("text", "") for p in out["content"] if p.get("type") == "text")
