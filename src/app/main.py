# pyright: reportMissingImports=false
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from src.config import get_settings
from src.core.assistant import interpret_message
from src.core.diff import diff_change_ratio, diff_texts_html
from src.core.extract import extract_title_text
from src.core.fetch import fetch_live
from src.core.summarize import summarize_changes
from src.core.wayback import fetch_archive_html, pick_snapshots
from src.storage.db import (create_report, get_report, get_snapshot_html,
                            init_db, list_snapshots, purge_old_reports,
                            save_snapshot)
from src.storage.db import vacuum as db_vacuum

env = Environment(
    loader=FileSystemLoader("templates"), autoescape=select_autoescape(["html", "xml"])
)

app = FastAPI(title="Mandela Report", version="0.1.0")
settings = get_settings()


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add common security-related HTTP headers to every response.

    - Content-Security-Policy: restrict sources; do not allow inline
      scripts by default.
    - X-Frame-Options: DENY
    - X-Content-Type-Options: nosniff
    - Referrer-Policy: same-origin
    - Strict-Transport-Security (HSTS): enabled only when behind TLS
      (based on settings)
    """
    resp: Response = await call_next(request)
    # Minimal, conservative CSP: only allow same-origin for styles,
    # images and frames
    csp = (
        "default-src 'none'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'self';"
    )
    resp.headers.setdefault("Content-Security-Policy", csp)
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    # Only set HSTS when settings indicate TLS enforcement
    # (do not enable in dev)
    try:
        if getattr(settings, "enforce_https", False):
            # 1 year plus preload hint
            hsts_val = "max-age=31536000; includeSubDomains; preload"
            resp.headers.setdefault("Strict-Transport-Security", hsts_val)
    except Exception:
        pass
    return resp


class DiffRequest(BaseModel):
    url: str
    since: Optional[str] = None  # YYYY-MM-DD
    until: Optional[str] = None  # YYYY-MM-DD
    snapshots: int = 3  # number of historical snapshots to compare


def parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d")


@app.on_event("startup")
async def on_startup():
    await init_db()
    # Kick off background retention worker
    if settings.retention_enabled:
        # start_retention_worker returns a callable that itself starts the
        # actual asyncio task. Call it here to schedule the background
        # coroutine rather than registering another startup handler.
        start_retention_worker()
    # Mount static assets (logo, favicon)
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
    except Exception:
        # If already mounted (hot reload), ignore
        pass


def start_retention_worker():
    async def _worker():
        import asyncio

        while True:
            try:
                deleted = await purge_old_reports(settings.retention_days)
                if deleted and settings.vacuum_after_purge:
                    await db_vacuum()
            except Exception:
                # Best-effort: don't crash app due to housekeeping error
                pass
            # sleep between runs
            await asyncio.sleep(settings.retention_interval_hours * 3600)

    import asyncio

    loop = asyncio.get_event_loop()
    loop.create_task(_worker())
    # return a no-op callback for the startup handler API

    async def _noop():
        return None

    return _noop


@app.get("/", response_class=HTMLResponse)
async def wizard_view():
    template = env.get_template("wizard.html")
    return HTMLResponse(template.render())


@app.post("/assistant")
async def assistant_route(payload: dict):
    message = str(payload.get("message") or "").strip()
    slots = payload.get("slots") or {}
    if not message:
        return {
            "reply": "Tell me the page URL to begin.",
            "slots": slots,
            "ready": False,
        }
    res = interpret_message(message, slots, settings.llm_base_url)
    return res


@app.post("/diff")
async def make_diff(req: DiffRequest):
    url = str(req.url)
    since_dt = parse_date(req.since)
    until_dt = parse_date(req.until) or datetime.utcnow()
    if since_dt and since_dt > until_dt:
        raise HTTPException(400, "since must be <= until")

    report_id = str(uuid.uuid4())
    await create_report(report_id=report_id, url=url)

    # 1) Fetch live (respect robots)
    live_html: Optional[str] = None
    try:
        live_res = await fetch_live(
            url=url,
            ua=settings.user_agent,
            timeout=settings.request_timeout,
            max_mb=settings.max_response_mb,
            obey_robots=settings.obey_robots,
        )
        if live_res.allowed and live_res.html:
            live_html = live_res.html
            title, text = extract_title_text(live_html)
            await save_snapshot(
                report_id=report_id,
                source="live",
                when=datetime.utcnow().isoformat(),
                url=url,
                title=title,
                text=text,
                html=live_html,
            )
    except Exception:
        pass

    # 2) Pick Wayback snapshots
    wb = pick_snapshots(
        url=url,
        since=since_dt,
        until=until_dt,
        count=max(1, req.snapshots),
    )
    # 3) Fetch Wayback HTML and store
    for meta in wb:
        try:
            html = fetch_archive_html(
                meta["archive_url"],
                ua=settings.user_agent,
            )
            title, text = extract_title_text(html)
            await save_snapshot(
                report_id=report_id,
                source="wayback",
                when=meta["timestamp"],
                url=meta["original"],
                title=title,
                text=text,
                html=html,
            )
        except Exception:
            continue

    # 4) Build diffs
    snaps = await list_snapshots(report_id)
    if not snaps:
        raise HTTPException(404, "No snapshots available for diff")

    snaps_sorted = sorted(snaps, key=lambda s: s["when"])
    pairs = []
    if len(snaps_sorted) >= 2:
        pairs.append(
            (
                snaps_sorted[0],
                snaps_sorted[-1],
                "Historical change (first vs last Wayback)",
            )
        )
    live = next((s for s in snaps_sorted if s["source"] == "live"), None)
    last_wb = next(
        (s for s in reversed(snaps_sorted) if s["source"] == "wayback"),
        None,
    )
    if live and last_wb:
        pairs.append((last_wb, live, "Recent change (last Wayback vs Live)"))

    diffs = [
        {
            "label": label,
            "from_when": a["when"],
            "to_when": b["when"],
            "html": diff_texts_html(a["text"], b["text"]),
            "stats": diff_change_ratio(a["text"], b["text"]),
        }
        for a, b, label in pairs
    ]

    summary = summarize_changes(
        url=url,
        pairs=[
            {
                "label": d["label"],
                "from_when": d["from_when"],
                "to_when": d["to_when"],
            }
            for d in diffs
        ],
        from_text=snaps_sorted[0]["text"],
        to_text=(live["text"] if live else snaps_sorted[-1]["text"]),
        provider=settings.summary_provider,
        llm_base_url=settings.llm_base_url,
        ua=settings.user_agent,
    )
    # Build snapshot link helpers

    def view_url_for(source: str, when: str, url: str) -> str:
        if source == "wayback":
            ts = when.replace("-", "").replace(":", "").replace(" ", "")
            return f"https://web.archive.org/web/{ts}/{url}"
        if source == "live":
            return url
        return ""

    snaps_out = [
        {
            "id": s.get("id"),
            "source": s["source"],
            "when": s["when"],
            "url": s["url"],
            "title": s.get("title"),
            "view_url": view_url_for(s["source"], s["when"], s["url"]),
            "report_url": f"/snapshot/{s.get('id')}" if s.get("id") else "",
        }
        for s in snaps_sorted
    ]

    # 5) Gap notices (UTC, 90+ days threshold)
    GAP_DAYS = 90
    notices = []
    # earliest and latest Wayback (ignore live)
    earliest_wb = next((s for s in snaps_sorted if s["source"] == "wayback"), None)
    latest_wb = next(
        (s for s in reversed(snaps_sorted) if s["source"] == "wayback"),
        None,
    )
    try:
        if earliest_wb and since_dt:
            wb_dt = datetime.fromisoformat(earliest_wb["when"])  # naive UTC
            delta = (wb_dt - since_dt).days
            if delta > GAP_DAYS:
                msg = (
                    "Earliest Wayback archive is {} ({} days after "
                    "requested start {})."
                ).format(
                    wb_dt.date().isoformat(),
                    delta,
                    since_dt.date().isoformat(),
                )
                notices.append(msg)
        if latest_wb and until_dt:
            wb_dt = datetime.fromisoformat(latest_wb["when"])  # naive UTC
            delta = (until_dt - wb_dt).days
            if delta > GAP_DAYS:
                msg = (
                    "Latest Wayback archive is {} ({} days before " "requested end {})."
                ).format(
                    wb_dt.date().isoformat(),
                    delta,
                    until_dt.date().isoformat(),
                )
                notices.append(msg)
    except Exception:
        # best-effort; do not fail diff if parsing notices fails
        pass

    # Overall ratio from first->last pair if available, else 0
    overall_ratio = diffs[0]["stats"]["ratio"] if diffs else 0.0

    return {
        "report_id": report_id,
        "pairs": [d["label"] for d in diffs],
        "summary": summary,
        "snapshots": snaps_out,
        "notices": notices,
        "change_ratio": overall_ratio,
    }


def _normalize_int(value: Optional[str], default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


@app.post("/wizard")
async def wizard_submit(
    url: str = Form(...),
    since: Optional[str] = Form(None),
    until: Optional[str] = Form(None),
    snapshots: Optional[str] = Form(None),
    style: Optional[str] = Form(None),
):
    # If style == 'llm', we still pass through to the same engine. The actual
    # LLM is used inside summarize_changes based on settings.
    req = DiffRequest(
        url=url,  # FastAPI validates as HttpUrl
        since=since or None,
        until=until or None,
        snapshots=_normalize_int(snapshots, 3),
    )
    try:
        result = await make_diff(req)
        report_id = result["report_id"]
        # carry the chosen summary style to the report page (optional override)
        suffix = f"?style={style}" if style in {"llm", "rule"} else ""
        return RedirectResponse(
            url=f"/report/{report_id}{suffix}",
            status_code=303,
        )
    except HTTPException as ex:
        if ex.status_code == 404:
            template = env.get_template("error.html")
            msg = (
                "No snapshots were available to compare. The page may not be "
                "archived for the selected dates, or access may be restricted."
            )
            return HTMLResponse(template.render(message=msg), status_code=200)
        raise


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def report_view(
    report_id: str,
    style: Optional[str] = Query(default=None),
):
    report = await get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    snaps = await list_snapshots(report_id)
    if not snaps:
        raise HTTPException(404, "No snapshots for report")

    snaps_sorted = sorted(snaps, key=lambda s: s["when"])
    pairs = []
    if len(snaps_sorted) >= 2:
        pairs.append(
            (
                snaps_sorted[0],
                snaps_sorted[-1],
                "Historical change (first vs last Wayback)",
            )
        )
    live = next((s for s in snaps_sorted if s["source"] == "live"), None)
    last_wb = next(
        (s for s in reversed(snaps_sorted) if s["source"] == "wayback"),
        None,
    )
    if live and last_wb:
        pairs.append((last_wb, live, "Recent change (last Wayback vs Live)"))

    diffs = [
        {
            "label": label,
            "from_when": a["when"],
            "to_when": b["when"],
            "html": diff_texts_html(a["text"], b["text"]),
        }
        for a, b, label in pairs
    ]

    # allow optional override of summary provider via ?style=llm|rule
    provider = settings.summary_provider
    if style in {"llm", "rule"}:
        provider = style

    summary = summarize_changes(
        url=report["url"],
        pairs=[
            {
                "label": d["label"],
                "from_when": d["from_when"],
                "to_when": d["to_when"],
            }
            for d in diffs
        ],
        from_text=snaps_sorted[0]["text"],
        to_text=(live["text"] if live else snaps_sorted[-1]["text"]),
        provider=provider,
        llm_base_url=settings.llm_base_url,
        ua=settings.user_agent,
    )

    template = env.get_template("report.html")
    html = template.render(
        url=report["url"],
        created_at=report["created_at"],
        diffs=diffs,
        summary=summary,
    )
    return HTMLResponse(content=html)


@app.get("/snapshot/{snapshot_id}", response_class=HTMLResponse)
async def snapshot_view(snapshot_id: int):
    snap = await get_snapshot_html(snapshot_id)
    if not snap:
        raise HTTPException(404, "Snapshot not found")
    # To avoid executing arbitrary scripts from stored snapshots when a
    # user opens the snapshot in their browser, serve the captured HTML
    # inside a sandboxed iframe. We encode the HTML into srcdoc to keep
    # the snapshot self-contained while preventing script execution.
    raw_body = snap.get("html") or ("<em>No HTML captured for this snapshot.</em>")
    import base64

    b64 = base64.b64encode(raw_body.encode("utf-8")).decode("ascii")
    title = snap.get("title") or "Snapshot"
    head = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<meta name=referrer content=no-referrer></head>"
    )
    body_start = "<body style='margin:0;'>"
    # Use data URL in the iframe src; keep sandbox without 'allow-scripts'
    iframe = (
        "<iframe sandbox='allow-forms' style='border:0;"
        "width:100vw;height:100vh;'"
        f' src="data:text/html;charset=utf-8;base64,{b64}"></iframe>'
    )
    wrapper = head + body_start + iframe + "</body></html>"
    return HTMLResponse(wrapper)
