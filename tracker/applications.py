from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .db import connect, now_iso
from .models import Internship, PRIORITIES, STATUSES


def _row_to_internship(row) -> Internship:
    return Internship(**{name: row[name] for name in Internship.__dataclass_fields__})


def list_internships(user_id: int) -> list[Internship]:
    with connect() as conn:
        rows = conn.execute(
            """select * from internships where user_id=? order by
            case priority when 'High' then 1 when 'Medium' then 2 else 3 end,
            case when deadline is null then 1 else 0 end, deadline, updated_at desc""",
            (user_id,),
        ).fetchall()
    return [_row_to_internship(row) for row in rows]


def get_internship(user_id: int, internship_id: int) -> Internship | None:
    with connect() as conn:
        row = conn.execute("select * from internships where id=? and user_id=?", (internship_id, user_id)).fetchone()
    return _row_to_internship(row) if row else None


def log_activity(conn, user_id: int, action: str, internship_id: int | None, details: str = "") -> None:
    conn.execute(
        "insert into activity_log(user_id,internship_id,action,details,created_at) values(?,?,?,?,?)",
        (user_id, internship_id, action, details, now_iso()),
    )


def _sync_auto_reminder(conn, internship_id: int, kind: str, when: str | None, note: str) -> None:
    row = conn.execute(
        "select id,reminder_date,completed from reminders where internship_id=? and reminder_type=? and is_auto=1",
        (internship_id, kind),
    ).fetchone()
    if when:
        if row:
            completed = row["completed"] if row["reminder_date"] == when else 0
            conn.execute(
                "update reminders set reminder_date=?,notes=?,completed=? where id=?",
                (when, note, completed, row["id"]),
            )
        else:
            conn.execute(
                "insert into reminders(internship_id,reminder_type,reminder_date,completed,notes,is_auto,created_at) values(?,?,?,0,?,1,?)",
                (internship_id, kind, when, note, now_iso()),
            )
    elif row:
        conn.execute("delete from reminders where id=?", (row["id"],))


def validate_payload(data: dict[str, Any]) -> None:
    if not data.get("company_name", "").strip() or not data.get("role_title", "").strip():
        raise ValueError("Company and role are required.")
    if data.get("status") not in STATUSES or data.get("priority") not in PRIORITIES:
        raise ValueError("Invalid status or priority.")
    link = data.get("application_link")
    if link:
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Application link must be a valid HTTP/HTTPS URL.")


