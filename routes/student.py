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


@student_bp.route("/student-message-delete", methods=["POST"])
def delete_message():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    message_id = request.form.get("message_id", type=int)
    if message_id is None:
        return "A message is required.", 400
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            "UPDATE Reports SET message_id = NULL WHERE message_id = %s",
            (message_id,),
        )
        cursor.execute("DELETE FROM Alerts WHERE message_id = %s", (message_id,))
        cursor.execute(
            "DELETE FROM Messages WHERE message_id = %s AND sender_id = %s",
            (message_id, session["student_user_id"]),
        )
        if cursor.rowcount == 0:
            return "You can only delete your own messages.", 403
    return redirect(url_for("student.student_dashboard"))


@student_bp.route("/student-inbox-delete", methods=["POST"])
def delete_inbox_message():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    message_id = request.form.get("message_id", type=int)
    if message_id is None:
        return "A message is required.", 400
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            INSERT IGNORE INTO MessageInboxDeletions (user_id, message_id)
            SELECT %s, message_id FROM Messages
            WHERE message_id = %s AND recipient_id = %s
            """,
            (session["student_user_id"], message_id, session["student_user_id"]),
        )
        if cursor.rowcount == 0:
            return "You can only remove messages from your own inbox.", 403
    return redirect(url_for("student.student_dashboard"))


@student_bp.route("/student-dashboard")
def student_dashboard():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT m.message_id, u.full_name, u.email, m.message_text,
                   m.detection_result, m.confidence, m.date_sent
            FROM Messages m
            JOIN Users u ON m.sender_id = u.user_id
            WHERE m.recipient_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM MessageInboxDeletions d
                  WHERE d.user_id = %s AND d.message_id = m.message_id
              )
            ORDER BY m.message_id DESC
            LIMIT 20
            """,
            (session["student_user_id"], session["student_user_id"]),
        )
        inbox_messages = cursor.fetchall()
        cursor.execute(
            """
            SELECT m.message_id, u.full_name, u.email, m.message_text,
                   m.detection_result, m.confidence, m.date_sent
            FROM Messages m
            JOIN Users u ON m.recipient_id = u.user_id
            WHERE m.sender_id = %s
            ORDER BY m.message_id DESC
            LIMIT 20
            """,
            (session["student_user_id"],),
        )
        sent_messages = cursor.fetchall()
        cursor.execute(
            """
            SELECT notification_id, notification_message, date_created
            FROM Notifications
            WHERE user_id = %s
            ORDER BY notification_id DESC
            LIMIT 10
            """,
            (session["student_user_id"],),
        )
        notifications = cursor.fetchall()
    return render_template(
        "student_dashboard.html",
        student_name=session.get("student_name"),
        inbox_messages=inbox_messages,
        sent_messages=sent_messages,
        notifications=notifications,
    )


def _save_public_post(message):
    result, confidence = detect_with_ai(message)
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            INSERT INTO Messages
            (sender_id, recipient_id, message_text, detection_result, confidence, status)
            VALUES (%s, NULL, %s, %s, %s, %s)
            """,
            (
                session["student_user_id"],
                message,
                result,
                confidence,
                "review_required" if result.startswith("Cyberbullying") else "checked",
            ),
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
                    "Cyberbullying",
                    "Cyberbullying detected in a student blog post.",
                    "unread",
                ),
            )


@student_bp.route("/student-post", methods=["POST"])
def student_post():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    message, error = get_message_from_request()
    if error:
        return error, 400
    _save_public_post(message)
    return redirect(url_for("discussion.blog"))


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
