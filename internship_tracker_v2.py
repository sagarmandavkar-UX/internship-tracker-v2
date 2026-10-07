from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from tracker.ai import cover_letter, list_results, resume_match, save_result, summarize_job
from tracker.applications import activity, delete_internship, get_auto_reminder_date, list_internships, metrics, save_internship, status_history, update_status
from tracker.auth import authenticate, create_user, get_profile, get_user, update_profile
from tracker.db import init_db
from tracker.extras import add_note, add_question, add_reminder, delete_reminder, export_csv, list_notes, list_questions, list_reminders, toggle_reminder
from tracker.models import PRIORITIES, QUESTION_TYPES, REMINDER_TYPES, STATUSES
from tracker.sync import latest_sync, parse_sync_file, sync_applications

st.set_page_config(page_title="Internship Tracker AI", page_icon="💼", layout="wide")


def theme(dark: bool) -> None:
    bg, card, text, muted, border, accent = (("#0b1020", "#111827", "#f8fafc", "#a8b3c7", "#293548", "#8b7cff") if dark else ("#f8f9fc", "#ffffff", "#111936", "#667085", "#e1e5ee", "#6258e8"))
    st.markdown(f"""
    <style>
      .stApp {{background:{bg}; color:{text};}}
      section[data-testid='stSidebar'] {{background:{card}; border-right:1px solid {border};}}
      section[data-testid='stSidebar'] h1 {{color:{text} !important; font-size:1.45rem;}}
      section[data-testid='stSidebar'] [data-testid='stMarkdownContainer'] p {{color:{muted};}}
      section[data-testid='stSidebar'] [data-testid='stRadio'] label {{padding:.42rem .55rem; border-radius:.5rem;}}
      section[data-testid='stSidebar'] [data-testid='stRadio'] label:has(input:checked) {{background:{'#272342' if dark else '#eeecff'};}}
      section[data-testid='stSidebar'] [data-testid='stRadio'] label:has(input:checked) p {{color:{'#dcd8ff' if dark else '#4d42d6'}; font-weight:650;}}
      .block-container {{padding-top:2.1rem; padding-bottom:3rem; max-width:1500px;}}
      h1 {{letter-spacing:-.035em; color:{text};}}
      h2, h3 {{letter-spacing:-.018em;}}
      div[data-testid='stMetric'] {{background:{card}; border:1px solid {border}; padding:.8rem .9rem; border-radius:.7rem; box-shadow:0 1px 2px rgba(17,25,54,.03);}}
      div[data-testid='stMetric'] label {{color:{muted}; font-size:.79rem;}}
      div[data-testid='stMetricValue'] {{color:{text}; font-weight:700;}}
      div[data-testid='stDataFrame'] {{border:1px solid {border}; border-radius:.65rem; overflow:hidden;}}
      [data-baseweb='input'], [data-baseweb='base-input'], [data-baseweb='input'] > div, [data-baseweb='select'] > div, [data-baseweb='textarea'] > div {{background:{card} !important; border-color:{border} !important; color:{text};}}
      [data-baseweb='input'] input, [data-baseweb='select'] span, [data-baseweb='textarea'] textarea {{color:{text} !important;}}
      .sync-panel {{background:{'#181631' if dark else '#f0efff'}; border:1px solid {'#3a3564' if dark else '#dddbff'}; border-radius:.7rem; padding:.85rem 1rem; margin:.8rem 0 1.2rem;}}
      .sync-panel strong {{color:{'#dcd8ff' if dark else '#332b95'};}}
      .sync-panel p {{margin:.2rem 0; color:{muted}; font-size:.9rem;}}
      .sync-dot {{display:inline-block; width:.48rem; height:.48rem; border-radius:50%; background:{accent}; margin-right:.5rem;}}
      .status-grid {{display:grid; grid-template-columns:repeat(9,minmax(0,1fr)); gap:.55rem; margin:.15rem 0 1.2rem;}}
      .status-tile {{background:{card}; border:1px solid {border}; border-radius:.65rem; padding:.65rem .7rem; min-width:0;}}
      .status-tile span {{display:block; color:{muted}; font-size:.72rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}}
      .status-tile strong {{display:block; color:{text}; font-size:1.25rem; line-height:1.35;}}
      .status-applied {{background:{'#13243b' if dark else '#edf6ff'};}}
      .status-warm {{background:{'#36251c' if dark else '#fff3e8'};}}
      .status-assessment {{background:{'#352d18' if dark else '#fff8e8'};}}
      .status-interview {{background:{'#262042' if dark else '#f3f0ff'};}}
      .status-final-round {{background:{'#242444' if dark else '#f0f1ff'};}}
      .status-rejected {{background:{'#2b2027' if dark else '#fff0f2'};}}
      .status-offer, .status-accepted {{background:{'#143025' if dark else '#ebfaf2'};}}
      .applications-table-wrap {{border:1px solid {border}; border-radius:.65rem; overflow:auto; background:{card};}}
      .applications-table {{width:100%; border-collapse:collapse; min-width:680px;}}
      .applications-table th {{background:{'#172033' if dark else '#f5f7fb'}; color:{muted}; font-size:.72rem; font-weight:650; text-align:left; padding:.62rem .7rem; border-bottom:1px solid {border}; white-space:nowrap;}}
      .applications-table td {{color:{text}; font-size:.82rem; padding:.65rem .7rem; border-bottom:1px solid {border}; vertical-align:top;}}
      .applications-table tr:last-child td {{border-bottom:0;}}
      .applications-table td:first-child {{font-weight:650;}}
      .applications-table .notes-cell {{color:{muted}; max-width:230px;}}
      .status-pill {{display:inline-block; border-radius:999px; padding:.18rem .52rem; background:{'#262042' if dark else '#f0efff'}; color:{'#dcd8ff' if dark else '#4d42d6'}; font-size:.72rem; font-weight:650; white-space:nowrap;}}
      @media (max-width: 1000px) {{.status-grid {{grid-template-columns:repeat(3,minmax(0,1fr));}}}}
      .small-muted {{color:{muted}; font-size:.86rem;}}
    </style>
    """, unsafe_allow_html=True)


