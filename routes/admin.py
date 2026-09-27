from flask import Blueprint, redirect, render_template, request, session, url_for

from extensions import database_cursor

admin_bp = Blueprint("admin", __name__)


def _admin_login_redirect():
    return redirect(url_for("auth.admin_login"))


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
                   Messages.detection_result, Messages.confidence, Messages.status
            FROM Messages JOIN Users ON Messages.sender_id = Users.user_id
            ORDER BY Messages.message_id DESC LIMIT 10
            """
        )
        recent_messages = cursor.fetchall()
        cursor.execute(
            """
            SELECT Alerts.alert_id, Alerts.message_id, Users.full_name, Alerts.alert_type,
                   Alerts.alert_message, Alerts.date_created, Alerts.status
            FROM Alerts JOIN Messages ON Alerts.message_id = Messages.message_id
            JOIN Users ON Messages.sender_id = Users.user_id
            ORDER BY Alerts.alert_id DESC LIMIT 10
            """
        )
        recent_alerts = cursor.fetchall()
    return render_template(
        "dashboard.html",
        total_users=total_users,
        students=students,
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
        recent_alerts=recent_alerts,
    )


@admin_bp.route("/mark-alert-read/<int:alert_id>", methods=["POST"])
def mark_alert_read(alert_id):
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute("UPDATE Alerts SET status = 'read' WHERE alert_id = %s", (alert_id,))
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/reports")
def reports():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()
    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT Reports.report_id, Reports.message_id, Users.full_name, Reports.reason,
                   Reports.date_reported, Reports.action_taken, Reports.status
            FROM Reports JOIN Users ON Reports.reported_by = Users.user_id
            ORDER BY Reports.report_id DESC
            """
        )
        report_rows = cursor.fetchall()
    return render_template("reports.html", reports=report_rows)


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
