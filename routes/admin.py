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
            SELECT u.user_id, u.full_name, u.institution_id, u.email, u.status,
                   n.notification_message
            FROM Users u
            LEFT JOIN Notifications n
              ON n.user_id = u.user_id
             AND n.notification_type = 'admin_decision'
             AND n.notification_id = (
                 SELECT MAX(notification_id)
                 FROM Notifications latest
                 WHERE latest.user_id = u.user_id
                   AND latest.notification_type = 'admin_decision'
             )
            WHERE LOWER(TRIM(u.status)) = 'temporarily_restricted'
            ORDER BY u.full_name ASC
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
    from decision_templates import build_formal_decision_notice

    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            SELECT Messages.message_id, Messages.sender_id,
                   Messages.detection_result, Messages.confidence,
                   Users.full_name, Users.institution_id, Users.email,
                   Messages.message_text, Messages.date_sent
            FROM Alerts
            JOIN Messages ON Alerts.message_id = Messages.message_id
            JOIN Users ON Messages.sender_id = Users.user_id
            WHERE Alerts.alert_id = %s
            """,
            (alert_id,),
        )
        alert = cursor.fetchone()
        if alert is None:
            return "The alert no longer exists.", 404

        (
            message_id,
            sender_id,
            detection_result,
            confidence,
            student_name,
            institution_id,
            student_email,
            message_text,
            date_sent,
        ) = alert

        decision = get_admin_decision(detection_result, confidence)
        if action not in valid_actions:
            return "Choose a valid administrative decision.", 400
        if not decision["is_cyberbullying"]:
            return "Only cyberbullying alerts can receive an administrative action.", 400

        notice = build_formal_decision_notice(
            student_name=student_name,
            institution_id=institution_id,
            student_email=student_email,
            action=action,
            message_excerpt=message_text,
            confidence=confidence,
            incident_date=date_sent,
            alert_id=alert_id,
            admin_name=session.get("admin_name", "Office of the Dean of Students"),
        )

        cursor.execute(
            "UPDATE Alerts SET status = 'reviewed' WHERE alert_id = %s",
            (alert_id,),
        )
        cursor.execute(
            "UPDATE Messages SET status = %s WHERE message_id = %s",
            (notice["status_update"], message_id),
        )
        if notice["account_status"] != "active":
            cursor.execute(
                "UPDATE Users SET status = %s WHERE user_id = %s",
                (notice["account_status"], sender_id),
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
                notice["formal_text"],
            ),
        )

    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/notice/<int:notification_id>")
def view_admin_notice(notification_id):
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()

    from decision_templates import notice_from_notification_row

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT n.notification_id, n.notification_message, n.date_created,
                   u.full_name, u.institution_id, u.email
            FROM Notifications n
            JOIN Users u ON n.user_id = u.user_id
            WHERE n.notification_id = %s
            """,
            (notification_id,),
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
        back_url=url_for("admin.admin_dashboard"),
    )


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


@admin_bp.route("/admin/report/print")
@admin_bp.route("/reports/print")
def print_admin_report():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()

    from datetime import datetime

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

    records = []
    flagged_count = 0
    clean_count = 0
    resolved_count = 0

    for r in report_rows:
        det = str(r[10] or "")
        is_cb = det.startswith("Cyberbullying")
        if is_cb:
            flagged_count += 1
        else:
            clean_count += 1

        stat = str(r[7] or "")
        if stat.lower() == "resolved":
            resolved_count += 1

        date_str = r[5].strftime("%b %d, %Y %H:%M") if hasattr(r[5], "strftime") else str(r[5] or "")

        records.append({
            "ref_id": f"RPT-{r[0]:04d}",
            "date_str": date_str,
            "sender": r[8] or "Anonymous / System",
            "recipient": r[9] or "Public Forum",
            "reported_by": r[3],
            "content": r[2] or "Content deleted",
            "reason": r[4],
            "is_cyberbullying": is_cb,
            "confidence": float(r[11]) if r[11] is not None else None,
            "action_taken": r[6],
            "status": r[7],
        })

    now = datetime.now()
    summary = {
        "total_items": len(records),
        "flagged_count": flagged_count,
        "clean_count": clean_count,
        "resolved_count": resolved_count,
    }

    return render_template(
        "printable_report.html",
        report_title="OFFICIAL CYBERBULLYING INCIDENT & MONITORING REPORT",
        report_reference=f"NISH/ADM/RPT-{now.strftime('%Y%m%d-%H%M')}",
        generated_at=now.strftime("%B %d, %Y &bull; %H:%M EAT"),
        user_name=session.get("admin_name", "System Administrator"),
        user_role="Institutional Administrator",
        summary=summary,
        records=records,
        back_url=url_for("admin.reports"),
    )