def auth_screen() -> None:
    st.title("Internship Tracker AI")
    st.caption("Track applications, deadlines, interviews, recruiters, resume versions, and AI-assisted prep.")
    login_tab, signup_tab = st.tabs(["Log in", "Create account"])
    with login_tab:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log in", type="primary")
        if submit:
            user = authenticate(email, password)
            if user:
                st.session_state.user_id = user.id
                st.rerun()
            st.error("Invalid email or password.")
    with signup_tab:
        with st.form("signup"):
            name = st.text_input("Display name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            st.caption("Use 10+ characters with uppercase, lowercase, and a number.")
            submit = st.form_submit_button("Create account", type="primary")
        if submit:
            ok, msg, user_id = create_user(email, password, name)
            if ok and user_id:
                st.session_state.user_id = user_id
                st.rerun()
            st.error(msg)


def sidebar(profile) -> str:
    st.sidebar.title("Internship Tracker")
    st.sidebar.caption(profile["target_role"] or "Application workspace")
    return st.sidebar.radio("Navigate", ["Dashboard", "Internships", "Reminders", "Interview Prep", "Analytics", "AI Tools", "Profile", "Export"], label_visibility="collapsed")


def dashboard(user_id: int) -> None:
    st.title("Dashboard")
    st.caption("Your internship search, in one clear view.")
    m = metrics(user_id)
    cols = st.columns(5)
    cols[0].metric("Applications sent", m["sent"])
    cols[1].metric("Active", m["active"])
    cols[2].metric("Interview rate", f"{m['interview_rate']}%")
    cols[3].metric("Offer rate", f"{m['offer_rate']}%")
    cols[4].metric("Response rate", f"{m['response_rate']}%")
    items = list_internships(user_id)
    sync = latest_sync(user_id)
    if sync:
        changes = "".join(f"<p><span class='sync-dot'></span>{escape(change)}</p>" for change in sync["changes"][:4])
        if not changes:
            changes = "<p>No application changes were needed.</p>"
        st.markdown(
            f"<div class='sync-panel'><strong>Changed in last sync</strong>{changes}"
            f"<p>{sync['added_count']} added · {sync['updated_count']} updated · {sync['skipped_count']} unchanged or skipped</p></div>",
            unsafe_allow_html=True,
        )

    st.subheader("Application status overview")
    counts = {status: sum(item.status == status for item in items) for status in STATUSES}
    status_tiles = "".join(
        f"<div class='status-tile status-{status.lower().replace(' ', '-')}'><span>{status}</span><strong>{counts[status]}</strong></div>"
        for status in STATUSES
    )
    st.markdown(f"<div class='status-grid'>{status_tiles}</div>", unsafe_allow_html=True)

    left, right = st.columns([2.2, 1])
    with left:
        st.subheader("Applications")
        search_col, status_col = st.columns([2, 1])
        search = search_col.text_input("Search applications", placeholder="Search companies, roles, or notes…")
        status_filter = status_col.selectbox("Filter by status", ["All statuses"] + STATUSES)
        filtered = []
        for item in items:
            haystack = " ".join([item.company_name, item.role_title, item.notes or "", item.next_action or ""]).casefold()
            if search and search.casefold() not in haystack:
                continue
            if status_filter != "All statuses" and item.status != status_filter:
                continue
            filtered.append(item)
        if filtered:
            rows = "".join(
                "<tr>"
                f"<td>{escape(item.company_name)}</td>"
                f"<td>{escape(item.role_title)}</td>"
                f"<td><span class='status-pill'>{escape(item.status)}</span></td>"
                f"<td>{escape(item.date_applied or '')}</td>"
                f"<td>{escape(item.next_action or '')}</td>"
                f"<td class='notes-cell'>{escape(item.notes or '')}</td>"
                "</tr>"
                for item in filtered
            )
            st.markdown(
                "<div class='applications-table-wrap'><table class='applications-table'>"
                "<thead><tr><th>Company</th><th>Role</th><th>Status</th><th>Applied</th><th>Next action</th><th>Notes</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></div>",
                unsafe_allow_html=True,
            )
            st.caption(f"{len(filtered)} of {len(items)} applications shown")
        else:
            st.info("No applications match these filters." if items else "Add your first internship to start tracking your pipeline.")
        st.subheader("Recent activity")
        for row in activity(user_id, 8):
            with st.container(border=True):
                st.markdown(f"**{row['action']}**")
                st.write(row["details"] or "")
                st.caption(row["created_at"])
    with right:
        st.subheader("Reminders due")
        due = [r for r in list_reminders(user_id, include_completed=False) if r["reminder_date"] <= date.today().isoformat()]
        for row in due[:5]:
            with st.container(border=True):
                st.write(f"**{row['company_name']} · {row['reminder_type']}**")
                st.caption(row["reminder_date"] + (" · overdue" if row["reminder_date"] < date.today().isoformat() else " · today"))
                if st.button("Complete", key=f"dashboard-reminder-{row['id']}"):
                    toggle_reminder(user_id, row["id"], True)
                    st.rerun()
        if not due: st.info("No reminders due today.")
        st.subheader("Upcoming deadlines")
        deadlines = [i for i in items if i.deadline and i.deadline >= date.today().isoformat() and i.status not in {"Rejected", "Accepted"}]
        for item in sorted(deadlines, key=lambda x: x.deadline)[:6]:
            with st.container(border=True):
                st.markdown(f"**{item.company_name}**")
                st.write(item.role_title)
                st.caption(item.deadline)
        if not deadlines: st.info("No upcoming deadlines.")


def _date_value(value: str | None):
    return date.fromisoformat(value) if value else None


def internship_form(user_id: int, profile, item=None, key="new") -> None:
    with st.form(f"internship-{key}"):
        c1, c2 = st.columns(2)
        with c1:
            company = st.text_input("Company *", value=item.company_name if item else "")
            role = st.text_input("Role *", value=item.role_title if item else "")
            location = st.text_input("Location", value=item.location or "" if item else "")
            link = st.text_input("Application link", value=item.application_link or "" if item else "")
            source = st.text_input("Source", value=item.source or "" if item else "", placeholder="LinkedIn, referral, company site")
            salary = st.text_input("Salary / compensation", value=item.salary or "" if item else "")
        with c2:
            status = st.selectbox("Status", STATUSES, index=STATUSES.index(item.status) if item else 0)
            priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(item.priority) if item else 1)
            applied = st.date_input("Date applied", value=_date_value(item.date_applied) if item else None, format="YYYY-MM-DD")
            deadline = st.date_input("Deadline", value=_date_value(item.deadline) if item else None, format="YYYY-MM-DD")
            followup = st.date_input(
                "Follow-up",
                value=_date_value(get_auto_reminder_date(user_id, item.id, "Follow-up")) if item else None,
                format="YYYY-MM-DD",
            )
            resume = st.text_input("Resume version", value=item.resume_version or profile["resume_version"] or "" if item else profile["resume_version"] or "")
        recruiter = st.text_input("Recruiter / contact", value=item.recruiter_name or "" if item else "")
        contact = st.text_input("Contact info", value=item.recruiter_contact or "" if item else "")
        next_action = st.text_input("Next action", value=item.next_action or "" if item else "")
        notes = st.text_area("Notes", value=item.notes or "" if item else "")
        submit = st.form_submit_button("Save", type="primary")
    if submit:
        data = {
            "company_name": company, "role_title": role, "location": location.strip() or None, "application_link": link.strip() or None,
            "deadline": deadline.isoformat() if deadline else None, "date_applied": applied.isoformat() if applied else None,
            "status": status, "notes": notes.strip() or None, "recruiter_name": recruiter.strip() or None,
            "recruiter_contact": contact.strip() or None, "salary": salary.strip() or None, "source": source.strip() or None,
            "priority": priority, "next_action": next_action.strip() or None, "resume_version": resume.strip() or None,
            "follow_up_date": followup.isoformat() if followup else None,
        }
        try:
            save_internship(user_id, data, item.id if item else None)
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))


