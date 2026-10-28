from flask import Blueprint, redirect, render_template, request, session, url_for

from ai_detector import detect_with_ai
from extensions import (
    REPORT_REASON_MAX_LENGTH,
    database_cursor,
    get_message_from_request,
    is_account_blocked,
    notice_from_notification_row,
)

student_bp = Blueprint("student", __name__)


def _student_login_redirect():
    return redirect(url_for("auth.student_login"))


def _student_required():
    if not session.get("student_logged_in"):
        return _student_login_redirect()
    user_id = session.get("student_user_id")
    if user_id is not None:
        with database_cursor() as (_, cursor):
            cursor.execute(
                "SELECT status FROM Users WHERE user_id = ?",
                (user_id,),
            )
            account = cursor.fetchone()
        if account is None or is_account_blocked(account[0]):
            session.pop("student_logged_in", None)
            session.pop("student_user_id", None)
            session.pop("student_name", None)
            return _student_login_redirect()
    return None


@student_bp.route("/student-message-delete", methods=["POST"])
def delete_message():
    redirect_response = _student_required()
    if redirect_response:
        return redirect_response
    message_id = request.form.get("message_id", type=int)
    if message_id is None:
        return "A message is required.", 400
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            "UPDATE Reports SET message_id = NULL WHERE message_id = ?",
            (message_id,),
        )
        cursor.execute("DELETE FROM Alerts WHERE message_id = ?", (message_id,))
        cursor.execute(
            "DELETE FROM Messages WHERE message_id = ? AND sender_id = ?",
            (message_id, session["student_user_id"]),
        )
        if cursor.rowcount == 0:
            return "You can only delete your own messages.", 403
    return redirect(url_for("student.student_dashboard"))


@student_bp.route("/student-inbox-delete", methods=["POST"])
def delete_inbox_message():
    redirect_response = _student_required()
    if redirect_response:
        return redirect_response
    message_id = request.form.get("message_id", type=int)
    if message_id is None:
        return "A message is required.", 400
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            INSERT OR IGNORE INTO MessageInboxDeletions (user_id, message_id)
            SELECT ?, message_id FROM Messages
            WHERE message_id = ? AND recipient_id = ?
            """,
            (session["student_user_id"], message_id, session["student_user_id"]),
        )
        if cursor.rowcount == 0:
            return "You can only remove messages from your own inbox.", 403
    return redirect(url_for("student.student_dashboard"))


@student_bp.route("/student-dashboard")
def student_dashboard():
    redirect_response = _student_required()
    if redirect_response:
        return redirect_response
    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT m.message_id, u.full_name, u.email, m.message_text,
                   m.detection_result, m.confidence, m.date_sent
            FROM Messages m
            JOIN Users u ON m.sender_id = u.user_id
            WHERE m.recipient_id = ?
              AND m.status = 'checked'
              AND NOT EXISTS (
                  SELECT 1 FROM MessageInboxDeletions d
                  WHERE d.user_id = ? AND d.message_id = m.message_id
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
            WHERE m.sender_id = ?
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
            WHERE user_id = ?
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
            VALUES (?, NULL, ?, ?, ?, ?)
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
                VALUES (?, ?, ?, ?)
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
    redirect_response = _student_required()
    if redirect_response:
        return redirect_response
    message, error = get_message_from_request()
    if error:
        return error, 400
    _save_public_post(message)
    return redirect(url_for("discussion.blog"))


@student_bp.route("/report", methods=["POST"])
def report_message():
    redirect_response = _student_required()
    if redirect_response:
        return redirect_response
    message_id = request.form.get("message_id", type=int)
    reason = (request.form.get("reason") or "").strip()
    if message_id is None or not reason:
        return "A message and report reason are required.", 400
    if len(reason) > REPORT_REASON_MAX_LENGTH:
        return f"Report reason must be {REPORT_REASON_MAX_LENGTH} characters or fewer.", 400
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            "SELECT message_id FROM Messages WHERE message_id = ? AND sender_id = ?",
            (message_id, session.get("student_user_id")),
        )
        if cursor.fetchone() is None:
            return "You can only report your own messages.", 403
        cursor.execute(
            """
            INSERT INTO Reports
            (message_id, reported_by, reason, action_taken, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, session["student_user_id"], reason, "Pending", "Pending"),
        )
    return """
    <h2>Message Reported Successfully</h2>
    <p>The message has been reported to the administrator.</p>
    <a href="/student-dashboard">Back to Student Dashboard</a>
    """


