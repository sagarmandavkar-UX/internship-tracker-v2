# Internship Tracker v2

A Streamlit application for tracking internship and new-grad applications, deadlines, follow-ups, interview prep, recruiter context, resume versions, analytics, exports, and optional OpenAI assistance. Each person signs in to see only their own records through the app.

![CI](https://github.com/sagarmandavkar-UX/internship-tracker-v2/actions/workflows/smoke-test.yml/badge.svg)

## Features

- Sign-up and login with salted PBKDF2-SHA256 password hashes
- Per-user application data and ownership checks
- Add, edit, search, filter, update, and delete applications
- Application status history
- Priority, source, recruiter, compensation, resume version, and next-action tracking
- Automatically created deadline and follow-up reminders, plus manual tasks and a dashboard of items due today or overdue
- Interview question bank and company notes
- Dashboard and funnel analytics that preserve stages reached after later status changes
- Local resume/job-description keyword comparison, labeled as keyword coverage
- Optional AI job-description summaries and cover-letter drafts
- Clearly labeled local fallback when no OpenAI API key is configured or a request fails
- Saved analyses attached to the owner's application
- CSV export
- Dark mode preference
- SQLite foreign-key enforcement and cascading cleanup

## Tech

- Python 3.10+
- Streamlit
- SQLite
- OpenAI Python SDK, used only when an API key is configured

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

Open the local address Streamlit prints, usually `http://localhost:8501`. Create an account, add an application, set a deadline or follow-up, and open Analytics or AI Tools. The app creates `internships.db` in the repository directory. Database files are excluded from Git by `.gitignore`.

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

AI calls use `store=False`. If a key is configured, clicking Summarize or Generate cover letter sends the text you pasted to OpenAI. Generated outputs are saved in the local SQLite database with the associated user/application. Raw resume and job-description inputs are not saved in the `ai_results` table. Review the service provider's data policies before submitting personal text.

Without an API key, job summaries use a local term scan, resume matching uses local keyword coverage, and cover letters use a basic local template. The UI labels the source; a keyword score is not an ATS score or hiring prediction.

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
tests/                     App startup, owner isolation, funnel, reminder, and AI fallback tests
requirements.txt           Python dependencies
.env.example               Environment-variable template
.gitignore                 Local DB, secrets, virtualenv and editor ignores
```

## Test

```bash
python smoke_test_tracker.py
python -m pytest -q tests
```

GitHub Actions installs the pinned dependencies, compiles the code, and runs both test suites on Python 3.10, 3.11, and 3.12. The tests cover account authentication, application creation, reminders, status history, cross-user isolation, funnel rates, local and mocked AI paths, a Streamlit sign-up flow, foreign-key enforcement, and cascade deletion. Live OpenAI requests are not part of CI.

## Security notes

- Passwords are salted and hashed, never stored as plaintext.
- Application, reminder, note, question, and AI-result operations are scoped to the signed-in user in the app.
- `.env`, Streamlit secrets, and local SQLite data are excluded from Git.
- OpenAI requests use `store=False`.
- Reminders appear inside the app; it does not send emails or operating-system notifications in the background.
- The SQLite database is not encrypted at rest. People who can read the database file on the host can read its application data. This is a local or small single-instance demo, not a production multi-tenant service. A public deployment needs managed authentication and storage, password reset, login rate limiting, HTTPS, backups, and a production database.
