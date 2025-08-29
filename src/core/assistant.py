"""
Conversational assistant to interpret user messages into MandelaReport slots.

Slots schema:
{ url: str|None, since: str|None, until: str|None, snapshots: int|None,
  style: str|None }

Returns dict: { reply: str, slots: {...}, ready: bool }
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, cast

try:
    from dateutil import parser as du_parser
    from dateutil.relativedelta import relativedelta
except Exception:  # pragma: no cover - editor/env guard
    du_parser = None  # type: ignore
    relativedelta = None  # type: ignore

import httpx

URL_RE = re.compile(r"https?://[^\s]+", re.I)
DOMAIN_RE = re.compile(r"\b([a-z0-9-]+\.)+[a-z]{2,}\b", re.I)
DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def _iso_days_ago(n: int) -> str:
    return (datetime.utcnow().date() - timedelta(days=n)).isoformat()


def _since_span(n: int, unit: str) -> str:
    unit = unit.lower()
    if "year" in unit:
        days = 365 * n
    elif "month" in unit:
        days = 30 * n
    elif "week" in unit:
        days = 7 * n
    else:
        days = 1 * n
    return _iso_days_ago(days)


def _normalize_url(u: str | None) -> str | None:
    if not u:
        return u
    ul = u.strip()
    if not ul:
        return None
    if not re.match(r"^https?://", ul, re.I):
        ul = "https://" + ul
    return ul


def _merge_slots(
    existing: Dict[str, Any],
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(existing or {})
    for k, v in (updates or {}).items():
        if v in (None, ""):
            continue
        out[k] = v
    return out


def _slots_ready(slots: Dict[str, Any]) -> bool:
    return bool(slots.get("url"))


def _heuristic_extract(message: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    ml = message.lower()
    today = datetime.utcnow().date()
    m = URL_RE.search(message)
    if m:
        slots["url"] = m.group(0)
    else:
        d = DOMAIN_RE.search(message)
        if d:
            slots["url"] = f"https://{d.group(0)}"
    # dates - pick first two in order as since/until
    dates = DATE_RE.findall(message)
    if dates:

        def fmt(d):
            return f"{d[0]}-{d[1]}-{d[2]}"

        if len(dates) >= 1:
            slots["since"] = fmt(dates[0])
        if len(dates) >= 2:
            slots["until"] = fmt(dates[1])
    else:
        # year-only phrases like "from 1999 to now" or "2015 - 2018"
        years = [int(y) for y in YEAR_RE.findall(message)]
        if years:
            years.sort()
            y1 = years[0]
            if 1990 <= y1 <= 2100:
                slots["since"] = f"{y1:04d}-01-01"
            if len(years) >= 2:
                y2 = years[-1]
                if 1990 <= y2 <= 2100 and y2 >= y1:
                    slots["until"] = f"{y2:04d}-12-31"
        # Relative phrases
        if re.search(r"\b(now|today)\b", ml):
            # leave until open to mean up to current time
            slots.setdefault("until", None)
        # since/from yesterday -> since yesterday; bare 'yesterday' -> until
        if re.search(r"\b(since|from)\s+yesterday\b", ml):
            slots["since"] = _iso_days_ago(1)
        elif re.search(r"\buntil\s+yesterday\b", ml):
            slots["until"] = _iso_days_ago(1)
        elif re.search(r"\byesterday\b", ml):
            slots["until"] = _iso_days_ago(1)
        # last week/month/year
        if re.search(r"\blast week\b", ml):
            slots.setdefault("since", _iso_days_ago(7))
        if re.search(r"\blast month\b", ml):
            slots.setdefault("since", _iso_days_ago(30))
        if re.search(r"\blast year\b", ml):
            slots.setdefault("since", _iso_days_ago(365))
        # past/last N years|months|weeks|days
        span_pat = r"\b(past|last)\s+(\d{1,3})\s+" r"(years?|months?|weeks?|days?)\b"
        m_span = re.search(span_pat, ml)
        if m_span:
            n = int(m_span.group(2))
            unit = m_span.group(3)
            slots.setdefault("since", _since_span(n, unit))
        # since last year -> Jan 1 of last year
        if re.search(r"\bsince last year\b", ml):
            slots["since"] = f"{today.year - 1:04d}-01-01"
        # until last year -> Dec 31 of last year
        if re.search(r"\buntil last year\b", ml):
            slots["until"] = f"{today.year - 1:04d}-12-31"
        # until last month -> last day of previous month
        if re.search(r"\buntil last month\b", ml):
            first_of_month = today.replace(day=1)
            last_of_prev = first_of_month - timedelta(days=1)
            slots["until"] = last_of_prev.isoformat()

        # dateutil-powered natural phrases (best-effort, guarded)
        # Examples: "last Friday", "end of Q2 2023", "mid 2016"
        try:
            if du_parser is not None:
                # If explicit YYYY-MM-DD already present,
                # skip to avoid conflict
                if not DATE_RE.search(message):
                    # Try parsing 'since ...' and 'until ...' segments
                    m_since = re.search(r"\b(since|from)\s+([^,;]+)", ml)
                    if m_since and not slots.get("since"):
                        _parsed = du_parser.parse(
                            m_since.group(2),
                            fuzzy=True,
                            default=datetime.utcnow(),
                        )
                        if isinstance(_parsed, tuple):
                            _parsed = _parsed[0]
                        dt = cast(datetime, _parsed)
                        slots["since"] = dt.date().isoformat()
                    m_until = re.search(r"\buntil\s+([^,;]+)", ml)
                    if m_until and not slots.get("until"):
                        _parsed2 = du_parser.parse(
                            m_until.group(1),
                            fuzzy=True,
                            default=datetime.utcnow(),
                        )
                        if isinstance(_parsed2, tuple):
                            _parsed2 = _parsed2[0]
                        dt2 = cast(datetime, _parsed2)
                        slots["until"] = dt2.date().isoformat()
                    # Handle 'mid <year>' as June 15 of that year
                    m_mid = re.search(r"\bmid\s+(\d{4})\b", ml)
                    if m_mid and not slots.get("since"):
                        y = int(m_mid.group(1))
                        slots["since"] = f"{y:04d}-06-15"
                    # 'end of Q2 2023' -> until = 2023-06-30
                    m_q = re.search(r"\bend of q([1-4])\s+(\d{4})\b", ml)
                    if m_q and not slots.get("until"):
                        q = int(m_q.group(1))
                        y = int(m_q.group(2))
                        month = q * 3
                        # last day of the quarter = first day of next month
                        # minus 1 day
                        next_month = month + 1
                        next_year = y + (1 if next_month == 13 else 0)
                        next_month = 1 if next_month == 13 else next_month
                        first_of_next = datetime(next_year, next_month, 1)
                        last_day = first_of_next - timedelta(days=1)
                        slots["until"] = last_day.date().isoformat()
        except Exception:
            # ignore parsing failures; keep earlier heuristics
            pass
    if "rule" in message.lower():
        slots["style"] = "rule"
    if "llm" in message.lower():
        slots["style"] = "llm"
    # snapshots: prefer patterns like "5 snapshots";
    # fallback to presence of 7/5/3
    m_sn = re.search(r"(\d+)\s*(?:snapshots?|points?)", message, re.I)
    if m_sn:
        try:
            n = int(m_sn.group(1))
            # clamp to supported set
            if n in (3, 5, 7):
                slots["snapshots"] = n
        except Exception:
            pass
    if "snapshots" not in slots:
        if "7" in message:
            slots["snapshots"] = 7
        elif "5" in message:
            slots["snapshots"] = 5
        elif "3" in message:
            slots["snapshots"] = 3
    return slots


def interpret_message(
    message: str,
    slots: Dict[str, Any] | None,
    base_url: str,
) -> Dict[str, Any]:
    """
    Use the local LLM (OpenAI-compatible) to interpret the user's message.
    Fallback to heuristics if the model isn't available.
    """
    system = (
        "You are Mandela for the Mandela Report. You help investigate "
        "possible Mandela Effects by comparing a webpage across time. "
        "Ask short, friendly questions and update slots. "
        "Slots: url (required), since (YYYY-MM-DD, optional), until "
        "(YYYY-MM-DD, optional), snapshots (3|5|7, default 5), style "
        "(llm|rule, default llm). When url is set, you may set ready=true. "
        'Respond with ONLY a single JSON object: {"reply": str, '
        '"slots": {...}, "ready": bool}.'
    )
    slots = slots or {}
    try:
        payload = {
            "model": "tinyllama-1.1b-chat",
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "message": message,
                            "slots": slots,
                        }
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 300,
        }
        with httpx.Client(timeout=20.0) as client:
            r = client.post(f"{base_url}/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"].strip()
            # Try to locate JSON in response
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                obj = json.loads(content[start : end + 1])
                merged = _merge_slots(slots, obj.get("slots") or {})
                # Fill any missing fields using heuristics
                # (do not override provided ones)
                heur = _heuristic_extract(message)
                for k, v in heur.items():
                    if k not in merged or merged.get(k) in (None, ""):
                        merged[k] = v
                # Normalize fields
                merged["url"] = _normalize_url(merged.get("url"))
                # If the user's message says 'now' or 'today',
                # force open-ended until regardless of what the LLM
                # suggested (prevents stale hard-coded dates).
                if re.search(r"\b(now|today)\b", message, re.I):
                    merged["until"] = None
                elif isinstance(merged.get("until"), str) and merged[
                    "until"
                ].strip().lower() in {"now", "today"}:
                    merged["until"] = None
                # If the user's message says 'yesterday', use an explicit
                # date string for clarity in both slots and reply.
                if re.search(r"\byesterday\b", message, re.I):
                    merged["until"] = (
                        datetime.utcnow().date() - timedelta(days=1)
                    ).isoformat()
                # defaults
                if "snapshots" not in merged:
                    merged["snapshots"] = 5
                if "style" not in merged:
                    merged["style"] = "llm"
                # Additional phrase-based overrides for relative ranges
                ml = message.lower()
                tdy = datetime.utcnow().date()
                if not merged.get("since") and re.search(r"\blast week\b", ml):
                    merged["since"] = _iso_days_ago(7)
                if not merged.get("since") and re.search(r"\blast month\b", ml):
                    merged["since"] = _iso_days_ago(30)
                if not merged.get("since") and re.search(r"\blast year\b", ml):
                    merged["since"] = _iso_days_ago(365)
                span_pat = (
                    r"\b(past|last)\s+(\d{1,3})\s+" r"(years?|months?|weeks?|days?)\b"
                )
                m_span = re.search(span_pat, ml)
                if not merged.get("since") and m_span:
                    n = int(m_span.group(2))
                    unit = m_span.group(3)
                    merged["since"] = _since_span(n, unit)
                if re.search(r"\bsince last year\b", ml):
                    merged["since"] = f"{tdy.year - 1:04d}-01-01"
                if re.search(r"\buntil last year\b", ml):
                    merged["until"] = f"{tdy.year - 1:04d}-12-31"
                if re.search(r"\buntil last month\b", ml):
                    first_of_month = tdy.replace(day=1)
                    last_of_prev = first_of_month - timedelta(days=1)
                    merged["until"] = last_of_prev.isoformat()
                # Build a fallback reply if the LLM didn't provide one
                reply = obj.get("reply") or ""
                if not reply:
                    parts = ["Got it."]
                    if merged.get("url"):
                        parts.append(f"URL set to {merged['url']}.")
                    if merged.get("since"):
                        parts.append(f"Using since {merged['since']}.")
                    if merged.get("until"):
                        parts.append(f"Using until {merged['until']}.")
                    else:
                        # If user indicated 'now/today', state today's date
                        # explicitly for clarity
                        if re.search(r"\b(now|today)\b", message, re.I):
                            today = datetime.utcnow().date().isoformat()
                            parts.append(f"Using until {today}.")
                    parts.append(
                        "You can also tell me exact dates like 2024-01-01 and "
                        "a snapshot count (3, 5, or 7)."
                    )
                    reply = " ".join(parts)
                return {
                    "reply": reply,
                    "slots": merged,
                    # Consider ready when required fields are present
                    "ready": _slots_ready(merged),
                }
            raise ValueError("No JSON in LLM output")
    except Exception:
        # Heuristic fallback
        extracted = _heuristic_extract(message)
        merged = _merge_slots(slots, extracted)
        merged["url"] = _normalize_url(merged.get("url"))
        if re.search(r"\b(now|today)\b", message, re.I):
            merged["until"] = None
        elif isinstance(merged.get("until"), str) and merged[
            "until"
        ].strip().lower() in {"now", "today"}:
            merged["until"] = None
        if re.search(r"\byesterday\b", message, re.I):
            merged["until"] = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
        if "snapshots" not in merged:
            merged["snapshots"] = 5
        if "style" not in merged:
            merged["style"] = "llm"
        # Also handle relative phrases directly in fallback path
        ml = message.lower()
        tdy = datetime.utcnow().date()
        if not merged.get("since") and re.search(r"\blast week\b", ml):
            merged["since"] = _iso_days_ago(7)
        if not merged.get("since") and re.search(r"\blast month\b", ml):
            merged["since"] = _iso_days_ago(30)
        if not merged.get("since") and re.search(r"\blast year\b", ml):
            merged["since"] = _iso_days_ago(365)
        span_pat = r"\b(past|last)\s+(\d{1,3})\s+" r"(years?|months?|weeks?|days?)\b"
        m_span = re.search(span_pat, ml)
        if not merged.get("since") and m_span:
            n = int(m_span.group(2))
            unit = m_span.group(3)
            merged["since"] = _since_span(n, unit)
        if re.search(r"\bsince last year\b", ml):
            merged["since"] = f"{tdy.year - 1:04d}-01-01"
        if re.search(r"\buntil last year\b", ml):
            merged["until"] = f"{tdy.year - 1:04d}-12-31"
        if re.search(r"\buntil last month\b", ml):
            first_of_month = tdy.replace(day=1)
            last_of_prev = first_of_month - timedelta(days=1)
            merged["until"] = last_of_prev.isoformat()
        reply_parts = ["Got it."]
        if merged.get("url"):
            reply_parts.append(f"URL set to {merged['url']}.")
        if merged.get("since"):
            reply_parts.append(f"Using since {merged['since']}.")
        if merged.get("until"):
            reply_parts.append(f"Using until {merged['until']}.")
        else:
            if re.search(r"\b(now|today)\b", message, re.I):
                today = datetime.utcnow().date().isoformat()
                reply_parts.append(f"Using until {today}.")
        reply_parts.append(
            "You can also tell me exact dates like 2024-01-01 and a "
            "snapshot count (3, 5, or 7)."
        )
        reply = " ".join(reply_parts)
        return {
            "reply": reply,
            "slots": merged,
            "ready": _slots_ready(merged),
        }