def save_internship(user_id: int, data: dict[str, Any], internship_id: int | None = None) -> int:
    validate_payload(data)
    with connect() as conn:
        if internship_id is None:
            cur = conn.execute(
                """insert into internships(
                    user_id,company_name,role_title,location,application_link,deadline,date_applied,status,notes,
                    recruiter_name,recruiter_contact,salary,source,priority,next_action,resume_version,created_at,updated_at
                ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user_id, data["company_name"].strip(), data["role_title"].strip(), data.get("location"),
                    data.get("application_link"), data.get("deadline"), data.get("date_applied"), data["status"],
                    data.get("notes"), data.get("recruiter_name"), data.get("recruiter_contact"), data.get("salary"),
                    data.get("source"), data["priority"], data.get("next_action"), data.get("resume_version"),
                    now_iso(), now_iso(),
                ),
            )
            internship_id = int(cur.lastrowid)
            conn.execute(
                "insert into status_history(internship_id,old_status,new_status,changed_at) values(?,?,?,?)",
                (internship_id, None, data["status"], now_iso()),
            )
            log_activity(conn, user_id, "Added internship", internship_id, f"{data['company_name']} - {data['role_title']}")
        else:
            old = conn.execute("select * from internships where id=? and user_id=?", (internship_id, user_id)).fetchone()
            if not old:
                raise PermissionError("Internship not found.")
            conn.execute(
                """update internships set
                    company_name=?,role_title=?,location=?,application_link=?,deadline=?,date_applied=?,status=?,notes=?,
                    recruiter_name=?,recruiter_contact=?,salary=?,source=?,priority=?,next_action=?,resume_version=?,updated_at=?
                    where id=? and user_id=?""",
                (
                    data["company_name"].strip(), data["role_title"].strip(), data.get("location"), data.get("application_link"),
                    data.get("deadline"), data.get("date_applied"), data["status"], data.get("notes"), data.get("recruiter_name"),
                    data.get("recruiter_contact"), data.get("salary"), data.get("source"), data["priority"], data.get("next_action"),
                    data.get("resume_version"), now_iso(), internship_id, user_id,
                ),
            )
            if old["status"] != data["status"]:
                conn.execute(
                    "insert into status_history(internship_id,old_status,new_status,changed_at) values(?,?,?,?)",
                    (internship_id, old["status"], data["status"], now_iso()),
                )
            log_activity(conn, user_id, "Updated internship", internship_id, f"{data['company_name']} - {data['role_title']}")
        _sync_auto_reminder(conn, internship_id, "Deadline", data.get("deadline"), "Application deadline")
        _sync_auto_reminder(conn, internship_id, "Follow-up", data.get("follow_up_date"), "Follow-up reminder")
        conn.commit()
    return internship_id


def update_status(user_id: int, internship_id: int, status: str) -> bool:
    if status not in STATUSES:
        return False
    with connect() as conn:
        row = conn.execute("select status from internships where id=? and user_id=?", (internship_id, user_id)).fetchone()
        if not row:
            return False
        if row["status"] == status:
            return True
        conn.execute("update internships set status=?,updated_at=? where id=? and user_id=?", (status, now_iso(), internship_id, user_id))
        conn.execute(
            "insert into status_history(internship_id,old_status,new_status,changed_at) values(?,?,?,?)",
            (internship_id, row["status"], status, now_iso()),
        )
        log_activity(conn, user_id, "Updated status", internship_id, f"{row['status']} -> {status}")
        conn.commit()
    return True


def delete_internship(user_id: int, internship_id: int) -> bool:
    with connect() as conn:
        row = conn.execute("select company_name,role_title from internships where id=? and user_id=?", (internship_id, user_id)).fetchone()
        if not row:
            return False
        conn.execute("delete from internships where id=? and user_id=?", (internship_id, user_id))
        log_activity(conn, user_id, "Deleted internship", None, f"{row['company_name']} - {row['role_title']}")
        conn.commit()
    return True


def status_history(user_id: int, internship_id: int):
    with connect() as conn:
        return conn.execute(
            "select h.* from status_history h join internships i on i.id=h.internship_id where h.internship_id=? and i.user_id=? order by h.changed_at",
            (internship_id, user_id),
        ).fetchall()


def activity(user_id: int, limit: int = 10):
    with connect() as conn:
        return conn.execute("select * from activity_log where user_id=? order by created_at desc limit ?", (user_id, limit)).fetchall()


def metrics(user_id: int) -> dict[str, int]:
    items = list_internships(user_id)
    sent = [x for x in items if x.status != "Wishlist" or x.date_applied]
    interviews = [x for x in sent if x.status in {"Interview", "Final Round", "Offer", "Accepted"}]
    offers = [x for x in sent if x.status in {"Offer", "Accepted"}]
    responses = [x for x in sent if x.status in {"Assessment", "Interview", "Final Round", "Rejected", "Offer", "Accepted"}]
    return {
        "tracked": len(items),
        "sent": len(sent),
        "active": sum(x.status in {"Applied", "Assessment", "Interview", "Final Round", "Offer"} for x in items),
        "interview_rate": round(100 * len(interviews) / len(sent)) if sent else 0,
        "offer_rate": round(100 * len(offers) / len(sent)) if sent else 0,
        "response_rate": round(100 * len(responses) / len(sent)) if sent else 0,
    }
