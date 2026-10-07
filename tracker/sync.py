from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from typing import Any, Iterable

from .db import connect, now_iso
from .models import STATUSES

STATUS_ALIASES = {
    "wishlist": "Wishlist",
    "applied": "Applied",
    "warm": "Warm",
    "assessment": "Assessment",
    "interview": "Interview",
    "interviewing": "Interview",
    "final round": "Final Round",
    "final": "Final Round",
    "rejected": "Rejected",
    "offer": "Offer",
    "accepted": "Accepted",
}

PROGRESS = {
    "Wishlist": 0,
    "Applied": 1,
    "Warm": 2,
    "Assessment": 3,
    "Interview": 4,
    "Final Round": 5,
    "Offer": 6,
    "Accepted": 7,
}

_TRAILING_ROLE_CODE = re.compile(
    r"\s*(?:\[(?=[A-Z0-9_-]*\d)[A-Z0-9_-]{3,}\]|\((?:req(?:uisition)?\s*)?#?(?=[A-Z0-9_-]*\d)[A-Z0-9_-]{3,}\)|[-–—]\s*(?:req(?:uisition)?\s*)?#?(?=[A-Z0-9_-]*\d)[A-Z0-9_-]{3,})\s*$",
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _key(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _role_key(value: str) -> str:
    return _key(_TRAILING_ROLE_CODE.sub("", value))


def _iso_date(value: Any) -> str | None:
    text = _clean(value)
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Invalid date: {text}. Use YYYY-MM-DD or MM/DD/YYYY.")


def _status(value: Any) -> str:
    status = STATUS_ALIASES.get(_key(_clean(value)))
    if not status or status not in STATUSES:
        raise ValueError(f"Unsupported status: {_clean(value) or '(blank)'}.")
    return status


def _note_with_date(existing: str | None, incoming: str, event_date: str | None) -> str | None:
    incoming = incoming.strip()
    if not incoming:
        return existing
    current = (existing or "").strip()
    if incoming.casefold() in current.casefold():
        return existing
    stamp_date = date.fromisoformat(event_date) if event_date else date.today()
    addition = f"[{stamp_date:%m/%d}] {incoming}"
    return f"{current} | {addition}" if current else addition


def _is_true(value: Any) -> bool:
    return value is True or _key(_clean(value)) in {"1", "true", "yes", "y"}


def _next_status(
    current: str,
    incoming: str,
    current_date: str | None,
    incoming_date: str | None,
    event_date: str | None = None,
    changed: bool = False,
) -> tuple[str, bool]:
    if current == incoming:
        return current, False
    if current == "Accepted":
        return current, False
    if current == "Rejected":
        if incoming == "Applied" and incoming_date and (not current_date or incoming_date > current_date):
            return "Applied", True
        return current, False
    if current == "Offer" and incoming == "Rejected":
        return current, False
    if incoming == "Rejected":
        return "Rejected", True
    if incoming == "Warm":
        return ("Warm", True) if current in {"Wishlist", "Applied"} else (current, False)
    if current == "Warm" and incoming in {"Wishlist", "Applied"}:
        return current, False
    if current == "Warm" and incoming in {"Assessment", "Interview", "Final Round", "Offer"}:
        if not changed and (not event_date or (current_date and event_date <= current_date)):
            return current, False
    return (incoming, True) if PROGRESS.get(incoming, -1) > PROGRESS.get(current, -1) else (current, False)


def parse_sync_file(content: bytes, filename: str) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    if filename.lower().endswith(".json"):
        payload = json.loads(text)
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("JSON must contain an array of applications or an object with a rows array.")
        return [dict(row) for row in rows if isinstance(row, dict)]
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def sync_applications(user_id: int, rows: Iterable[dict[str, Any]], source: str = "Imported file") -> dict[str, Any]:
    prepared = list(rows)
    added = updated = skipped = 0
    change_summaries: list[str] = []
    timestamp = now_iso()

    with connect() as conn:
        run = conn.execute(
            "insert into sync_runs(user_id,source,created_at) values(?,?,?)",
            (user_id, source.strip() or "Imported file", timestamp),
        )
        run_id = int(run.lastrowid)
        existing_rows = conn.execute("select * from internships where user_id=?", (user_id,)).fetchall()
        existing = {(_key(row["company_name"]), _role_key(row["role_title"])): row for row in existing_rows}

        for raw in prepared:
            company = _clean(raw.get("company") or raw.get("company_name"))
            role = _clean(raw.get("role") or raw.get("role_title"))
            try:
                if not company or not role:
                    raise ValueError("Company and role are required.")
                incoming_status = _status(raw.get("status") or "Applied")
                applied_date = _iso_date(raw.get("date") or raw.get("date_applied"))
                event_date = _iso_date(raw.get("event_date") or raw.get("changed_at"))
            except ValueError:
                skipped += 1
                continue

            note = _clean(raw.get("notes"))
            changed = _is_true(raw.get("changed"))
            key = (_key(company), _role_key(role))
            current = existing.get(key)
            if current is None:
                cur = conn.execute(
                    """insert into internships(
                        user_id,company_name,role_title,date_applied,status,notes,source,priority,created_at,updated_at
                    ) values(?,?,?,?,?,?,?,?,?,?)""",
                    (user_id, company, role, applied_date, incoming_status, _note_with_date(None, note, event_date or applied_date), source, "Medium", timestamp, timestamp),
                )
                internship_id = int(cur.lastrowid)
                conn.execute(
                    "insert into status_history(internship_id,old_status,new_status,changed_at) values(?,?,?,?)",
                    (internship_id, None, incoming_status, timestamp),
                )
                conn.execute(
                    "insert into activity_log(user_id,internship_id,action,details,created_at) values(?,?,?,?,?)",
                    (user_id, internship_id, "Synced application", f"Added {company} - {role}", timestamp),
                )
                summary = f"{company} — added {role} as {incoming_status}"
                existing[key] = conn.execute("select * from internships where id=?", (internship_id,)).fetchone()
                added += 1
            else:
                internship_id = int(current["id"])
                display_company = current["company_name"]
                display_role = current["role_title"]
                new_status, status_changed = _next_status(
                    current["status"], incoming_status, current["date_applied"], applied_date, event_date, changed
                )
                new_notes = _note_with_date(current["notes"], note, event_date or applied_date)
                re_applied = current["status"] == "Rejected" and new_status == "Applied"
                new_date = applied_date if re_applied else current["date_applied"] or applied_date
                if re_applied:
                    new_notes = _note_with_date(new_notes, "Re-applied", event_date or applied_date)
                notes_changed = new_notes != current["notes"]
                date_changed = new_date != current["date_applied"]
                if not (status_changed or notes_changed or date_changed):
                    skipped += 1
                    continue
                conn.execute(
                    "update internships set status=?,notes=?,date_applied=?,updated_at=? where id=? and user_id=?",
                    (new_status, new_notes, new_date, timestamp, internship_id, user_id),
                )
                if status_changed:
                    conn.execute(
                        "insert into status_history(internship_id,old_status,new_status,changed_at) values(?,?,?,?)",
                        (internship_id, current["status"], new_status, timestamp),
                    )
                detail = f"{current['status']} → {new_status}" if status_changed else "notes updated"
                conn.execute(
                    "insert into activity_log(user_id,internship_id,action,details,created_at) values(?,?,?,?,?)",
                    (user_id, internship_id, "Synced application", f"{company} - {role}: {detail}", timestamp),
                )
                summary = f"{display_company} — {display_role}: {detail}"
                existing[key] = conn.execute("select * from internships where id=?", (internship_id,)).fetchone()
                updated += 1

            change_summaries.append(summary)
            conn.execute(
                "insert into sync_changes(run_id,internship_id,summary,created_at) values(?,?,?,?)",
                (run_id, internship_id, summary, timestamp),
            )

        conn.execute(
            "update sync_runs set added_count=?,updated_count=?,skipped_count=? where id=? and user_id=?",
            (added, updated, skipped, run_id, user_id),
        )
        conn.commit()

    return {"run_id": run_id, "added": added, "updated": updated, "skipped": skipped, "changes": change_summaries}


def latest_sync(user_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        run = conn.execute("select * from sync_runs where user_id=? order by id desc limit 1", (user_id,)).fetchone()
        if not run:
            return None
        changes = conn.execute("select summary from sync_changes where run_id=? order by id", (run["id"],)).fetchall()
    result = dict(run)
    result["changes"] = [row["summary"] for row in changes]
    return result