@student_bp.route("/student/report/print")
def print_student_report():
    redirect_response = _student_required()
    if redirect_response:
        return redirect_response

    from datetime import datetime

    user_id = session.get("student_user_id")

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT full_name, institution_id, email
            FROM Users WHERE user_id = ?
            """,
            (user_id,),
        )
        user_info = cursor.fetchone() or ("Student", "N/A", "N/A")

        cursor.execute(
            """
            SELECT m.message_id, m.date_sent, sender.full_name, recipient.full_name,
                   m.message_text, m.detection_result, m.confidence, m.status,
                   r.reason, r.action_taken, r.status
            FROM Messages m
            JOIN Users sender ON m.sender_id = sender.user_id
            LEFT JOIN Users recipient ON m.recipient_id = recipient.user_id
            LEFT JOIN Reports r ON m.message_id = r.message_id
            WHERE m.sender_id = ? OR m.recipient_id = ?
            ORDER BY m.message_id DESC
            LIMIT 50
            """,
            (user_id, user_id),
        )
        rows = cursor.fetchall()

    records = []
    flagged_count = 0
    clean_count = 0
    resolved_count = 0

    for r in rows:
        det = str(r[5] or "")
        is_cb = det.startswith("Cyberbullying")
        if is_cb:
            flagged_count += 1
        else:
            clean_count += 1

        stat = str(r[10] or r[7] or "")
        if stat.lower() in ("resolved", "checked"):
            resolved_count += 1

        date_str = r[1].strftime("%b %d, %Y %H:%M") if hasattr(r[1], "strftime") else str(r[1] or "")

        status_labels = {
            "warning_issued": "Warning Issued",
            "blocked_admin_review": "Blocked (Pending Review)",
            "restricted": "Restricted",
            "banned": "Banned",
            "checked": "Cleared / Delivered",
            "Resolved": "Resolved",
            "Pending": "Pending",
        }
        raw_stat = r[10] or r[7] or "Recorded"

        records.append({
            "ref_id": f"MSG-{r[0]:04d}",
            "date_str": date_str,
            "sender": r[2] or "Me",
            "recipient": r[3] or "Public Forum",
            "reported_by": "Self" if r[8] else None,
            "content": r[4],
            "reason": r[8],
            "is_cyberbullying": is_cb,
            "confidence": float(r[6]) if r[6] is not None else None,
            "action_taken": r[9] or ("Flagged by AI Filter" if is_cb else "Standard AI Filter Check"),
            "status": status_labels.get(raw_stat, raw_stat.replace("_", " ").title()),
        })

    now = datetime.now()
    summary = {
        "total_items": len(records),
        "flagged_count": flagged_count,
        "clean_count": clean_count,
        "resolved_count": resolved_count,
    }

    inst_id = user_info[1] or "N/A"
    return render_template(
        "printable_report.html",
        report_title="OFFICIAL STUDENT DIGITAL COMMUNICATION & SAFETY RECORD",
        report_reference=f"NISH/STU/REC-{now.strftime('%Y%m%d-%H%M')}",
        generated_at=now.strftime("%B %d, %Y \u2022 %H:%M EAT"),
        user_name=user_info[0],
        user_role=f"Student (ID: {inst_id})",
        summary=summary,
        records=records,
        back_url=url_for("student.student_dashboard"),
    )


@student_bp.route("/student/notice/<int:notification_id>")
def view_student_notice(notification_id):
    redirect_response = _student_required()
    if redirect_response:
        return redirect_response

    user_id = session.get("student_user_id")

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT n.notification_id, n.notification_message, n.date_created,
                   u.full_name, u.institution_id, u.email
            FROM Notifications n
            JOIN Users u ON n.user_id = u.user_id
            WHERE n.notification_id = ? AND n.user_id = ?
            """,
            (notification_id, user_id),
        )
        row = cursor.fetchone()

    if not row:
        return "Disciplinary decision notice not found.", 404

    notice_dict = notice_from_notification_row(
        notification_id=row[0],
        raw_text=row[1],
        date_created=row[2],
        student_name=row[3],
        institution_id=row[4],
        email=row[5],
    )

    return render_template(
        "formal_notice.html",
        notice=notice_dict,
        back_url=url_for("student.student_dashboard"),
    )
