"""User isolation, reminder editing, funnel history, and real UI startup."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from tracker import db
from tracker import ai
from tracker.ai import cover_letter, list_results, resume_match, save_result, summarize_job
from tracker.applications import activity, get_auto_reminder_date, metrics, save_internship, status_history, update_status
from tracker.auth import create_user
from tracker.extras import add_note, add_question, export_csv, list_notes, list_questions, list_reminders


@pytest.fixture
def clean_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "tracker.db")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db.init_db()


def user(email):
    ok, message, user_id = create_user(email, "StrongPass123", "Test User")
    assert ok, message
    return user_id


def application(**changes):
    data = {"company_name": "Acme", "role_title": "APM", "status": "Applied", "priority": "High", "date_applied": date.today().isoformat()}
    return data | changes


def test_edit_preserves_followup_and_authorizes_lookup(clean_db):
    owner, other = user("owner@example.com"), user("other@example.com")
    app_id = save_internship(owner, application(follow_up_date="2026-10-10", deadline="2026-10-08"))
    assert get_auto_reminder_date(owner, app_id, "Follow-up") == "2026-10-10"
    assert get_auto_reminder_date(other, app_id, "Follow-up") is None
    save_internship(owner, application(role_title="PM"), app_id)
    assert get_auto_reminder_date(owner, app_id, "Follow-up") == "2026-10-10"
    assert get_auto_reminder_date(owner, app_id, "Deadline") == "2026-10-08"
    save_internship(owner, application(follow_up_date=None), app_id)
    assert get_auto_reminder_date(owner, app_id, "Follow-up") is None
    assert len(list_reminders(other)) == 0


def test_funnel_retains_prior_interview_after_rejection(clean_db):
    owner, other = user("owner@example.com"), user("other@example.com")
    app_id = save_internship(owner, application())
    assert update_status(owner, app_id, "Interview")
    assert update_status(owner, app_id, "Rejected")
    assert metrics(owner)["interview_rate"] == 100
    assert metrics(owner)["response_rate"] == 100
    assert metrics(other)["sent"] == 0
    assert update_status(other, app_id, "Offer") is False


def test_local_analysis_is_labeled_and_saved_per_user(clean_db):
    owner, other = user("owner@example.com"), user("other@example.com")
    app_id = save_internship(owner, application())
    match = resume_match("Python SQL analytics", "Python analytics leadership")
    summary = summarize_job("We seek Python and SQL analytics experience.")
    letter = cover_letter("Acme", "APM", "Python SQL analytics", "Python and SQL required", "Test User")
    assert match["source"] == "Local keyword coverage"
    assert summary["source"] == "Local term scan"
    assert letter["source"] == "Local template"
    save_result(owner, app_id, "cover_letter", letter)
    assert list_results(owner, app_id)[0]["result"]["text"] == letter["text"]
    assert list_results(other, app_id) == []
    with pytest.raises(PermissionError):
        save_result(other, app_id, "resume_match", match)
    with pytest.raises(ValueError):
        summarize_job("  ")


def test_every_application_surface_is_scoped_to_owner(clean_db):
    owner, other = user("owner@example.com"), user("other@example.com")
    app_id = save_internship(owner, application(notes="Private interview notes", follow_up_date="2026-10-10"))
    assert add_question(owner, app_id, "PM", "Private question", "Private answer")
    assert add_note(owner, app_id, "Private company note")
    assert list_questions(other, app_id) == []
    assert list_notes(other, app_id) == []
    assert list_reminders(other) == []
    assert status_history(other, app_id) == []
    assert activity(other) == []
    assert b"Private interview notes" not in export_csv(other)
    assert b"Private interview notes" in export_csv(owner)


def test_invalid_dates_and_spreadsheet_formulas_are_handled(clean_db):
    owner = user("owner@example.com")
    with pytest.raises(ValueError, match="Deadline"):
        save_internship(owner, application(deadline="2026-02-30"))
    assert export_csv(owner).startswith(b"company_name,role_title,")
    save_internship(owner, application(company_name="=HYPERLINK(\"https://example.com\")"))
    assert b"'=HYPERLINK" in export_csv(owner)


def test_ai_path_and_fallback_are_explicit(clean_db, monkeypatch):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        text = '{"summary":"Apply through the company site","key_skills":["SQL"],"deadline":"Not listed"}' if "JSON" in kwargs["input"] else "Dear hiring team, I have SQL experience."
        return SimpleNamespace(output_text=text)
    monkeypatch.setattr(ai, "_client", lambda: SimpleNamespace(responses=SimpleNamespace(create=create)))
    summary = summarize_job("SQL required")
    letter = cover_letter("Acme", "APM", "SQL analyst", "SQL required", "Test User")
    assert summary["source"] == letter["source"] == "OpenAI"
    assert all(call["store"] is False for call in calls)
    monkeypatch.setattr(ai, "_client", lambda: SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("test outage")))))
    assert summarize_job("SQL required")["warning"]
    assert cover_letter("Acme", "APM", "SQL analyst", "SQL required", "Test User")["source"] == "Local template"


def test_signup_application_and_reminder_in_streamlit(clean_db):
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "internship_tracker_v2.py").run(timeout=20)
    assert not app.exception
    app.text_input[2].input("Test User")
    app.text_input[3].input("ui@example.com")
    app.text_input[4].input("StrongPass123")
    app.button[1].click().run(timeout=20)
    assert not app.exception
    owner = app.session_state["user_id"]

    app.radio[0].set_value("Internships").run(timeout=20)
    app.text_input[0].input("Acme")
    app.text_input[1].input("APM")
    app.date_input[2].set_value(date.today())
    app.button[0].click().run(timeout=20)
    assert not app.exception
    with db.connect() as conn:
        app_id = conn.execute("select id from internships where user_id=?", (owner,)).fetchone()[0]
    assert get_auto_reminder_date(owner, app_id, "Follow-up") == date.today().isoformat()
    assert any(input.value == date.today() for input in app.date_input if input.label == "Follow-up")

    for page in ("Dashboard", "Reminders", "Interview Prep", "Analytics", "AI Tools", "Export"):
        app.radio[0].set_value(page).run(timeout=20)
        assert not app.exception, page
        if page == "AI Tools":
            app.text_area[0].input("Python and SQL analysis")
            app.text_area[1].input("Python and SQL required")
            app.button[0].click().run(timeout=20)
            assert not app.exception
            assert list_results(owner, app_id)[0]["result"]["source"] == "Local keyword coverage"