def internships_page(user_id: int, profile) -> None:
    st.title("Internships")
    items = list_internships(user_id)
    with st.expander("Add internship", expanded=not items):
        internship_form(user_id, profile)
    if not items: return
    f1, f2, f3 = st.columns([2,1,1])
    search = f1.text_input("Search")
    status_filter = f2.selectbox("Status", ["All"] + STATUSES)
    priority_filter = f3.selectbox("Priority", ["All"] + PRIORITIES)
    filtered = []
    for item in items:
        haystack = " ".join([item.company_name, item.role_title, item.location or "", item.recruiter_name or "", item.source or ""]).lower()
        if search and search.lower() not in haystack: continue
        if status_filter != "All" and item.status != status_filter: continue
        if priority_filter != "All" and item.priority != priority_filter: continue
        filtered.append(item)
    st.dataframe([{"Company":i.company_name,"Role":i.role_title,"Status":i.status,"Priority":i.priority,"Deadline":i.deadline or "","Resume":i.resume_version or "","Next action":i.next_action or ""} for i in filtered], width="stretch", hide_index=True)
    if not filtered: return
    selected_id = st.selectbox("Open application", [i.id for i in filtered], format_func=lambda x: next(f"{i.company_name} · {i.role_title}" for i in filtered if i.id == x))
    item = next(i for i in filtered if i.id == selected_id)
    st.subheader(f"{item.company_name} · {item.role_title}")
    new_status = st.selectbox("Quick status update", STATUSES, index=STATUSES.index(item.status), key=f"status-{item.id}")
    if st.button("Update status", key=f"status-btn-{item.id}"):
        update_status(user_id, item.id, new_status); st.rerun()
    overview, edit, history = st.tabs(["Overview", "Edit", "History"])
    with overview:
        st.write(f"**Location:** {item.location or 'Not set'}")
        st.write(f"**Deadline:** {item.deadline or 'Not set'}")
        st.write(f"**Recruiter:** {item.recruiter_name or 'Not set'}")
        st.write(f"**Next action:** {item.next_action or 'Not set'}")
        if item.application_link: st.link_button("Open application", item.application_link)
        if item.notes: st.write(item.notes)
        with st.expander("Delete application"):
            confirm = st.checkbox("I understand this is permanent", key=f"confirm-{item.id}")
            if st.button("Delete", disabled=not confirm, key=f"delete-{item.id}"):
                delete_internship(user_id, item.id); st.rerun()
    with edit: internship_form(user_id, profile, item, key=str(item.id))
    with history:
        for row in reversed(status_history(user_id, item.id)):
            st.write(f"**{row['old_status'] or 'Created'} → {row['new_status']}**")
            st.caption(row["changed_at"])