@admin_bp.route("/admin/students/print")
@admin_bp.route("/students/print")
def print_students():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()

    from datetime import datetime

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT user_id, full_name, institution_id, email, status, date_created
            FROM Users
            WHERE LOWER(role) = 'student'
            ORDER BY full_name ASC
            """
        )
        student_rows = cursor.fetchall()

    students = []
    active_count = 0
    restricted_count = 0
    banned_count = 0

    for idx, s in enumerate(student_rows, start=1):
        status = (s[4] or "active").strip().lower()
        if status == "active":
            active_count += 1
            display_status = "Active"
        elif status == "temporarily_restricted":
            restricted_count += 1
            display_status = "Restricted"
        elif status == "banned":
            banned_count += 1
            display_status = "Banned"
        else:
            active_count += 1
            display_status = status.capitalize()

        date_str = s[5].strftime("%b %d, %Y") if hasattr(s[5], "strftime") else str(s[5] or "N/A")

        students.append({
            "index": idx,
            "user_id": s[0],
            "full_name": s[1],
            "institution_id": s[2] or "Not provided",
            "email": s[3] or "Not provided",
            "status": display_status,
            "raw_status": status,
            "date_enrolled": date_str,
        })

    now = datetime.now()
    summary = {
        "total_students": len(students),
        "active_count": active_count,
        "restricted_count": restricted_count,
        "banned_count": banned_count,
    }

    return render_template(
        "printable_students.html",
        report_title="OFFICIAL ENROLLED STUDENTS DIRECTORY",
        report_reference=f"NISH/ADM/STU-{now.strftime('%Y%m%d-%H%M')}",
        generated_at=now.strftime("%B %d, %Y &bull; %H:%M EAT"),
        user_name=session.get("admin_name", "System Administrator"),
        user_role="Institutional Administrator",
        summary=summary,
        students=students,
        back_url=url_for("admin.admin_dashboard"),
    )


@admin_bp.route("/admin/lecturers/print")
@admin_bp.route("/lecturers/print")
def print_lecturers():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()

    from datetime import datetime

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT user_id, full_name, institution_id, email, role, status, date_created
            FROM Users
            WHERE LOWER(role) IN ('lecturer', 'teacher')
            ORDER BY full_name ASC
            """
        )
        lecturer_rows = cursor.fetchall()

    lecturers = []
    active_count = 0

    for idx, row in enumerate(lecturer_rows, start=1):
        status = (row[5] or "active").strip().lower()
        if status == "active":
            active_count += 1
            display_status = "Active"
        else:
            display_status = status.capitalize()

        date_str = row[6].strftime("%b %d, %Y") if hasattr(row[6], "strftime") else str(row[6] or "N/A")

        lecturers.append({
            "index": idx,
            "user_id": row[0],
            "full_name": row[1],
            "institution_id": row[2] or "Not provided",
            "email": row[3] or "Not provided",
            "role": (row[4] or "Lecturer").capitalize(),
            "status": display_status,
            "date_appointed": date_str,
        })

    now = datetime.now()
    summary = {
        "total_lecturers": len(lecturers),
        "active_count": active_count,
    }

    return render_template(
        "printable_lecturers.html",
        report_title="OFFICIAL FACULTY & LECTURERS DIRECTORY",
        report_reference=f"NISH/ADM/FAC-{now.strftime('%Y%m%d-%H%M')}",
        generated_at=now.strftime("%B %d, %Y &bull; %H:%M EAT"),
        user_name=session.get("admin_name", "System Administrator"),
        user_role="Institutional Administrator",
        summary=summary,
        lecturers=lecturers,
        back_url=url_for("admin.admin_dashboard"),
    )


