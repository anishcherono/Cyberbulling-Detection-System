from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ai_detector import detect_with_ai
from extensions import database_cursor, get_message_from_request
from message_policy import get_delivery_decision
from user_directory import normalize_role

discussion_bp = Blueprint("discussion", __name__)


def _current_user():
    if session.get("student_logged_in"):
        return session["student_user_id"], "Student"
    if session.get("teacher_logged_in"):
        return session["teacher_user_id"], "Lecturer"
    return None, None


def _login_redirect():
    if session.get("teacher_logged_in"):
        return redirect(url_for("auth.lecturer_login"))
    return redirect(url_for("auth.student_login"))


@discussion_bp.route("/blog-message-delete", methods=["POST"])
def delete_message():
    user_id, _ = _current_user()
    if user_id is None:
        return _login_redirect()
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
            (message_id, user_id),
        )
        if cursor.rowcount == 0:
            return "You can only delete your own messages.", 403
    return redirect(url_for("discussion.blog"))


@discussion_bp.route("/discussion-delete", methods=["POST"])
def delete_discussion_item():
    user_id, _ = _current_user()
    if user_id is None:
        return _login_redirect()
    announcement_id = request.form.get("announcement_id", type=int)
    reply_id = request.form.get("reply_id", type=int)
    if (announcement_id is None) == (reply_id is None):
        return "Choose one discussion item to delete.", 400
    with database_cursor(commit=True) as (_, cursor):
        if announcement_id is not None:
            cursor.execute(
                "UPDATE Reports SET announcement_id = NULL WHERE announcement_id = %s",
                (announcement_id,),
            )
            cursor.execute(
                """
                DELETE FROM Announcements
                WHERE announcement_id = %s AND teacher_id = %s
                """,
                (announcement_id, user_id),
            )
        else:
            cursor.execute(
                "UPDATE Reports SET reply_id = NULL WHERE reply_id = %s",
                (reply_id,),
            )
            cursor.execute(
                """
                DELETE FROM DiscussionReplies
                WHERE reply_id = %s AND author_id = %s
                """,
                (reply_id, user_id),
            )
        if cursor.rowcount == 0:
            return "You can only delete your own discussion items.", 403
    return redirect(url_for("discussion.blog"))


@discussion_bp.route("/content-report", methods=["POST"])
def report_content():
    user_id, _ = _current_user()
    if user_id is None:
        return _login_redirect()
    message_id = request.form.get("message_id", type=int)
    announcement_id = request.form.get("announcement_id", type=int)
    reply_id = request.form.get("reply_id", type=int)
    reason = (request.form.get("reason") or "Content reported by a user.").strip()
    targets = [message_id, announcement_id, reply_id]
    if sum(target is not None for target in targets) != 1:
        return "Choose one item to report.", 400
    if len(reason) > 1000:
        return "Report reason must be 1000 characters or fewer.", 400
    with database_cursor(commit=True) as (_, cursor):
        if message_id is not None:
            cursor.execute("SELECT message_id FROM Messages WHERE message_id = %s", (message_id,))
        elif announcement_id is not None:
            cursor.execute(
                "SELECT announcement_id FROM Announcements WHERE announcement_id = %s",
                (announcement_id,),
            )
        else:
            cursor.execute(
                "SELECT reply_id FROM DiscussionReplies WHERE reply_id = %s",
                (reply_id,),
            )
        if cursor.fetchone() is None:
            return "The item no longer exists.", 404
        cursor.execute(
            """
            INSERT INTO Reports
            (message_id, announcement_id, reply_id, reported_by,
             reason, action_taken, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                message_id,
                announcement_id,
                reply_id,
                user_id,
                reason,
                "Pending",
                "Pending",
            ),
        )
    return redirect(url_for("discussion.blog"))


@discussion_bp.route("/message-recipients")
def message_recipients():
    user_id, sender_role = _current_user()
    if user_id is None:
        return jsonify({"recipients": []}), 401
    query = (request.args.get("q") or "").strip().lower()
    if len(query) < 2:
        return jsonify({"recipients": []})

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT user_id, full_name, email, role, status
            FROM Users
            WHERE user_id <> %s
              AND status = 'active'
              AND LOWER(role) IN ('student', 'teacher', 'lecturer')
              AND email IS NOT NULL
              AND (LOWER(email) LIKE %s OR LOWER(full_name) LIKE %s)
            ORDER BY full_name ASC
            LIMIT 20
            """,
            (user_id, f"%{query}%", f"%{query}%"),
        )
        recipients = []
        for row in cursor.fetchall():
            recipients.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "role": normalize_role(row[3]),
                }
            )
    return jsonify({"recipients": recipients})