def reminders_page(user_id: int) -> None:
    st.title("Reminders")
    items = list_internships(user_id)
    if not items: st.info("Add an internship first."); return
    with st.form("new-reminder"):
        internship_id = st.selectbox("Application", [i.id for i in items], format_func=lambda x: next(f"{i.company_name} · {i.role_title}" for i in items if i.id == x))
        kind = st.selectbox("Type", REMINDER_TYPES)
        when = st.date_input("Date", value=date.today())
        notes = st.text_input("Notes")
        submit = st.form_submit_button("Add reminder")
    if submit:
        add_reminder(user_id, internship_id, kind, when.isoformat(), notes); st.rerun()
    for row in list_reminders(user_id):
        with st.container(border=True):
            st.markdown(f"**{row['reminder_type']} · {row['company_name']}**")
            st.write(row["notes"] or row["role_title"])
            st.caption(row["reminder_date"] + (" · completed" if row["completed"] else ""))
            c1,c2=st.columns(2)
            if c1.button("Reopen" if row["completed"] else "Complete", key=f"toggle-{row['id']}"):
                toggle_reminder(user_id,row["id"],not bool(row["completed"])); st.rerun()
            if c2.button("Delete",key=f"rem-del-{row['id']}"):
                delete_reminder(user_id,row["id"]); st.rerun()


