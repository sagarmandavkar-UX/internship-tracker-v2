from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv("INTERNSHIP_TRACKER_DB", Path(__file__).resolve().parent.parent / "internships.db"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma busy_timeout = 5000")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            create table if not exists users (
              id integer primary key autoincrement,
              email text not null unique,
              password_hash text not null,
              created_at text not null
            );
            create table if not exists profiles (
              user_id integer primary key,
              display_name text not null,
              bio text,
              target_role text,
              resume_version text,
              dark_mode integer not null default 0,
              created_at text not null,
              updated_at text not null,
              foreign key(user_id) references users(id) on delete cascade
            );
            create table if not exists internships (
              id integer primary key autoincrement,
              user_id integer not null,
              company_name text not null,
              role_title text not null,
              location text,
              application_link text,
              deadline text,
              date_applied text,
              status text not null,
              notes text,
              recruiter_name text,
              recruiter_contact text,
              salary text,
              source text,
              priority text not null default 'Medium',
              next_action text,
              resume_version text,
              created_at text not null,
              updated_at text not null,
              foreign key(user_id) references users(id) on delete cascade
            );
            create table if not exists reminders (
              id integer primary key autoincrement,
              internship_id integer not null,
              reminder_type text not null,
              reminder_date text not null,
              completed integer not null default 0,
              notes text,
              is_auto integer not null default 0,
              created_at text not null,
              foreign key(internship_id) references internships(id) on delete cascade
            );
            create table if not exists interview_questions (
              id integer primary key autoincrement,
              internship_id integer not null,
              question_type text not null,
              question_text text not null,
              answer_notes text,
              created_at text not null,
              foreign key(internship_id) references internships(id) on delete cascade
            );
            create table if not exists company_notes (
              id integer primary key autoincrement,
              internship_id integer not null,
              note_text text not null,
              created_at text not null,
              foreign key(internship_id) references internships(id) on delete cascade
            );
            create table if not exists activity_log (
              id integer primary key autoincrement,
              user_id integer not null,
              internship_id integer,
              action text not null,
              details text,
              created_at text not null,
              foreign key(user_id) references users(id) on delete cascade,
              foreign key(internship_id) references internships(id) on delete set null
            );
            create table if not exists status_history (
              id integer primary key autoincrement,
              internship_id integer not null,
              old_status text,
              new_status text not null,
              changed_at text not null,
              foreign key(internship_id) references internships(id) on delete cascade
            );
            create table if not exists ai_results (
              id integer primary key autoincrement,
              user_id integer not null,
              internship_id integer,
              prompt_type text not null,
              output_json text not null,
              created_at text not null,
              foreign key(user_id) references users(id) on delete cascade,
              foreign key(internship_id) references internships(id) on delete cascade
            );
            create index if not exists idx_internships_user_status on internships(user_id, status);
            create index if not exists idx_reminders_date on reminders(internship_id, reminder_date);
            create index if not exists idx_status_history on status_history(internship_id, changed_at);
            """
        )
        conn.commit()
