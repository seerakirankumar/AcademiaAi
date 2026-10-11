"""
Personalised recommendations.

Each recommendation is produced by a transparent rule, is linked to the exact
student indicators that triggered it (`based_on`), and is worded as SUPPORT, not
as a judgement. Recommendations are suggestions for faculty/placement mentors
and students to discuss; nothing here is decided automatically.

DATA LIMITATION: the datasets contain aggregate scores only (no per-subject marks
or subject names), so the backend cannot produce a subject-by-subject revision
plan. The academic recommendation says so and asks the mentor to pair it with the
student's subject-wise marks.
"""
from __future__ import annotations

from .config import OPEN_INTERVENTION_STATUSES, REC_CONFIG as C
from .utils import is_missing

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def _val(row: dict, key: str):
    v = row.get(key)
    return None if is_missing(v) else v


def _based_on(row: dict, *pairs: tuple[str, str]) -> list[dict]:
    """pairs = (column, human label). Only includes columns that actually have data."""
    out = []
    for col, label in pairs:
        v = _val(row, col)
        if v is not None:
            out.append({"indicator": col, "label": label, "value": v})
    return out


def build_recommendations(row: dict, open_interventions: list[dict]) -> list[dict]:
    recs: list[dict] = []

    def add(rec_id, category, priority, title, description, steps, based_on, intervention_type=None):
        if not based_on and rec_id != "maintain_momentum":
            return
        existing = next((i for i in open_interventions
                         if intervention_type and i["intervention_type"] == intervention_type
                         and i["status"] in OPEN_INTERVENTION_STATUSES), None)
        recs.append({
            "id": rec_id, "category": category, "priority": priority, "title": title,
            "description": description, "suggested_steps": steps, "based_on": based_on,
            "related_intervention_type": intervention_type,
            "existing_open_intervention": None if existing is None else {
                "intervention_id": existing["intervention_id"], "status": existing["status"]},
        })

    # ---- Attendance
    att, short = _val(row, "overall_attendance_pct"), _val(row, "subjects_below_attendance_threshold")
    if (att is not None and att < C["attendance_below"]) or (short is not None and short >= 1):
        high = att is not None and att < C["attendance_high_below"]
        n = f" in {int(short)} subject(s)" if short else ""
        add("attendance_support", "Attendance", "High" if high else "Medium",
            "Attendance improvement support",
            f"Attendance is below the expected level{n}. A short conversation to understand the "
            "reasons (health, travel, timetable, motivation) is the best first step.",
            ["Meet the class mentor to identify which subjects are short and why",
             "Agree on a realistic weekly attendance target",
             "Ask faculty about make-up classes or notes for missed sessions"],
            _based_on(row, ("overall_attendance_pct", "Overall attendance %"),
                      ("subjects_below_attendance_threshold", "Subjects below threshold")),
            "Attendance counselling")

    # ---- Academics
    cgpa, sem, internal = _val(row, "cgpa"), _val(row, "semester_score_pct"), _val(row, "internal_score_pct")
    weak = ((cgpa is not None and cgpa < C["cgpa_below"]) or (sem is not None and sem < C["semester_below"])
            or (internal is not None and internal < C["internal_below"]))
    if weak:
        high = cgpa is not None and cgpa < C["cgpa_high_below"]
        add("academic_revision", "Academics", "High" if high else "Medium",
            "Structured revision plan",
            "Academic scores are lower than expected. The dataset only holds aggregate scores (no "
            "subject-wise marks), so please pair this plan with the student's subject-wise results.",
            ["List the subjects with the lowest marks together with the mentor",
             "Block 3-4 revision slots per week, starting with the weakest subject",
             "Use past papers and faculty doubt-clearing sessions",
             "Re-check progress after the next internal assessment"],
            _based_on(row, ("cgpa", "CGPA (0-10)"), ("semester_score_pct", "Semester score %"),
                      ("internal_score_pct", "Internal score %")),
            "Academic tutoring")

    # ---- Backlogs
    backlogs = _val(row, "backlogs")
    if backlogs is not None and backlogs >= 1:
        add("backlog_preparation", "Academics", "High" if backlogs >= 3 else "Medium",
            "Backlog preparation plan",
            f"{int(backlogs)} backlog(s) recorded. Clearing them one at a time with a dated plan is "
            "usually more manageable than trying to do everything at once.",
            ["Note the upcoming backlog exam dates",
             "Clear the backlog with the best chance of passing first",
             "Join tutoring or peer-study sessions for those subjects"],
            _based_on(row, ("backlogs", "Backlogs")), "Academic tutoring")

    # ---- LMS / assignments
    assign = _val(row, "assignment_completion_pct")
    if assign is not None and assign < C["assignment_below"]:
        add("assignment_completion", "Learning habits", "High" if assign < C["assignment_high_below"] else "Medium",
            "Assignment completion plan",
            "A good share of assignments is still pending. A small weekly routine can help catch up.",
            ["List all pending assignments with their deadlines",
             "Finish one pending assignment every two days, oldest first",
             "Ask the faculty about extensions for assignments that are already overdue"],
            _based_on(row, ("assignment_completion_pct", "Assignment completion %")), "Mentoring")
    logins, hours = _val(row, "logins_last_30_days"), _val(row, "avg_weekly_learning_hours")
    if (logins is not None and logins < C["logins_below"]) or (hours is not None and hours < C["weekly_hours_below"]):
        add("lms_engagement", "Learning habits", "Medium" if (logins is not None and logins < C["logins_below"]) else "Low",
            "Increase regular learning time",
            "LMS activity or weekly learning hours are low. Short, regular study sessions work better than rare long ones.",
            ["Set fixed study slots in the weekly timetable",
             "Log in to the LMS at least every other day to check new material",
             "Share a weekly learning-hours goal with the mentor"],
            _based_on(row, ("logins_last_30_days", "Logins in last 30 days"),
                      ("avg_weekly_learning_hours", "Average weekly learning hours")))

    # ---- Placement preparation
    def skill_rec(col, label, rec_id, title, desc, steps, intervention_type):
        v = _val(row, col)
        if v is not None and v < C["skill_below"]:
            add(rec_id, "Placement readiness", "High" if v < C["skill_high_below"] else "Medium",
                title, desc, steps, _based_on(row, (col, label)), intervention_type)

    skill_rec("aptitude_score", "Aptitude score", "daily_aptitude", "Daily aptitude practice",
              "Aptitude is a common first screening round, and regular short practice improves it steadily.",
              ["Practise 20-30 minutes daily (quantitative, logical reasoning, verbal)",
               "Take one timed mock test each week and review the mistakes"], "Aptitude training")
    skill_rec("coding_score", "Coding score", "coding_practice", "Coding practice routine",
              "Coding rounds reward consistent practice with problem-solving.",
              ["Solve 3-4 graded problems per week, starting with easy ones",
               "Revise core data structures with a mentor or peer group",
               "Join a campus coding club or practice contest"], "Coding practice")
    skill_rec("mock_interview_score", "Mock interview score", "mock_interviews", "Mock interview sessions",
              "Practising interviews with feedback builds confidence and clarity.",
              ["Book a mock interview with the placement team",
               "Prepare short answers to common questions (introduction, projects, strengths)"], "Mock interview")
    skill_rec("resume_readiness_pct", "Resume readiness %", "resume_improvement", "Resume improvement",
              "A clear, well-structured resume improves shortlisting chances.",
              ["Get the resume reviewed by the placement team",
               "Add measurable details to projects and internships",
               "Keep it to one page with a consistent format"], None)
    skill_rec("technical_skill_score", "Technical skill score", "technical_skills", "Strengthen technical skills",
              "Technical skills are below the level expected for most placement roles.",
              ["Pick one core technology for the target role and follow a guided course",
               "Apply it in a small hands-on project"], None)
    soft = _val(row, "soft_skill_score")
    if soft is not None and soft < C["soft_skill_below"]:
        add("soft_skills", "Placement readiness", "Medium", "Communication and soft-skills practice",
            "Communication and teamwork matter in interviews and on the job.",
            ["Join a communication or group-discussion workshop",
             "Practise a 2-minute self-introduction with a friend or mentor"],
            _based_on(row, ("soft_skill_score", "Soft skill score")))
    projects = _val(row, "projects_count")
    if projects is not None and projects < 1 and row.get("placement_status") != "Placed":
        add("first_project", "Placement readiness", "Medium", "Start a first portfolio project",
            "No projects are recorded yet; even one small project gives you something concrete to discuss.",
            ["Choose a small project related to the target role",
             "Ask a faculty member or senior to review it"],
            _based_on(row, ("projects_count", "Projects completed")))

    # ---- Student voice / mentor meeting
    if row.get("support_requested") == "Yes":
        topic = _val(row, "feedback_topic") or "not specified"
        placement_topic = topic == "Career guidance"
        add("mentor_meeting", "Mentoring", "High",
            "Meet a placement mentor" if placement_topic else "Meet a faculty mentor",
            "The student asked for support, so a timely follow-up shows the request was heard.",
            ["Schedule a 20-30 minute one-to-one meeting",
             f"Start from the student's own feedback topic: {topic}",
             "Agree on 1-2 concrete next steps and a follow-up date"],
            _based_on(row, ("support_requested", "Support requested"), ("feedback_topic", "Feedback topic")),
            "Mentoring")
    sat, fac = _val(row, "student_satisfaction_1_to_5"), _val(row, "faculty_feedback_1_to_5")
    if (sat is not None and sat <= C["low_feedback_at_most"]) or (fac is not None and fac <= C["low_feedback_at_most"]):
        add("feedback_check_in", "Mentoring", "Low", "Check in about the learning experience",
            "Low satisfaction or faculty-feedback ratings can point to issues worth hearing about.",
            ["Ask the student what is and is not working",
             "Pass relevant concerns on to the department"],
            _based_on(row, ("student_satisfaction_1_to_5", "Student satisfaction (1-5)"),
                      ("faculty_feedback_1_to_5", "Faculty feedback (1-5)")))

    # ---- Engagement (gentle, low priority)
    events, hacks, club = _val(row, "events_attended"), _val(row, "hackathons_participated"), row.get("club_participation")
    if events == 0 and hacks == 0 and club == "None":
        add("explore_engagement", "Engagement", "Low", "Explore one campus activity",
            "No events, hackathons or clubs are recorded. Joining one activity can build skills and a peer network.",
            ["Try one club, event or hackathon this term"],
            _based_on(row, ("events_attended", "Events attended"), ("hackathons_participated", "Hackathons"),
                      ("club_participation", "Club participation")))

    # ---- Strong profile
    score = _val(row, "success_score")
    if not recs and score is not None and score >= C["strong_readiness_min_score"]:
        add("maintain_momentum", "Growth", "Low", "Keep the momentum going",
            "No support indicators were triggered. Consider stretch opportunities.",
            ["Try advanced coding contests, hackathons or leadership roles",
             "Consider mentoring a peer who needs support"],
            _based_on(row, ("success_score", "Student success score")))

    recs.sort(key=lambda r: PRIORITY_ORDER[r["priority"]])
    return recs
