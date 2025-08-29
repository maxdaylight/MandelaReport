# pyright: reportMissingImports=false
import urllib.robotparser as robotparser
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx


@dataclass
class LiveFetchResult:
    allowed: bool
    html: Optional[str]
    status: Optional[int]
    note: str


def _robots_allowed(url: str, ua: str) -> Optional[bool]:
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(ua, url)
    except Exception:
        return False


async def fetch_live(
    url: str,
    ua: str,
    timeout: int,
    max_mb: int,
    obey_robots: bool,
) -> LiveFetchResult:
    if obey_robots:
        allowed = _robots_allowed(url, ua)
        if not allowed:
            return LiveFetchResult(
                allowed=False,
                html=None,
                status=None,
                note="robots disallow",
            )
    try:
        async with httpx.AsyncClient(
            http2=True,
            headers={"User-Agent": ua},
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            ctype = resp.headers.get("content-type", "")
            if "text/html" not in ctype.lower():
                return LiveFetchResult(
                    True,
                    None,
                    resp.status_code,
                    "non-HTML content",
                )
            if len(resp.content) > max_mb * 1024 * 1024:
                return LiveFetchResult(
                    True,
                    None,
                    resp.status_code,
                    "response too large",
                )
            return LiveFetchResult(True, resp.text, resp.status_code, "ok")
    except Exception as e:
        return LiveFetchResult(True, None, None, f"error: {e}")
