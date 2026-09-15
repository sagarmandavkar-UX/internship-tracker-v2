# Internship Tracker v2

A Streamlit application for tracking internship and new-grad applications, deadlines, follow-ups, interview prep, recruiter context, resume versions, analytics, exports, and optional OpenAI assistance.

## Features

- Secure sign-up and login with salted PBKDF2-SHA256 password hashes
- Per-user application data and ownership checks
- Add, edit, search, filter, update, and delete applications
- Application status history
- Priority, source, recruiter, compensation, resume version, and next-action tracking
- Deadline and follow-up reminders plus manual tasks
- Interview question bank and company notes
- Dashboard and pipeline analytics
- Resume/job-description match helper
- Job-description summary helper
- Cover-letter generator
- Local fallback behavior when no OpenAI API key is configured
- CSV export
- Dark mode preference
- SQLite foreign-key enforcement and cascading cleanup

## Tech

- Python 3.10+
- Streamlit
- SQLite
- OpenAI Python SDK, optional

## Install

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

## Run

```bash
streamlit run internship_tracker_v2.py
```

The app creates `internships.db` in the repository directory. That file is excluded from Git by `.gitignore`.

To use a different database path:

```bash
export INTERNSHIP_TRACKER_DB=/absolute/path/to/internships.db
```

## Optional OpenAI features

Set your API key in the environment. Never commit the key to GitHub.

```bash
export OPENAI_API_KEY="your_key_here"
```

Optional model override:

```bash
export OPENAI_MODEL="gpt-4.1-mini"
```

AI calls use `store=False`. Generated outputs are saved locally with the associated user/application, while raw resume and job-description text is not stored in the `ai_results` table.

Without an API key, job summaries and resume matching use local fallback logic, and cover letters use a basic local template.

## Repository layout

```text
internship_tracker_v2.py   Streamlit UI and routing
tracker/
  __init__.py
  db.py                    SQLite schema and connection setup
  models.py                Shared models and constants
  auth.py                  Authentication and profile service
  applications.py          Application CRUD, status history, analytics
  extras.py                Reminders, interview prep, notes, CSV export
  ai.py                    Optional OpenAI and local AI helpers
smoke_test_tracker.py      Core data/security smoke tests
requirements.txt           Python dependencies
.env.example               Environment-variable template
.gitignore                 Local DB, secrets, virtualenv and editor ignores
```

## Test

```bash
python smoke_test_tracker.py
```

The smoke test covers account authentication, application creation, automatic and manual reminders, status history, cross-user isolation, foreign-key enforcement, and cascade deletion.

## Security notes

- Passwords are salted and hashed, never stored as plaintext.
- Application, reminder, note, question, and AI-result operations are scoped to the authenticated user.
- `.env`, Streamlit secrets, and local SQLite data are excluded from Git.
- OpenAI requests use `store=False`.
- This project is suitable for a personal portfolio demo or small single-instance deployment. For a public multi-instance service, move authentication and persistence to managed infrastructure, add password reset/email verification, server-side rate limiting, backups, and a production database such as PostgreSQL.