@discussion_bp.route("/message-send", methods=["POST"])
def send_message():
    sender_id, sender_role = _current_user()
    if sender_id is None:
        return _login_redirect()
    recipient_email = (request.form.get("recipient_email") or "").strip().lower()
    message, error = get_message_from_request()
    if error:
        return error, 400
    if not recipient_email:
        return "Recipient institution email is required.", 400

    result, confidence = detect_with_ai(message)
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            SELECT user_id FROM Users
            WHERE LOWER(email) = %s AND user_id <> %s
            """,
            (recipient_email, sender_id),
        )
        recipient = cursor.fetchone()
        if recipient is None:
            return "No institution user was found with that email.", 404

        decision = get_delivery_decision(result, confidence, recipient[0])
        if not decision["delivery_allowed"]:
            cursor.execute(
                """
                INSERT INTO Messages
                (sender_id, recipient_id, message_text, detection_result,
                 confidence, status)
                VALUES (%s, NULL, %s, %s, %s, %s)
                """,
                (
                    sender_id,
                    message,
                    result,
                    confidence,
                    decision["status"],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO Messages
                (sender_id, recipient_id, message_text, detection_result,
                 confidence, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    sender_id,
                    decision["recipient_id"],
                    message,
                    result,
                    confidence,
                    decision["status"],
                ),
            )

        message_id = cursor.lastrowid
        if not decision["delivery_allowed"]:
            cursor.execute(
                """
                INSERT INTO Alerts (message_id, alert_type, alert_message, status)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    message_id,
                    "Cyberbullying",
                    decision["notification_message"] +
                    f" Blocked message: {message}",
                    "unread",
                ),
            )
            cursor.execute(
                """
                INSERT INTO Notifications
                (user_id, notification_type, notification_message)
                VALUES (%s, %s, %s)
                """,
                (
                    sender_id,
                    "cyberbullying_blocked",
                    decision["notification_message"],
                ),
            )

    destination = (
        "teacher.teacher_dashboard"
        if sender_role == "Lecturer"
        else "student.student_dashboard"
    )
    return redirect(url_for(destination))


@discussion_bp.route("/blog")
def blog():
    user_id, role = _current_user()
    if user_id is None:
        return _login_redirect()

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT m.message_id, u.full_name, u.role, m.message_text,
                   DATE_FORMAT(m.date_sent, '%Y-%m-%d %H:%i') AS posted_at,
                   m.sender_id
            FROM Messages m
            JOIN Users u ON m.sender_id = u.user_id
            WHERE m.recipient_id IS NULL
              AND m.status = 'checked'
            ORDER BY m.message_id DESC
            LIMIT 50
            """
        )
        posts = cursor.fetchall()
        cursor.execute(
            """
            SELECT a.announcement_id, u.full_name, a.title, a.content,
                   DATE_FORMAT(a.date_created, '%Y-%m-%d %H:%i') AS posted_at,
                   a.teacher_id
            FROM Announcements a
            JOIN Users u ON a.teacher_id = u.user_id
            WHERE a.status = 'published'
            ORDER BY a.announcement_id DESC
            LIMIT 50
            """
        )
        announcements = cursor.fetchall()
        cursor.execute(
            """
            SELECT r.reply_id, r.message_id, r.announcement_id,
                   u.full_name, u.role, r.reply_text,
                   DATE_FORMAT(r.date_created, '%Y-%m-%d %H:%i') AS posted_at,
                   r.author_id
            FROM DiscussionReplies r
            JOIN Users u ON r.author_id = u.user_id
            WHERE r.status = 'checked'
            ORDER BY r.reply_id ASC
            LIMIT 500
            """
        )
        replies = cursor.fetchall()

    return render_template(
        "blog.html",
        viewer_role=role,
        posts=posts,
        announcements=announcements,
        replies=replies,
    )


@discussion_bp.route("/discussion-reply", methods=["POST"])
def create_reply():
    author_id, _ = _current_user()
    if author_id is None:
        return _login_redirect()

    message_id = request.form.get("message_id", type=int)
    announcement_id = request.form.get("announcement_id", type=int)
    if (message_id is None) == (announcement_id is None):
        return "Choose one post or announcement to reply to.", 400

    reply_text, error = get_message_from_request()
    if error:
        return error, 400

    result, confidence = detect_with_ai(reply_text)
    status = "review_required" if result.startswith("Cyberbullying") else "checked"
    with database_cursor(commit=True) as (_, cursor):
        if message_id is not None:
            cursor.execute(
                "SELECT message_id FROM Messages WHERE message_id = %s",
                (message_id,),
            )
        else:
            cursor.execute(
                """
                SELECT announcement_id FROM Announcements
                WHERE announcement_id = %s AND status = 'published'
                """,
                (announcement_id,),
            )
        if cursor.fetchone() is None:
            return "The discussion item no longer exists.", 404
        cursor.execute(
            """
            INSERT INTO DiscussionReplies
            (message_id, announcement_id, author_id, reply_text,
             detection_result, confidence, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                message_id,
                announcement_id,
                author_id,
                reply_text,
                result,
                confidence,
                status,
            ),
        )

    return redirect(url_for("discussion.blog"))
