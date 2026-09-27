from flask import Blueprint, redirect, render_template, request, session, url_for

from ai_detector import detect_with_ai
from extensions import database_cursor, get_message_from_request

teacher_bp = Blueprint("teacher", __name__)


def _teacher_required():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("auth.lecturer_login"))
    return None


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
    return render_template(
        "teacher_dashboard.html",
        teacher_name=session["teacher_name"],
        announcements=announcements,
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
