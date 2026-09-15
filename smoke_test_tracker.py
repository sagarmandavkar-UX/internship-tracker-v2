from __future__ import annotations
import os
import tempfile
from pathlib import Path

fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(fd)
os.unlink(db_path)
os.environ['INTERNSHIP_TRACKER_DB'] = db_path

from tracker import db
from tracker.auth import authenticate, create_user
from tracker.applications import delete_internship, get_internship, list_internships, save_internship, status_history, update_status
from tracker.extras import add_reminder, delete_reminder, list_reminders, toggle_reminder

db.DB_PATH = Path(db_path)
db.init_db()

ok, msg, user1_id = create_user('user1@example.com', 'StrongPass123', 'User One')
assert ok, msg
assert user1_id
assert authenticate('user1@example.com', 'StrongPass123') is not None

payload = {
    'company_name': 'Acme', 'role_title': 'Associate Product Manager', 'location': 'Nashville',
    'application_link': 'https://example.com/job', 'deadline': '2026-10-01', 'date_applied': '2026-09-14',
    'status': 'Applied', 'notes': 'Initial application', 'recruiter_name': 'Recruiter',
    'recruiter_contact': 'recruiter@example.com', 'salary': '$100k', 'source': 'Company site',
    'priority': 'High', 'next_action': 'Follow up', 'resume_version': 'PM v2', 'follow_up_date': '2026-09-20'
}
app_id = save_internship(user1_id, payload)
assert len(list_internships(user1_id)) == 1
assert len(list_reminders(user1_id)) == 2
assert add_reminder(user1_id, app_id, 'Task', '2026-09-18', 'Manual reminder')
manual_id = next(r['id'] for r in list_reminders(user1_id) if r['reminder_type'] == 'Task')
assert toggle_reminder(user1_id, manual_id, True)
assert next(r['completed'] for r in list_reminders(user1_id) if r['id'] == manual_id) == 1

assert update_status(user1_id, app_id, 'Assessment')
assert status_history(user1_id, app_id)[-1]['new_status'] == 'Assessment'

ok, msg, user2_id = create_user('user2@example.com', 'AnotherPass456', 'User Two')
assert ok, msg
assert user2_id
assert get_internship(user2_id, app_id) is None
assert add_reminder(user2_id, app_id, 'Task', '2026-09-19', 'Unauthorized') is False
assert delete_reminder(user2_id, manual_id) is False

assert delete_internship(user1_id, app_id)
assert get_internship(user1_id, app_id) is None
assert list_reminders(user1_id) == []

with db.connect() as conn:
    assert conn.execute('pragma foreign_keys').fetchone()[0] == 1

print('All modular Internship Tracker smoke tests passed.')
