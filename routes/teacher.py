from flask import Blueprint, redirect, render_template, request, session, url_for

from ai_detector import detect_with_ai
from extensions import database_cursor, get_message_from_request
from message_policy import is_account_blocked

teacher_bp = Blueprint("teacher", __name__)


def _teacher_required():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("auth.lecturer_login"))
    user_id = session.get("teacher_user_id")
    if user_id is not None:
        with database_cursor() as (_, cursor):
            cursor.execute(
                "SELECT status FROM Users WHERE user_id = %s",
                (user_id,),
            )
            account = cursor.fetchone()
        if account is None or is_account_blocked(account[0]):
            session.pop("teacher_logged_in", None)
            session.pop("teacher_user_id", None)
            session.pop("teacher_name", None)
            return redirect(url_for("auth.lecturer_login"))
    return None


@teacher_bp.route("/announcement-delete", methods=["POST"])
def delete_announcement():
    redirect_response = _teacher_required()
    if redirect_response:
        return redirect_response
    announcement_id = request.form.get("announcement_id", type=int)
    if announcement_id is None:
        return "An announcement is required.", 400
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            "UPDATE Reports SET announcement_id = NULL WHERE announcement_id = %s",
            (announcement_id,),
        )
        cursor.execute(
            """
            DELETE FROM Announcements
            WHERE announcement_id = %s AND teacher_id = %s
            """,
            (announcement_id, session["teacher_user_id"]),
        )
        if cursor.rowcount == 0:
            return "You can only delete your own announcements.", 403
    return redirect(url_for("teacher.teacher_dashboard"))


@teacher_bp.route("/lecturer-message-delete", methods=["POST"])
def delete_message():
    redirect_response = _teacher_required()
    if redirect_response:
        return redirect_response
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
            (message_id, session["teacher_user_id"]),
        )
        if cursor.rowcount == 0:
            return "You can only delete your own messages.", 403
    return redirect(url_for("teacher.teacher_dashboard"))


@teacher_bp.route("/lecturer-inbox-delete", methods=["POST"])
def delete_inbox_message():
    redirect_response = _teacher_required()
    if redirect_response:
        return redirect_response
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
            (session["teacher_user_id"], message_id, session["teacher_user_id"]),
        )
        if cursor.rowcount == 0:
            return "You can only remove messages from your own inbox.", 403
    return redirect(url_for("teacher.teacher_dashboard"))


