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
    client = _client()
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
            data = json.loads(response.output_text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    skills = [s for s in ["product", "sql", "python", "analytics", "a/b testing", "figma", "machine learning", "leadership"] if s in job_description.lower()]
    return {"summary": "Local fallback summary based on terms in the posting.", "key_skills": skills, "deadline": "Not detected"}


def resume_match(resume: str, job_description: str) -> dict[str, Any]:
    def tokens(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9+.-]+", text.lower()) if len(t) > 2}
    r, j = tokens(resume), tokens(job_description)
    overlap = sorted(r & j)
    score = round(100 * len(overlap) / max(1, len(j)))
    return {"score": min(score, 95), "matching_terms": overlap[:15], "missing_terms": sorted(j-r)[:15]}


def cover_letter(company: str, role: str, resume: str, job_description: str, name: str) -> str:
    client = _client()
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
                return response.output_text.strip()
        except Exception:
            pass
    return f"Dear {company} hiring team,\n\nI am applying for the {role} position and would welcome the opportunity to contribute my experience and problem-solving skills.\n\nBest,\n{name}"


def save_result(user_id: int, internship_id: int, prompt_type: str, result: dict[str, Any]) -> None:
    with connect() as conn:
        if not conn.execute("select 1 from internships where id=? and user_id=?", (internship_id, user_id)).fetchone():
            raise PermissionError("Internship not found")
        conn.execute(
            "insert into ai_results(user_id,internship_id,prompt_type,output_json,created_at) values(?,?,?,?,?)",
            (user_id, internship_id, prompt_type, json.dumps(result, ensure_ascii=False), now_iso()),
        )
        conn.commit()
