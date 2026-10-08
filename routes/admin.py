from flask import Blueprint, redirect, render_template, request, session, url_for

from extensions import database_cursor
from message_policy import get_admin_decision, get_admin_enforcement_result, is_banned_status

admin_bp = Blueprint("admin", __name__)


def _admin_login_redirect():
    return redirect(url_for("auth.admin_login"))


def _delete_message_and_notify(cursor, message_id, reason):
    cursor.execute(
        """
        SELECT sender_id FROM Messages
        WHERE message_id = %s
        """,
        (message_id,),
    )
    message = cursor.fetchone()
    if message is None:
        return False
    cursor.execute(
        """
        INSERT INTO Notifications
        (user_id, notification_type, notification_message)
        VALUES (%s, %s, %s)
        """,
        (
            message[0],
            "message_deleted",
            f"An administrator deleted your message. Reason: {reason}",
        ),
    )
    cursor.execute(
        "UPDATE Reports SET message_id = NULL WHERE message_id = %s",
        (message_id,),
    )
    cursor.execute("DELETE FROM Alerts WHERE message_id = %s", (message_id,))
    cursor.execute("DELETE FROM Messages WHERE message_id = %s", (message_id,))
    return True


@admin_bp.route("/admin-delete-message", methods=["POST"])
def delete_message():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    message_id = request.form.get("message_id", type=int)
    reason = (request.form.get("reason") or "").strip()
    if message_id is None or not reason:
        return "A message and deletion reason are required.", 400
    if len(reason) > 1000:
        return "Deletion reason must be 1000 characters or fewer.", 400
    with database_cursor(commit=True) as (_, cursor):
        if not _delete_message_and_notify(cursor, message_id, reason):
            return "The message no longer exists.", 404
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/dashboard")
@admin_bp.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in") or session.get("student_logged_in"):
        return _admin_login_redirect()
    with database_cursor() as (_, cursor):
        cursor.execute("SELECT COUNT(*) FROM Users")
        total_users = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT full_name, institution_id, email
            FROM Users
            WHERE LOWER(role) = 'student'
            ORDER BY full_name ASC
            """
        )
        students = cursor.fetchall()
        cursor.execute(
            """
            SELECT full_name, institution_id, email
            FROM Users
            WHERE LOWER(role) IN ('lecturer', 'teacher')
            ORDER BY full_name ASC
            """
        )
        lecturers = cursor.fetchall()
        cursor.execute(
            """
            SELECT user_id, full_name, institution_id, email, status
            FROM Users
            WHERE status = 'temporarily_restricted'
            ORDER BY full_name ASC
            """
        )
        restricted_users = cursor.fetchall()
        cursor.execute(
            """
            SELECT user_id, full_name, institution_id, email, status
            FROM Users
            WHERE LOWER(TRIM(status)) = 'banned'
            ORDER BY full_name ASC
            """
        )
        banned_users = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM Messages")
        total_messages = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM Alerts")
        total_alerts = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM Reports")
        total_reports = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(AVG(confidence), 0) FROM Messages")
        average_confidence = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM Messages WHERE detection_result LIKE 'Cyberbullying%'")
        cyberbullying_messages = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM Messages WHERE detection_result = 'Not Cyberbullying'")
        normal_messages = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT detection_result, COUNT(*) FROM Messages
            GROUP BY detection_result ORDER BY COUNT(*) DESC
            """
        )
        result_breakdown = cursor.fetchall()
        cursor.execute(
            """
            SELECT DATE_FORMAT(date_sent, '%Y-%m-%d'), COUNT(*) FROM Messages
            GROUP BY DATE_FORMAT(date_sent, '%Y-%m-%d')
            ORDER BY DATE_FORMAT(date_sent, '%Y-%m-%d') ASC LIMIT 30
            """
        )
        daily_activity = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM Alerts WHERE status = 'unread'")
        unread_alerts = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT Messages.message_id, Users.full_name, Messages.message_text,
                   Messages.detection_result, Messages.confidence, Messages.status,
                   Messages.sender_id
            FROM Messages JOIN Users ON Messages.sender_id = Users.user_id
            ORDER BY Messages.message_id DESC LIMIT 10
            """
        )
        recent_messages = cursor.fetchall()
        cursor.execute(
            """
            SELECT Alerts.alert_id, Alerts.message_id, Users.full_name, Alerts.alert_type,
                   Alerts.alert_message, Alerts.date_created, Alerts.status,
                   Messages.confidence
            FROM Alerts JOIN Messages ON Alerts.message_id = Messages.message_id
            JOIN Users ON Messages.sender_id = Users.user_id
            WHERE Alerts.status = 'unread'
            ORDER BY Alerts.alert_id DESC
            """
        )
        pending_alerts = cursor.fetchall()
        cursor.execute(
            """
            SELECT Alerts.alert_id, Alerts.message_id, Users.full_name, Alerts.alert_type,
                   Alerts.alert_message, Alerts.date_created, Alerts.status,
                   Messages.confidence
            FROM Alerts JOIN Messages ON Alerts.message_id = Messages.message_id
            JOIN Users ON Messages.sender_id = Users.user_id
            WHERE Alerts.status = 'reviewed'
            ORDER BY Alerts.alert_id DESC
            """
        )
        reviewed_alerts = cursor.fetchall()
    return render_template(
        "dashboard.html",
        total_users=total_users,
        students=students,
        lecturers=lecturers,
        restricted_users=restricted_users,
        banned_users=banned_users,
        total_messages=total_messages,
        total_alerts=total_alerts,
        unread_alerts=unread_alerts,
        cyberbullying_messages=cyberbullying_messages,
        normal_messages=normal_messages,
        total_reports=total_reports,
        average_confidence=average_confidence,
        result_breakdown=result_breakdown,
        daily_activity=daily_activity,
        recent_messages=recent_messages,
        pending_alerts=pending_alerts,
        reviewed_alerts=reviewed_alerts,
    )


@admin_bp.route("/mark-alert-read/<int:alert_id>", methods=["POST"])
def mark_alert_read(alert_id):
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute("UPDATE Alerts SET status = 'read' WHERE alert_id = %s", (alert_id,))
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/remove-restriction/<int:user_id>", methods=["POST"])
def remove_restriction(user_id):
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            UPDATE Users
            SET status = 'active'
            WHERE user_id = %s
              AND status = 'temporarily_restricted'
            """,
            (user_id,),
        )
        if cursor.rowcount == 0:
            return "The account is not currently temporarily restricted.", 400
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/unban-account/<int:user_id>", methods=["POST"])
def unban_account(user_id):
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            UPDATE Users
            SET status = 'active'
            WHERE user_id = %s AND status = 'banned'
            """,
            (user_id,),
        )
        if cursor.rowcount == 0:
            return "The account is not currently banned.", 400
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin-decision/<int:alert_id>", methods=["POST"])
def send_admin_decision(alert_id):
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    action = (request.form.get("action") or "notify_only").strip()
    valid_actions = {
        "notify_only",
        "warning",
        "temporary_restriction",
        "account_ban",
    }
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            SELECT Messages.message_id, Messages.sender_id,
                   Messages.detection_result, Messages.confidence
            FROM Alerts
            JOIN Messages ON Alerts.message_id = Messages.message_id
            WHERE Alerts.alert_id = %s
            """,
            (alert_id,),
        )
        alert = cursor.fetchone()
        if alert is None:
            return "The alert no longer exists.", 404

        message_id, sender_id, detection_result, confidence = alert
        decision = get_admin_decision(detection_result, confidence)
        if action not in valid_actions:
            return "Choose a valid administrative decision.", 400
        if not decision["is_cyberbullying"]:
            return "Only cyberbullying alerts can receive an administrative action.", 400

        enforcement = get_admin_enforcement_result(action, confidence)
        cursor.execute(
            "UPDATE Alerts SET status = 'reviewed' WHERE alert_id = %s",
            (alert_id,),
        )
        cursor.execute(
            "UPDATE Messages SET status = %s WHERE message_id = %s",
            (enforcement["status_update"], message_id),
        )
        if action == "account_ban":
            cursor.execute(
                "UPDATE Users SET status = 'banned' WHERE user_id = %s",
                (sender_id,),
            )
        elif action == "temporary_restriction":
            cursor.execute(
                "UPDATE Users SET status = 'temporarily_restricted' "
                "WHERE user_id = %s",
                (sender_id,),
            )
        elif action == "warning":
            cursor.execute(
                "UPDATE Users SET status = 'warning_issued' WHERE user_id = %s",
                (sender_id,),
            )

        cursor.execute(
            """
            INSERT INTO Notifications
            (user_id, notification_type, notification_message)
            VALUES (%s, %s, %s)
            """,
            (
                sender_id,
                "admin_decision",
                enforcement["notification_message"],
            ),
        )

    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/reports")
