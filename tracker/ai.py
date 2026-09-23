from __future__ import annotations

import json
import os
import re
from typing import Any

from .db import connect, now_iso

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


def _client():
    key = os.getenv("OPENAI_API_KEY")
    if not key or OpenAI is None:
        return None
    return OpenAI(api_key=key)


def summarize_job(job_description: str) -> dict[str, Any]:
    if not job_description.strip():
        raise ValueError("Paste a job description before summarizing.")
    client = _client()
    warning = None
    if client:
        try:
            response = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                store=False,
                input=(
                    "Summarize this job posting in concise bullets. Return JSON with keys summary, key_skills, deadline. "
                    "Do not invent facts.\n\n" + job_description[:40000]
                ),
            )
            data = json.loads(response.output_text.strip().removeprefix("```json").removesuffix("```").strip())
            if isinstance(data, dict) and isinstance(data.get("summary"), str) and isinstance(data.get("key_skills"), list):
                return {"source": "OpenAI", "summary": data["summary"], "key_skills": data["key_skills"], "deadline": data.get("deadline") or "Not detected"}
            warning = "AI returned an incomplete summary. Showing the local term scan."
        except Exception:
            warning = "AI analysis was unavailable. Showing the local term scan."
    skills = [s for s in ["product", "sql", "python", "analytics", "a/b testing", "figma", "machine learning", "leadership"] if s in job_description.lower()]
    return {"source": "Local term scan", "summary": "The highlighted terms below appear in the pasted posting.", "key_skills": skills, "deadline": "Not detected", "warning": warning}


def resume_match(resume: str, job_description: str) -> dict[str, Any]:
    if not resume.strip() or not job_description.strip():
        raise ValueError("Paste both a resume and a job description.")
    def tokens(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9+.-]+", text.lower()) if len(t) > 2}
    r, j = tokens(resume), tokens(job_description)
    overlap = sorted(r & j)
    score = round(100 * len(overlap) / max(1, len(j)))
    return {"score": score, "source": "Local keyword coverage", "matching_terms": overlap[:15], "missing_terms": sorted(j-r)[:15]}


def cover_letter(company: str, role: str, resume: str, job_description: str, name: str) -> dict[str, str]:
    if not resume.strip() or not job_description.strip():
        raise ValueError("Paste both a resume and a job description.")
    client = _client()
    warning = ""
    if client:
        try:
            response = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                store=False,
                input=(
                    f"Write a concise cover letter for {name} applying to {company} for {role}. Use only supplied facts. "
                    f"Do not invent metrics or experience.\n\nRESUME:\n{resume[:18000]}\n\nJOB:\n{job_description[:18000]}"
                ),
            )
            if response.output_text.strip():
                return {"text": response.output_text.strip(), "source": "OpenAI"}
            warning = "AI returned an empty draft. Showing a local template."
        except Exception:
            warning = "AI generation was unavailable. Showing a local template."
    return {"text": f"Dear {company} hiring team,\n\nI am applying for the {role} position and would welcome the opportunity to contribute my experience and problem-solving skills.\n\nBest,\n{name}", "source": "Local template", "warning": warning}


def save_result(user_id: int, internship_id: int, prompt_type: str, result: dict[str, Any]) -> None:
    with connect() as conn:
        if not conn.execute("select 1 from internships where id=? and user_id=?", (internship_id, user_id)).fetchone():
            raise PermissionError("Internship not found")
        conn.execute(
            "insert into ai_results(user_id,internship_id,prompt_type,output_json,created_at) values(?,?,?,?,?)",
            (user_id, internship_id, prompt_type, json.dumps(result, ensure_ascii=False), now_iso()),
        )
        conn.commit()


def list_results(user_id: int, internship_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """Return saved analyses for the owner's application only."""
    with connect() as conn:
        rows = conn.execute(
            """select a.prompt_type,a.output_json,a.created_at from ai_results a
               join internships i on i.id=a.internship_id
               where a.user_id=? and i.user_id=? and a.internship_id=?
               order by a.id desc limit ?""",
            (user_id, user_id, internship_id, limit),
        ).fetchall()
    return [{"type": row["prompt_type"], "result": json.loads(row["output_json"]), "created_at": row["created_at"]} for row in rows]
