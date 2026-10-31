#!/usr/bin/env python3
"""Minimal LLM client: OLLAMA | GEMINI | OPENAI | ANTHROPIC via plain HTTP."""
from __future__ import annotations
import json, os, urllib.request, urllib.error
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

def complete(prompt: str, system: str | None = None) -> str:
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower().strip()
    if provider == "ollama":
        return _ollama(prompt, system)
    if provider == "gemini":
        return _gemini(prompt, system)
    if provider == "openai":
        return _openai_compatible(prompt, system,
            base=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            key=os.environ["OPENAI_API_KEY"],
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    if provider == "anthropic":
        return _anthropic(prompt, system)
    raise LLMError(f"Unknown LLM_PROVIDER={provider}")

def _post(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise LLMError(f"HTTP {e.code} from {url}: {body[:500]}") from e

def _ollama(prompt, system):
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:3b")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    out = _post(f"{host}/api/chat", {"model": model, "messages": messages, "stream": False}, {})
    return out["message"]["content"]

def _gemini(prompt, system):
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    text = prompt if not system else f"{system}\n\n{prompt}"
    out = _post(url, {"contents": [{"parts": [{"text": text}]}]}, {})
    return out["candidates"][0]["content"]["parts"][0]["text"]

def _openai_compatible(prompt, system, base, key, model):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    out = _post(f"{base.rstrip('/')}/chat/completions",
                {"model": model, "messages": messages, "temperature": 0},
                {"Authorization": f"Bearer {key}"})
    return out["choices"][0]["message"]["content"]

def _anthropic(prompt, system):
    key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    payload = {"model": model, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}
    if system:
        payload["system"] = system
    out = _post("https://api.anthropic.com/v1/messages", payload, {
        "x-api-key": key, "anthropic-version": "2023-06-01",
    })
    return "".join(p.get("text", "") for p in out["content"] if p.get("type") == "text")