@admin_bp.route("/admin/users/print")
@admin_bp.route("/users/print")
def print_all_users():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()

    from datetime import datetime

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT full_name, institution_id, email, role, status, date_created
            FROM Users
            ORDER BY role ASC, full_name ASC
            """
        )
        rows = cursor.fetchall()

    role_names = {"student": "Student", "teacher": "Lecturer", "lecturer": "Lecturer",
                  "administrator": "Administrator", "admin": "Administrator"}
    status_names = {"active": "Active", "temporarily_restricted": "Restricted", "banned": "Banned"}

    users = []
    counts = {"Student": 0, "Lecturer": 0, "Administrator": 0}
    for idx, row in enumerate(rows, start=1):
        role = role_names.get((row[3] or "").strip().lower(), (row[3] or "Unknown").capitalize())
        counts[role] = counts.get(role, 0) + 1
        status = (row[4] or "active").strip().lower()
        users.append({
            "index": idx,
            "full_name": row[0],
            "institution_id": row[1] or "Not provided",
            "email": row[2] or "Not provided",
            "role": role,
            "status": status_names.get(status, status.capitalize()),
            "date_registered": row[5].strftime("%b %d, %Y") if hasattr(row[5], "strftime") else str(row[5] or "N/A")[:10],
        })

    now = datetime.now()
    summary = {
        "total_users": len(users),
        "students": counts.get("Student", 0),
        "lecturers": counts.get("Lecturer", 0),
        "admins": counts.get("Administrator", 0),
    }

    return render_template(
        "printable_users.html",
        report_title="OFFICIAL REGISTERED USERS DIRECTORY",
        report_reference=f"NISH/ADM/USR-{now.strftime('%Y%m%d-%H%M')}",
        generated_at=now.strftime("%B %d, %Y &bull; %H:%M EAT"),
        user_name=session.get("admin_name", "System Administrator"),
        user_role="Institutional Administrator",
        summary=summary,
        users=users,
        back_url=url_for("admin.admin_dashboard"),
    )


@admin_bp.route("/admin/cyberbullying-messages/print")
@admin_bp.route("/messages/cyberbullying/print")
def print_cyberbullying_messages():
    if not session.get("admin_logged_in"):
        return _admin_login_redirect()

    from datetime import datetime

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT Messages.message_id, Messages.message_text,
                   sender.full_name, sender.institution_id,
                   recipient.full_name,
                   Messages.detection_result, Messages.confidence,
                   Messages.status, Messages.date_sent
            FROM Messages
            JOIN Users sender ON Messages.sender_id = sender.user_id
            LEFT JOIN Users recipient ON Messages.recipient_id = recipient.user_id
            WHERE Messages.detection_result LIKE 'Cyberbullying%'
            ORDER BY Messages.message_id DESC
            """
        )
        msg_rows = cursor.fetchall()

    records = []
    high_risk_count = 0
    unique_senders = set()
    actioned_count = 0

    for r in msg_rows:
        conf = float(r[6]) if r[6] is not None else 0.0
        if conf >= 0.85:
            high_risk_count += 1

        sender_name = r[2] or "Unknown Student"
        unique_senders.add(sender_name)

        status_val = str(r[7] or "checked").strip()
        if status_val.lower() in ("deleted", "restricted", "banned", "warning", "actioned"):
            actioned_count += 1

        date_str = r[8].strftime("%b %d, %Y %H:%M") if hasattr(r[8], "strftime") else str(r[8] or "")

        records.append({
            "message_id": r[0],
            "ref_id": f"CBM-{r[0]:04d}",
            "date_str": date_str,
            "sender_name": sender_name,
            "sender_id_num": r[3] or "N/A",
            "recipient_name": r[4] or "Public Forum / Broadcast",
            "message_text": r[1],
            "detection_result": r[5],
            "confidence": conf,
            "status": status_val,
        })

    now = datetime.now()
    summary = {
        "total_flagged": len(records),
        "high_risk_count": high_risk_count,
        "unique_senders": len(unique_senders),
        "actioned_count": actioned_count,
    }

    return render_template(
        "printable_cyberbullying_messages.html",
        report_title="OFFICIAL AI CYBERBULLYING DETECTION & FLAGGED MESSAGES LOG",
        report_reference=f"NISH/ADM/CBM-{now.strftime('%Y%m%d-%H%M')}",
        generated_at=now.strftime("%B %d, %Y &bull; %H:%M EAT"),
        user_name=session.get("admin_name", "System Administrator"),
        user_role="Institutional Administrator",
        summary=summary,
        records=records,
        back_url=url_for("admin.admin_dashboard"),
    )



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