@teacher_bp.route("/teacher-dashboard")
@teacher_bp.route("/lecturer-dashboard")
def teacher_dashboard():
    redirect_response = _teacher_required()
    if redirect_response:
        return redirect_response

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT announcement_id, title, content, detection_result,
                   confidence, date_created, status
            FROM Announcements
            WHERE teacher_id = %s
            ORDER BY announcement_id DESC
            LIMIT 20
            """,
            (session["teacher_user_id"],),
        )
        announcements = cursor.fetchall()
        cursor.execute(
            """
            SELECT r.announcement_id, u.full_name, u.role, r.reply_text,
                   r.date_created, r.status, r.reply_id, r.author_id
            FROM DiscussionReplies r
            JOIN Users u ON r.author_id = u.user_id
            WHERE r.announcement_id IN (
                SELECT announcement_id FROM Announcements
                WHERE teacher_id = %s
            )
              AND r.status = 'checked'
            ORDER BY r.reply_id ASC
            """,
            (session["teacher_user_id"],),
        )
        announcement_replies = cursor.fetchall()
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
            (session["teacher_user_id"], session["teacher_user_id"]),
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
            (session["teacher_user_id"],),
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
            (session["teacher_user_id"],),
        )
        notifications = cursor.fetchall()
    return render_template(
        "teacher_dashboard.html",
        teacher_name=session["teacher_name"],
        announcements=announcements,
        announcement_replies=announcement_replies,
        inbox_messages=inbox_messages,
        sent_messages=sent_messages,
        notifications=notifications,
    )


@teacher_bp.route("/teacher-announcement", methods=["POST"])
@teacher_bp.route("/lecturer-announcement", methods=["POST"])
def create_announcement():
    redirect_response = _teacher_required()
    if redirect_response:
        return redirect_response

    title = (request.form.get("title") or "").strip()
    content, error = get_message_from_request()
    if error:
        return error, 400
    if not title:
        return "Announcement title cannot be empty.", 400
    if len(title) > 150:
        return "Announcement title must be 150 characters or fewer.", 400

    result, confidence = detect_with_ai(f"{title}\n{content}")
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            INSERT INTO Announcements
            (teacher_id, title, content, detection_result, confidence, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                session["teacher_user_id"],
                title,
                content,
                result,
                confidence,
                "review_required" if result.startswith("Cyberbullying") else "published",
            ),
        )
    return redirect(url_for("teacher.teacher_dashboard"))


@teacher_bp.route("/teacher/report/print")
@teacher_bp.route("/lecturer/report/print")
def print_teacher_report():
    redirect_response = _teacher_required()
    if redirect_response:
        return redirect_response

    from datetime import datetime

    teacher_id = session.get("teacher_user_id")

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT full_name, institution_id, email
            FROM Users WHERE user_id = %s
            """,
            (teacher_id,),
        )
        user_info = cursor.fetchone() or ("Lecturer", "N/A", "N/A")

        cursor.execute(
            """
            SELECT announcement_id, title, content, detection_result,
                   confidence, date_created, status
            FROM Announcements
            WHERE teacher_id = %s
            ORDER BY announcement_id DESC
            LIMIT 50
            """,
            (teacher_id,),
        )
        announcements = cursor.fetchall()

        cursor.execute(
            """
            SELECT r.reply_id, r.date_created, u.full_name, r.reply_text,
                   r.status
            FROM DiscussionReplies r
            JOIN Users u ON r.author_id = u.user_id
            WHERE r.announcement_id IN (
                SELECT announcement_id FROM Announcements WHERE teacher_id = %s
            )
            ORDER BY r.reply_id DESC
            LIMIT 50
            """,
            (teacher_id,),
        )
        replies = cursor.fetchall()

    records = []
    flagged_count = 0
    clean_count = 0
    resolved_count = 0

    for a in announcements:
        det = str(a[3] or "")
        is_cb = det.startswith("Cyberbullying")
        if is_cb:
            flagged_count += 1
        else:
            clean_count += 1

        if str(a[6]).lower() in ("published", "checked", "resolved"):
            resolved_count += 1

        date_str = a[5].strftime("%b %d, %Y %H:%M") if hasattr(a[5], "strftime") else str(a[5] or "")
        records.append({
            "ref_id": f"ANN-{a[0]:04d}",
            "date_str": date_str,
            "sender": user_info[0],
            "recipient": "All Enrolled Students",
            "reported_by": None,
            "content": f"[{a[1]}] {a[2]}",
            "reason": None,
            "is_cyberbullying": is_cb,
            "confidence": float(a[4]) if a[4] is not None else None,
            "action_taken": "Announcement Broadcast",
            "status": a[6],
        })

    for rep in replies:
        clean_count += 1
        date_str = rep[1].strftime("%b %d, %Y %H:%M") if hasattr(rep[1], "strftime") else str(rep[1] or "")
        records.append({
            "ref_id": f"REP-{rep[0]:04d}",
            "date_str": date_str,
            "sender": rep[2],
            "recipient": user_info[0],
            "reported_by": None,
            "content": rep[3],
            "reason": None,
            "is_cyberbullying": False,
            "confidence": None,
            "action_taken": "Discussion Thread Moderation",
            "status": rep[4] or "checked",
        })

    now = datetime.now()
    summary = {
        "total_items": len(records),
        "flagged_count": flagged_count,
        "clean_count": clean_count,
        "resolved_count": resolved_count,
    }

    inst_id = user_info[1] or "Faculty"
    return render_template(
        "printable_report.html",
        report_title="OFFICIAL COURSE DISCUSSION & SAFETY MONITORING REPORT",
        report_reference=f"NISH/LEC/MON-{now.strftime('%Y%m%d-%H%M')}",
        generated_at=now.strftime("%B %d, %Y &bull; %H:%M EAT"),
        user_name=user_info[0],
        user_role=f"Lecturer / Faculty ({inst_id})",
        summary=summary,
        records=records,
        back_url=url_for("teacher.teacher_dashboard"),
    )
