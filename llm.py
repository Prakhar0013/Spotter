"""Thin client for a local Ollama server. No data leaves the machine."""
import json
import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("SPOTTER_MODEL", "qwen2.5:7b")


def is_up():
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).ok
    except requests.RequestException:
        return False


def chat(system, user, json_mode=False, temperature=0.3, timeout=300):
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()["message"]["content"]


def chat_json(system, user):
    text = chat(system, user, json_mode=True, temperature=0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start:end + 1])
