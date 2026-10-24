"""Thin LLM client for Gemini and Groq using plain REST calls (requests only).

No vendor SDKs are required, which keeps deployment on Streamlit Community
Cloud light and avoids SDK version drift.
"""
import json
import re
from typing import Any

import requests

from core.config import PROVIDER_GEMINI, PROVIDER_GROQ

SYSTEM_PROMPT = (
    "You are a senior travel planner with deep, accurate knowledge of cities worldwide. "
    "Respond ONLY with valid JSON - no markdown fences, no commentary. "
    "Only suggest real places that exist. Coordinates must be accurate decimal degrees."
)


class LLMError(Exception):
    """Raised for any failure talking to, or parsing output from, an LLM."""


def _http_error(resp: requests.Response) -> str:
    try:
        msg = resp.json()
        if isinstance(msg, dict):
            err = msg.get("error", msg)
            msg = err.get("message", err) if isinstance(err, dict) else err
    except ValueError:
        msg = resp.text
    return "HTTP %s: %s" % (resp.status_code, str(msg)[:300])


def call_llm(provider: str, api_key: str, model: str, prompt: str,
             system: str = SYSTEM_PROMPT, timeout: int = 90) -> str:
    """Send one prompt and return the raw text of the model's reply."""
    if not api_key:
        raise LLMError("No API key supplied.")
    try:
        if provider == PROVIDER_GEMINI:
            url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
            resp = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 8192,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=timeout,
            )
            if resp.status_code != 200:
                raise LLMError("Gemini error - " + _http_error(resp))
            data = resp.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts)
            except (KeyError, IndexError, TypeError):
                raise LLMError("Gemini returned an empty or blocked response.")

        if provider == PROVIDER_GROQ:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0.7,
                    "max_tokens": 8000,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=timeout,
            )
            if resp.status_code != 200:
                raise LLMError("Groq error - " + _http_error(resp))
            try:
                return resp.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                raise LLMError("Groq returned an empty response.")

        raise LLMError("Unknown provider: %s" % provider)
    except requests.exceptions.Timeout:
        raise LLMError("The AI request timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise LLMError("Network problem contacting the AI service: %s" % exc)


def extract_json(text: str) -> Any:
    """Parse JSON from model output, tolerating code fences and stray prose."""
    if not text:
        raise LLMError("The AI returned an empty reply.")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except ValueError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(open_c), cleaned.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except ValueError:
                continue
    raise LLMError("Could not parse the AI reply as JSON.")


def ask_json(provider: str, api_key: str, model: str, prompt: str, retries: int = 1) -> Any:
    """call_llm + extract_json with a retry when the JSON is malformed."""
    last = None
    for _ in range(retries + 1):
        try:
            return extract_json(call_llm(provider, api_key, model, prompt))
        except LLMError as exc:
            last = exc
            if "parse" not in str(exc).lower() and "empty" not in str(exc).lower():
                break  # network/auth errors will not improve on retry
    raise last
