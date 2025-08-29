"""
Summary helpers.

"""

# pyright: reportMissingImports=false
import json
from typing import Dict, List

import httpx


def _rule_summary(
    url: str,
    pairs: List[Dict],
    from_text: str,
    to_text: str,
) -> str:
    delta = len(to_text.split()) - len(from_text.split())
    sign = "increased" if delta >= 0 else "decreased"
    spans = ", ".join(
        [f"{p['label']} ({p['from_when']} -> {p['to_when']})" for p in pairs]
    )
    return (
        f"Mandela Report (rule-based):\n"
        f"- Subject: {url}\n"
        f"- Spans compared: {spans}\n"
        f"- Overall word count {sign} by {abs(delta)} words.\n"
        f"- See highlighted insertions and deletions below for details.\n"
    )


def _llm_summary(
    url: str,
    pairs: List[Dict],
    from_text: str,
    to_text: str,
    base_url: str,
) -> str:
    prompt = (
        "You are a concise change analyst. Given two versions of a webpage,\n"
        "summarize the key changes for a non-technical reader.\n"
        "Focus on: new/removed sections, wording shifts affecting meaning\n"
        "(dates, prices, policies), and metadata like titles or disclaimers.\n"
        "Write 5-10 bullet points and a one-line TL;DR.\n"
        f"URL: {url}\n"
        f"Spans: {json.dumps(pairs)}\n"
        "----- BEFORE -----\n"
        f"{from_text[:8000]}\n"
        "----- AFTER -----\n"
        f"{to_text[:8000]}\n"
    )
    try:
        payload = {
            "model": "tinyllama-1.1b-chat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Be precise, neutral, and helpful. Focus on how "
                        "changes could lead to mismatched public memory "
                        "(Mandela Effects)."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 400,
        }
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{base_url}/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"(LLM unavailable, fallback to rule-based) {str(e)}"


def summarize_changes(
    url: str,
    pairs: List[Dict],
    from_text: str,
    to_text: str,
    provider: str,
    llm_base_url: str,
    ua: str,
) -> str:
    provider = provider.lower()
    if provider == "rule":
        return _rule_summary(url, pairs, from_text, to_text)
    elif provider == "llm":
        return _llm_summary(url, pairs, from_text, to_text, llm_base_url)
    else:
        s = _llm_summary(url, pairs, from_text, to_text, llm_base_url)
        if s.startswith("(LLM unavailable"):
            return _rule_summary(url, pairs, from_text, to_text)
        return s
