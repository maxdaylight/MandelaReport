# pyright: reportMissingImports=false
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiosqlite

DB_PATH = "data/mandelareport.sqlite3"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
        )
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT NOT NULL,
            source TEXT NOT NULL,
            "when" TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            text TEXT,
            html TEXT
        )
        """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_snap_report ON " "snapshots(report_id)"
        )
        await db.commit()


async def create_report(report_id: str, url: str):
    # Use a consistent ISO8601 UTC timestamp for created_at so all code
    # compares timestamps using the same format (Python-serialised). The
    # SQLite datetime('now') format differs (no 'T'), which made string
    # comparisons unreliable in purge_old_reports.
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reports (id, url, created_at) VALUES " "(?, ?, ?)",
            (report_id, url, now),
        )
        await db.commit()


async def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, url, created_at FROM reports WHERE id=?", (report_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "url": row[1], "created_at": row[2]}


async def save_snapshot(
    report_id: str,
    source: str,
    when: str,
    url: str,
    title: str,
    text: str,
    html: str,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO snapshots (report_id, source, "when", url, title, text,
                                   html)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (report_id, source, when, url, title, text, html),
        )
        await db.commit()


async def list_snapshots(report_id: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = []
        async with db.execute(
            'SELECT id, source, "when", url, title, text FROM snapshots '
            'WHERE report_id=? ORDER BY "when" ASC',
            (report_id,),
        ) as cur:
            async for r in cur:
                rows.append(
                    {
                        "id": r[0],
                        "source": r[1],
                        "when": r[2],
                        "url": r[3],
                        "title": r[4],
                        "text": r[5],
                    }
                )
        return rows


async def get_snapshot_html(snapshot_id: int) -> Optional[Dict[str, Any]]:
    """Return minimal snapshot info with stored HTML for inline viewing."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            (
                'SELECT id, source, "when", url, title, html '
                "FROM snapshots WHERE id=?"
            ),
            (snapshot_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "source": row[1],
                "when": row[2],
                "url": row[3],
                "title": row[4],
                "html": row[5],
            }


async def purge_old_reports(retention_days: int) -> int:
    """
    Delete reports (and their snapshots) older than the retention window.
    Returns number of reports deleted.
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Find report ids to delete
        ids: List[str] = []
        async with db.execute(
            "SELECT id FROM reports WHERE created_at < ?", (cutoff_iso,)
        ) as cur:
            async for r in cur:
                ids.append(r[0])
        if not ids:
            return 0
        # Delete snapshots then reports
        await db.executemany(
            "DELETE FROM snapshots WHERE report_id = ?", [(i,) for i in ids]
        )
        await db.executemany("DELETE FROM reports WHERE id = ?", [(i,) for i in ids])
        await db.commit()
        return len(ids)


async def vacuum() -> None:
    """Run VACUUM to reclaim space after large deletions."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("VACUUM")
        await db.commit()