def interview_page(user_id: int) -> None:
    st.title("Interview Prep")
    items = list_internships(user_id)
    if not items: st.info("Add an internship first."); return
    internship_id = st.selectbox("Application", [i.id for i in items], format_func=lambda x: next(f"{i.company_name} · {i.role_title}" for i in items if i.id == x))
    qtab, ntab = st.tabs(["Questions", "Company notes"])
    with qtab:
        with st.form("question"):
            kind=st.selectbox("Type",QUESTION_TYPES); question=st.text_area("Question"); answer=st.text_area("Answer notes"); submit=st.form_submit_button("Save question")
        if submit: add_question(user_id,internship_id,kind,question,answer); st.rerun()
        for row in list_questions(user_id,internship_id):
            with st.container(border=True): st.markdown(f"**{row['question_type']}**"); st.write(row["question_text"]); st.caption(row["answer_notes"] or "")
    with ntab:
        with st.form("note"):
            note=st.text_area("Company note"); submit_note=st.form_submit_button("Save note")
        if submit_note: add_note(user_id,internship_id,note); st.rerun()
        for row in list_notes(user_id,internship_id):
            with st.container(border=True): st.write(row["note_text"]); st.caption(row["created_at"])


def analytics_page(user_id: int) -> None:
    st.title("Analytics")
    m=metrics(user_id); cols=st.columns(5)
    cols[0].metric("Tracked",m["tracked"]); cols[1].metric("Sent",m["sent"]); cols[2].metric("Interview rate",f"{m['interview_rate']}%"); cols[3].metric("Offer rate",f"{m['offer_rate']}%"); cols[4].metric("Response rate",f"{m['response_rate']}%")
    items=list_internships(user_id)
    counts={s:sum(i.status==s for i in items) for s in STATUSES}
    chart={k:v for k,v in counts.items() if v}
    if chart: st.bar_chart(chart)
    else: st.info("Add an application to see your pipeline breakdown.")
    st.caption("Rates count the stages each application has reached, even if its current status later changes.")


