from __future__ import annotations

from dataclasses import dataclass

STATUSES = ["Wishlist", "Applied", "Assessment", "Interview", "Final Round", "Rejected", "Offer", "Accepted"]
PRIORITIES = ["Low", "Medium", "High"]
REMINDER_TYPES = ["Deadline", "Follow-up", "Interview", "Networking", "Task"]
QUESTION_TYPES = ["Behavioral", "Technical", "PM", "Case", "AI Generated"]


@dataclass
class User:
    id: int
    email: str
    created_at: str


@dataclass
class Internship:
    id: int
    user_id: int
    company_name: str
    role_title: str
    location: str | None
    application_link: str | None
    deadline: str | None
    date_applied: str | None
    status: str
    notes: str | None
    recruiter_name: str | None
    recruiter_contact: str | None
    salary: str | None
    source: str | None
    priority: str
    next_action: str | None
    resume_version: str | None
    created_at: str
    updated_at: str