def reports():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT Reports.report_id, Reports.message_id,
                   COALESCE(Messages.message_text, Announcements.content,
                            DiscussionReplies.reply_text) AS reported_content,
                   Users.full_name, Reports.reason, Reports.date_reported,
                   Reports.action_taken, Reports.status,
                   sender.full_name, recipient.full_name,
                   Messages.detection_result, Messages.confidence,
                   Messages.status
            FROM Reports
            JOIN Users ON Reports.reported_by = Users.user_id
            LEFT JOIN Messages ON Reports.message_id = Messages.message_id
            LEFT JOIN Users sender ON Messages.sender_id = sender.user_id
            LEFT JOIN Users recipient ON Messages.recipient_id = recipient.user_id
            LEFT JOIN Announcements ON Reports.announcement_id = Announcements.announcement_id
            LEFT JOIN DiscussionReplies ON Reports.reply_id = DiscussionReplies.reply_id
            ORDER BY Reports.report_id DESC
            """
        )
        report_rows = cursor.fetchall()
    return render_template("reports.html", reports=report_rows)


@admin_bp.route("/admin-delete-reported-message", methods=["POST"])
def delete_reported_message():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    report_id = request.form.get("report_id", type=int)
    reason = (request.form.get("reason") or "").strip()
    if report_id is None or not reason:
        return "A report and deletion reason are required.", 400
    if len(reason) > 1000:
        return "Deletion reason must be 1000 characters or fewer.", 400
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            "SELECT message_id FROM Reports WHERE report_id = %s",
            (report_id,),
        )
        report = cursor.fetchone()
        if report is None or report[0] is None:
            return "This report does not contain an available message.", 404
        if not _delete_message_and_notify(cursor, report[0], reason):
            return "The reported message no longer exists.", 404
        cursor.execute(
            """
            UPDATE Reports SET action_taken = %s, status = %s
            WHERE report_id = %s
            """,
            ("Message deleted by administrator", "Resolved", report_id),
        )
    return redirect(url_for("admin.reports"))


@admin_bp.route("/update-report/<int:report_id>", methods=["POST"])
def update_report(report_id):
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            UPDATE Reports SET action_taken = %s, status = %s
            WHERE report_id = %s
            """,
            (request.form.get("action_taken"), request.form.get("status"), report_id),
        )
    return redirect(url_for("admin.reports"))