def ai_page(user_id: int, profile) -> None:
    st.title("AI Tools")
    st.caption("With OPENAI_API_KEY configured, job descriptions and pasted resume text are sent to OpenAI only when you request an AI analysis. Without a key, the app uses labeled local tools.")
    items=list_internships(user_id)
    if not items: st.info("Add an internship first."); return
    internship_id=st.selectbox("Application",[i.id for i in items],format_func=lambda x:next(f"{i.company_name} · {i.role_title}" for i in items if i.id==x))
    item=next(i for i in items if i.id==internship_id)
    match_tab, summary_tab, cover_tab=st.tabs(["Resume match","Job summary","Cover letter"])
    with match_tab:
        resume=st.text_area("Resume text",height=180,key="match-resume"); jd=st.text_area("Job description",height=180,key="match-jd")
        if st.button("Analyze match"):
            try:
                result=resume_match(resume,jd); save_result(user_id,item.id,"resume_match",result)
                st.metric("Keyword coverage",f"{result['score']}%"); st.write("Matching:",", ".join(result["matching_terms"])); st.write("Gaps:",", ".join(result["missing_terms"]))
                st.caption("Local keyword comparison; this is not an ATS score or hiring prediction.")
            except ValueError as exc: st.warning(str(exc))
    with summary_tab:
        jd=st.text_area("Job description",height=220,key="summary-jd")
        if st.button("Summarize"):
            try:
                result=summarize_job(jd); save_result(user_id,item.id,"job_summary",result)
                if result.get("warning"): st.warning(result["warning"])
                st.json(result)
            except ValueError as exc: st.warning(str(exc))
    with cover_tab:
        resume=st.text_area("Resume text",height=160,key="cover-resume"); jd=st.text_area("Job description",height=180,key="cover-jd")
        if st.button("Generate cover letter"):
            try:
                result=cover_letter(item.company_name,item.role_title,resume,jd,profile["display_name"])
                save_result(user_id,item.id,"cover_letter",result)
                if result.get("warning"): st.warning(result["warning"])
                st.caption(f"Generated by: {result['source']}")
                st.text_area("Draft",value=result["text"],height=320)
            except ValueError as exc: st.warning(str(exc))
    with st.expander("Saved analyses for this application"):
        history=list_results(user_id,item.id)
        if not history: st.info("No analyses saved yet.")
        for entry in history:
            st.write(f"**{entry['type'].replace('_',' ').title()} · {entry['result'].get('source','Previously saved')}**")
            st.caption(entry["created_at"])
            if entry["type"]=="cover_letter":
                st.text(entry["result"].get("text") or entry["result"].get("cover_letter", ""))
            else: st.json(entry["result"])


def profile_page(user_id: int, profile) -> None:
    st.title("Profile")
    with st.form("profile"):
        name=st.text_input("Display name",value=profile["display_name"]); bio=st.text_area("Bio",value=profile["bio"] or ""); role=st.text_input("Target role",value=profile["target_role"] or ""); resume=st.text_input("Default resume version",value=profile["resume_version"] or ""); dark=st.checkbox("Dark mode",value=bool(profile["dark_mode"])); submit=st.form_submit_button("Save",type="primary")
    if submit: update_profile(user_id,name,bio,role,resume,dark); st.rerun()
    if st.button("Log out"):
        st.session_state.clear(); st.rerun()


def export_page(user_id: int) -> None:
    st.title("Import & Export")
    st.caption("Bring in a tracker file safely, then export a clean backup whenever you need it.")
    st.subheader("Sync from a file")
    st.write("Upload CSV or JSON with `company`, `role`, `status`, `date`, and `notes` columns. `company_name`, `role_title`, and `date_applied` also work.")
    upload = st.file_uploader("Application tracker file", type=["csv", "json"])
    source = st.text_input("Import source", value="Tracker file")
    if upload and st.button("Sync applications", type="primary"):
        try:
            rows = parse_sync_file(upload.getvalue(), upload.name)
            result = sync_applications(user_id, rows, source)
            st.success(f"Sync complete: {result['added']} added, {result['updated']} updated, {result['skipped']} unchanged or skipped.")
            if result["changes"]:
                with st.expander("View changes", expanded=True):
                    for change in result["changes"]:
                        st.write(f"• {change}")
        except (UnicodeDecodeError, ValueError) as exc:
            st.error(str(exc))
    st.caption("Existing notes are preserved. New notes are appended with a date, and advanced or terminal statuses are not silently moved backward.")
    st.divider()
    st.subheader("Export a backup")
    st.download_button("Download applications CSV",export_csv(user_id),"internship_tracker_applications.csv","text/csv")
    st.caption("Passwords and password hashes are never included in exports.")


def main() -> None:
    init_db()
    user_id=st.session_state.get("user_id")
    if not user_id:
        auth_screen(); return
    user=get_user(int(user_id))
    if not user:
        st.session_state.clear(); auth_screen(); return
    profile=get_profile(user.id)
    theme(bool(profile["dark_mode"]))
    nav=sidebar(profile)
    if nav=="Dashboard": dashboard(user.id)
    elif nav=="Internships": internships_page(user.id,profile)
    elif nav=="Reminders": reminders_page(user.id)
    elif nav=="Interview Prep": interview_page(user.id)
    elif nav=="Analytics": analytics_page(user.id)
    elif nav=="AI Tools": ai_page(user.id,profile)
    elif nav=="Profile": profile_page(user.id,profile)
    elif nav=="Export": export_page(user.id)


if __name__=="__main__":
    main()
