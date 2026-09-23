from __future__ import annotations

import csv
import io
from dataclasses import asdict
from datetime import date

from .applications import list_internships, log_activity
from .db import connect, now_iso
from .models import Internship, QUESTION_TYPES, REMINDER_TYPES


def list_reminders(user_id: int, include_completed: bool = True):
    clause = "" if include_completed else "and r.completed=0"
    with connect() as conn:
        return conn.execute(
            f"select r.*,i.company_name,i.role_title from reminders r join internships i on i.id=r.internship_id where i.user_id=? {clause} order by r.completed,r.reminder_date",
            (user_id,),
        ).fetchall()


def add_reminder(user_id: int, internship_id: int, kind: str, when: str, notes: str) -> bool:
    if kind not in REMINDER_TYPES:
        return False
    try:
        date.fromisoformat(when)
    except (TypeError, ValueError):
        return False
    with connect() as conn:
        if not conn.execute("select 1 from internships where id=? and user_id=?", (internship_id, user_id)).fetchone():
            return False
        conn.execute(
            "insert into reminders(internship_id,reminder_type,reminder_date,completed,notes,is_auto,created_at) values(?,?,?,0,?,0,?)",
            (internship_id, kind, when, notes.strip(), now_iso()),
        )
        log_activity(conn, user_id, "Added reminder", internship_id, f"{kind} on {when}")
        conn.commit()
    return True


def toggle_reminder(user_id: int, reminder_id: int, completed: bool) -> bool:
    with connect() as conn:
        row = conn.execute(
            "select r.id from reminders r join internships i on i.id=r.internship_id where r.id=? and i.user_id=?",
            (reminder_id, user_id),
        ).fetchone()
        if not row:
            return False
        conn.execute("update reminders set completed=? where id=?", (int(completed), reminder_id))
        conn.commit()
    return True


def delete_reminder(user_id: int, reminder_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            "select r.id from reminders r join internships i on i.id=r.internship_id where r.id=? and i.user_id=?",
            (reminder_id, user_id),
        ).fetchone()
        if not row:
            return False
        conn.execute("delete from reminders where id=?", (reminder_id,))
        conn.commit()
    return True


def list_questions(user_id: int, internship_id: int):
    with connect() as conn:
        return conn.execute(
            "select q.* from interview_questions q join internships i on i.id=q.internship_id where q.internship_id=? and i.user_id=? order by q.created_at desc",
            (internship_id, user_id),
        ).fetchall()


def add_question(user_id: int, internship_id: int, kind: str, question: str, answer: str) -> bool:
    if kind not in QUESTION_TYPES or not question.strip():
        return False
    with connect() as conn:
        if not conn.execute("select 1 from internships where id=? and user_id=?", (internship_id, user_id)).fetchone():
            return False
        conn.execute(
            "insert into interview_questions(internship_id,question_type,question_text,answer_notes,created_at) values(?,?,?,?,?)",
            (internship_id, kind, question.strip(), answer.strip(), now_iso()),
        )
        conn.commit()
    return True


def list_notes(user_id: int, internship_id: int):
    with connect() as conn:
        return conn.execute(
            "select n.* from company_notes n join internships i on i.id=n.internship_id where n.internship_id=? and i.user_id=? order by n.created_at desc",
            (internship_id, user_id),
        ).fetchall()


def add_note(user_id: int, internship_id: int, text: str) -> bool:
    if not text.strip():
        return False
    with connect() as conn:
        if not conn.execute("select 1 from internships where id=? and user_id=?", (internship_id, user_id)).fetchone():
            return False
        conn.execute("insert into company_notes(internship_id,note_text,created_at) values(?,?,?)", (internship_id, text.strip(), now_iso()))
        conn.commit()
    return True


def export_csv(user_id: int) -> bytes:
    fields = [name for name in Internship.__dataclass_fields__ if name not in {"id", "user_id", "created_at", "updated_at"}]
    rows = []
    for item in list_internships(user_id):
        row = asdict(item)
        for key in ("id", "user_id", "created_at", "updated_at"):
            row.pop(key, None)
        # Prevent spreadsheet programs from interpreting user-entered text as formulas.
        rows.append({key: "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value for key, value in row.items()})
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")
