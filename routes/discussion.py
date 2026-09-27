from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ai_detector import detect_with_ai
from extensions import database_cursor, get_message_from_request

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


@discussion_bp.route("/message-recipients")
def message_recipients():
    user_id, _ = _current_user()
    if user_id is None:
        return jsonify({"recipients": []}), 401
    query = (request.args.get("q") or "").strip().lower()
    if len(query) < 2:
        return jsonify({"recipients": []})
    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT user_id, full_name, email, role
            FROM Users
            WHERE user_id <> %s
              AND email IS NOT NULL
              AND (LOWER(email) LIKE %s OR LOWER(full_name) LIKE %s)
            ORDER BY full_name ASC
            LIMIT 10
            """,
            (user_id, f"%{query}%", f"%{query}%"),
        )
        recipients = [
            {"id": row[0], "name": row[1], "email": row[2], "role": row[3]}
            for row in cursor.fetchall()
        ]
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
    status = "review_required" if result.startswith("Cyberbullying") else "checked"
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
        cursor.execute(
            """
            INSERT INTO Messages
            (sender_id, recipient_id, message_text, detection_result, confidence, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (sender_id, recipient[0], message, result, confidence, status),
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
                    "Cyberbullying detected in a direct message.",
                    "unread",
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
                   DATE_FORMAT(m.date_sent, '%Y-%m-%d %H:%i') AS posted_at
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
                   DATE_FORMAT(a.date_created, '%Y-%m-%d %H:%i') AS posted_at
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
                   DATE_FORMAT(r.date_created, '%Y-%m-%d %H:%i') AS posted_at
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
