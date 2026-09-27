from flask import Blueprint, redirect, render_template, request, session, url_for

from ai_detector import detect_with_ai
from extensions import (
    REPORT_REASON_MAX_LENGTH,
    database_cursor,
    get_message_from_request,
)

student_bp = Blueprint("student", __name__)


def _student_login_redirect():
    return redirect(url_for("auth.student_login"))


def _validated_message():
    message, error = get_message_from_request()
    return (error, 400) if error else message


@student_bp.route("/student-dashboard")
def student_dashboard():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT message_id, message_text, detection_result, confidence, date_sent
            FROM Messages WHERE sender_id = %s
            ORDER BY message_id DESC LIMIT 10
            """,
            (session.get("student_user_id"),),
        )
        posts = cursor.fetchall()
        cursor.execute(
            """
            SELECT a.title, a.content, u.full_name, a.date_created,
                   a.detection_result
            FROM Announcements a
            JOIN Users u ON a.teacher_id = u.user_id
            WHERE a.status = 'published'
            ORDER BY a.announcement_id DESC
            LIMIT 10
            """
        )
        announcements = cursor.fetchall()
    return render_template(
        "student_dashboard.html",
        student_name=session.get("student_name"),
        posts=posts,
        announcements=announcements,
    )


def _save_message(message, alert_message, alert_type_from_result=True):
    result, confidence = detect_with_ai(message)
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            INSERT INTO Messages
            (sender_id, message_text, detection_result, confidence, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (session["student_user_id"], message, result, confidence, "checked"),
        )
        message_id = cursor.lastrowid
        if result.startswith("Cyberbullying"):
            cursor.execute(
                """
                INSERT INTO Alerts (message_id, alert_type, alert_message, status)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    message_id,
                    result if alert_type_from_result else "Cyberbullying",
                    alert_message,
                    "unread",
                ),
            )
        
    return result, confidence, message_id


@student_bp.route("/student-post", methods=["POST"])
def student_post():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    message = _validated_message()
    if isinstance(message, tuple):
        return message
    _save_message(
        message,
        "Cyberbullying detected in a student post.",
        alert_type_from_result=False,
    )
    return redirect(url_for("student.student_dashboard"))


@student_bp.route("/check", methods=["POST"])
def check_message():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    message = _validated_message()
    if isinstance(message, tuple):
        return message
    result, confidence, message_id = _save_message(
        message, "Cyberbullying detected in a message."
    )
    return render_template(
        "result.html",
        message=message,
        result=result,
        confidence=confidence,
        message_id=message_id,
    )


@student_bp.route("/report", methods=["POST"])
def report_message():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    message_id = request.form.get("message_id", type=int)
    reason = (request.form.get("reason") or "").strip()
    if message_id is None or not reason:
        return "A message and report reason are required.", 400
    if len(reason) > REPORT_REASON_MAX_LENGTH:
        return f"Report reason must be {REPORT_REASON_MAX_LENGTH} characters or fewer.", 400
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            "SELECT message_id FROM Messages WHERE message_id = %s AND sender_id = %s",
            (message_id, session.get("student_user_id")),
        )
        if cursor.fetchone() is None:
            return "You can only report your own messages.", 403
        cursor.execute(
            """
            INSERT INTO Reports
            (message_id, reported_by, reason, action_taken, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (message_id, session["student_user_id"], reason, "Pending", "Pending"),
        )
    return """
    <h2>Message Reported Successfully</h2>
    <p>The message has been reported to the administrator.</p>
    <a href="/student-dashboard">Back to Student Dashboard</a>
    """
