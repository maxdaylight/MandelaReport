"""
Wayback helpers using the Internet Archive CDX API directly.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false
from datetime import datetime
from typing import Dict, List, Optional

import requests


def _fmt_cdx_ts(dt: datetime) -> str:
    # CDX expects YYYYMMDDhhmmss
    return dt.strftime("%Y%m%d%H%M%S")


def pick_snapshots(
    url: str,
    since: Optional[datetime],
    until: Optional[datetime],
    count: int,
) -> List[Dict]:
    """
    Query the Internet Archive CDX API and pick up to `count` evenly spaced
    snapshots. Returns list of dicts with keys: timestamp (ISO), original,
    archive_url.
    """
    try:
        params = {
            "url": url,
            "output": "json",
            "fl": "timestamp,original,statuscode",
            "filter": "statuscode:200",
            "collapse": "digest",
            "limit": "2000",
        }
        if since:
            # start of day if time not provided
            params["from"] = _fmt_cdx_ts(since)
        if until:
            params["to"] = _fmt_cdx_ts(until)

        r = requests.get(
            "https://web.archive.org/cdx/search/cdx",
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if not data or len(data) <= 1:
            return []
        # first row is header
        rows = data[1:]
        # Build simple snapshot list with (ts, original)
        snapshots = [
            {"ts": row[0], "original": row[1]} for row in rows if len(row) >= 2
        ]
        if not snapshots:
            return []
        # Apply "price is right" endpoints with even distribution:
        # - last pick is ALWAYS the most recent snapshot at/before `until`
        # - first pick is the earliest snapshot at/after `since` (reverse)
        # - distribute remaining picks as evenly as possible between them
        total = len(snapshots)
        n = max(1, min(count, total))

        # Always include last index when at least one snapshot requested
        if n == 1:
            picks = [snapshots[-1]]
        elif n == 2:
            picks = [snapshots[0], snapshots[-1]]
        else:
            first_i, last_i = 0, total - 1
            # Evenly spaced integer indices across [first_i, last_i], inclusive
            # using floor to avoid going past the last index (price-is-right).
            idxs = [int(first_i + (last_i - first_i) * k / (n - 1)) for k in range(n)]
            # Deduplicate while preserving order
            seen = set()
            ordered: List[int] = []
            for i in idxs:
                if i not in seen:
                    seen.add(i)
                    ordered.append(i)
            # If dedup collapsed (e.g., very small total), backfill from the
            # end to ensure we still return up to n unique indices including
            # last.
            i = last_i
            while len(ordered) < n and i >= 0:
                if i not in seen:
                    seen.add(i)
                    # Insert before the final element to keep last element at
                    # end
                    ordered.insert(-1 if ordered else 0, i)
                i -= 1
            picks = [snapshots[i] for i in ordered[:n]]

        result: List[Dict] = []
        for s in picks:
            ts_iso = datetime.strptime(s["ts"], "%Y%m%d%H%M%S").isoformat()
            archive_url = f"https://web.archive.org/web/{s['ts']}/{s['original']}"
            result.append(
                {
                    "timestamp": ts_iso,
                    "original": s["original"],
                    "archive_url": archive_url,
                }
            )
        return result
    except Exception:
        return []


def fetch_archive_html(archive_url: str, ua: str) -> str:
    r = requests.get(archive_url, headers={"User-Agent": ua}, timeout=20)
    r.raise_for_status()
    return r.text
