from datetime import datetime
import os
import sqlite3
from contextlib import contextmanager

from dotenv import load_dotenv
from flask import request
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

MESSAGE_MAX_LENGTH = 2000
REPORT_REASON_MAX_LENGTH = 1000
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.getenv("SQLITE_DB_PATH", "cyberbullying.db"),
)


sqlite3.register_converter(
    "TIMESTAMP",
    lambda val: datetime.fromisoformat(val.decode("utf-8").strip()),
)


def configure_app(app):
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "nish-institution-secret-key")

    @app.context_processor
    def csrf_context():
        return {"csrf_token": lambda: ""}


def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def database_cursor(commit=False):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        yield connection, cursor
        if commit:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        close_database(connection, cursor)


def init_db():
    """Create all SQLite tables if they do not exist."""
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name VARCHAR(200) NOT NULL,
                institution_id VARCHAR(100) NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                username VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'active',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INT NOT NULL,
                recipient_id INT NULL,
                message_text TEXT NOT NULL,
                detection_result VARCHAR(100) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'checked',
                date_sent TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES Users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (recipient_id) REFERENCES Users(user_id) ON DELETE SET NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Announcements (
                announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INT NOT NULL,
                title VARCHAR(150) NOT NULL,
                content TEXT NOT NULL,
                detection_result VARCHAR(100) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'published',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES Users(user_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS DiscussionReplies (
                reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INT NULL,
                announcement_id INT NULL,
                author_id INT NOT NULL,
                reply_text TEXT NOT NULL,
                detection_result VARCHAR(100) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'checked',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES Messages(message_id) ON DELETE CASCADE,
                FOREIGN KEY (announcement_id) REFERENCES Announcements(announcement_id) ON DELETE CASCADE,
                FOREIGN KEY (author_id) REFERENCES Users(user_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INT NOT NULL,
                alert_type VARCHAR(50) NOT NULL,
                alert_message TEXT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'unread',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES Messages(message_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INT NULL,
                announcement_id INT NULL,
                reply_id INT NULL,
                reported_by INT NOT NULL,
                reason TEXT NOT NULL,
                action_taken VARCHAR(100) NOT NULL DEFAULT 'Pending',
                status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                date_reported TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES Messages(message_id) ON DELETE SET NULL,
                FOREIGN KEY (announcement_id) REFERENCES Announcements(announcement_id) ON DELETE SET NULL,
                FOREIGN KEY (reported_by) REFERENCES Users(user_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS MessageInboxDeletions (
                user_id INT NOT NULL,
                message_id INT NOT NULL,
                date_deleted TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, message_id),
                FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES Messages(message_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                notification_message TEXT NOT NULL,
                is_read BOOLEAN NOT NULL DEFAULT FALSE,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Donations (
                donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                donor_name VARCHAR(150) NOT NULL DEFAULT 'Anonymous',
                phone_number VARCHAR(20) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                merchant_request_id VARCHAR(100) NULL,
                checkout_request_id VARCHAR(100) UNIQUE NULL,
                mpesa_receipt_number VARCHAR(50) NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
                result_code INT NULL,
                result_desc VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def ensure_default_admin():
    with database_cursor() as (_, cursor):
        cursor.execute(
            "SELECT user_id FROM Users WHERE LOWER(email) = ? OR LOWER(username) = ?",
            ("admin@admin.nish.edu", "admin@admin.nish.edu"),
        )
        if cursor.fetchone() is None:
            with database_cursor(commit=True) as (_, insert_cursor):
                insert_cursor.execute(
                    """
                    INSERT INTO Users (full_name, institution_id, email, username, password, role, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "System Administrator",
                        "ADM-2026-0001",
                        "admin@admin.nish.edu",
                        "admin@admin.nish.edu",
                        generate_password_hash("admin123"),
                        "Administrator",
                        "active",
                    ),
                )


def verify_password(password, stored_password):
    if not isinstance(password, str) or not isinstance(stored_password, str):
        return False
    try:
        if check_password_hash(stored_password, password):
            return True
    except (ValueError, TypeError):
        pass
    return password == stored_password


def get_message_from_request():
    message = (request.form.get("message") or "").strip()
    if not message:
        return None, "Message cannot be empty."
    if len(message) > MESSAGE_MAX_LENGTH:
        return None, f"Message must be {MESSAGE_MAX_LENGTH} characters or fewer."
    return message, None


def close_database(connection, cursor):
    if cursor is not None:
        cursor.close()
    if connection is not None:
        connection.close()


def normalize_role(role):
    normalized = str(role or "").strip().lower()
    if normalized == "teacher":
        return "Lecturer"
    return normalized.title()


def is_account_blocked(status):
    return str(status or "").strip().lower() in {"banned", "temporarily_restricted"}


def format_blocked_notification(notification_message, blocked_message):
    return f"{notification_message} Blocked message: {blocked_message}"


def get_delivery_decision(detection_result, confidence, destination_user_id):
    is_cyberbullying = str(detection_result).startswith("Cyberbullying")
    if is_cyberbullying:
        confidence_pct = float(confidence) * 100
        return {
            "delivery_allowed": False,
            "recipient_id": None,
            "status": "blocked_admin_review",
            "notification_message": (
                f"This message was detected as cyberbullying by AI at "
                f"{confidence_pct:.2f}%. It was blocked and not delivered."
            ),
        }
    return {
        "delivery_allowed": True,
        "recipient_id": destination_user_id,
        "status": "checked",
        "notification_message": None,
    }


def get_admin_decision(detection_result, confidence):
    return {
        "action": "admin_review_required",
        "auto_ban": False,
        "is_cyberbullying": str(detection_result).startswith("Cyberbullying"),
    }


DECISION_METADATA = {
    "warning": {
        "title": "FORMAL DISCIPLINARY WARNING",
        "subtitle": "Notice of Violation of Institutional Digital Communication Policy",
        "severity": "Moderate",
        "policy_clause": "Section 4.2 (Anti-Cyberbullying and Harassment Provisions)",
        "sanction_summary": "Formal warning recorded in student disciplinary profile; account remains active.",
        "directive": (
            "You are hereby officially warned regarding your digital communication. "
            "Please ensure all future messages follow institutional guidelines."
        ),
        "status_update": "warning_issued",
        "account_status": "warning_issued",
    },
    "temporary_restriction": {
        "title": "NOTICE OF TEMPORARY ACCOUNT RESTRICTION",
        "subtitle": "Order of Immediate Communication Suspension Pending Conduct Review",
        "severity": "High",
        "policy_clause": "Section 4.2 & Section 5.1 (Severe Hostile Digital Conduct)",
        "sanction_summary": "Portal communication privileges temporarily suspended.",
        "directive": (
            "Your institutional portal account has been placed under a temporary restriction. "
            "Please contact the Office of Student Counseling & Welfare for account review."
        ),
        "status_update": "restricted",
        "account_status": "temporarily_restricted",
    },
    "account_ban": {
        "title": "NOTICE OF ACCOUNT EXPULSION & ACCESS REVOCATION",
        "subtitle": "Final Administrative Sanction for Critical Cyberbullying Breach",
        "severity": "Critical",
        "policy_clause": "Section 4.2, Section 6.0 (Zero-Tolerance Cyberbullying Policy)",
        "sanction_summary": "Indefinite suspension of student communication portal privileges.",
        "directive": (
            "Following review of critical cyberbullying conduct, the Administration has suspended "
            "your account access on the Nish Institution Digital Communication Platform."
        ),
        "status_update": "banned",
        "account_status": "banned",
    },
    "notify_only": {
        "title": "ADMINISTRATIVE CONTENT ADVISORY",
        "subtitle": "Informational Notification of Content Moderation Review",
        "severity": "Low / Advisory",
        "policy_clause": "Section 3.1 (Digital Etiquette and Responsible Communication)",
        "sanction_summary": "Content reviewed; no disciplinary sanctions applied.",
        "directive": (
            "Administration has reviewed flagged content from your account. "
            "Please remember to keep all digital communications respectful."
        ),
        "status_update": "reviewed",
        "account_status": "active",
    },
}


def build_formal_decision_notice(
    student_name,
    institution_id,
    student_email,
    action,
    message_excerpt,
    confidence,
    incident_date=None,
    alert_id=None,
    admin_name="Office of Student Welfare & Discipline",
):
    action_key = action.strip().lower() if action else "notify_only"
    meta = DECISION_METADATA.get(action_key, DECISION_METADATA["notify_only"])
    now = datetime.now()
    case_ref = f"NISH/DISC/{now.strftime('%Y')}/AL-{alert_id or 1001:04d}"
    inst_id = institution_id or "Not Registered"
    conf_pct = float(confidence) * 100 if confidence is not None else 0.0
    inc_date_str = (
        incident_date.strftime("%B %d, %Y at %H:%M")
        if hasattr(incident_date, "strftime")
        else str(incident_date or now.strftime("%B %d, %Y"))
    )
    formal_text = (
        f"--- OFFICIAL ADMINISTRATIVE DECISION ---\n"
        f"REF: {case_ref}\n"
        f"ISSUED TO: {student_name} (ID: {inst_id}) | {student_email}\n"
        f"DATE: {now.strftime('%B %d, %Y')}\n"
        f"DECISION: {meta['title']}\n"
        f"POLICY: {meta['policy_clause']}\n"
        f"INCIDENT: Flagged content sent on {inc_date_str} (AI Detection: {conf_pct:.2f}%)\n"
        f"SANCTION: {meta['sanction_summary']}\n\n"
        f"DIRECTIVE:\n{meta['directive']}\n\n"
        f"RIGHT OF APPEAL: You have the right to appeal within seven (7) academic days.\n"
        f"AUTHORITY: {admin_name}, Nish Institution."
    )
    return {
        "case_ref": case_ref,
        "action": action_key,
        "title": meta["title"],
        "subtitle": meta["subtitle"],
        "severity": meta["severity"],
        "policy_clause": meta["policy_clause"],
        "sanction_summary": meta["sanction_summary"],
        "directive": meta["directive"],
        "status_update": meta["status_update"],
        "account_status": meta["account_status"],
        "student_name": student_name,
        "institution_id": inst_id,
        "student_email": student_email,
        "message_excerpt": message_excerpt or "[Flagged communication]",
        "confidence_pct": conf_pct,
        "incident_date_str": inc_date_str,
        "decision_date_str": now.strftime("%B %d, %Y"),
        "admin_authority": admin_name,
        "formal_text": formal_text,
    }


def notice_from_notification_row(
    notification_id, raw_text, date_created, student_name, institution_id, email
):
    text = str(raw_text or "")
    ref = f"NISH/DISC/NOTICE-{notification_id:04d}"
    title = "OFFICIAL DISCIPLINARY DECISION"
    subtitle = "Formal Notice of Conduct Review"
    severity = "Formal Review"
    policy = "Section 4.2 (Anti-Cyberbullying Policy)"
    sanction = "Administrative decision on record."
    directive = text

    for line in text.splitlines():
        if line.startswith("REF:"):
            ref = line.replace("REF:", "").strip()
        elif line.startswith("DECISION:"):
            title = line.replace("DECISION:", "").strip()
        elif line.startswith("POLICY:"):
            policy = line.replace("POLICY:", "").strip()
        elif line.startswith("SANCTION:"):
            sanction = line.replace("SANCTION:", "").strip()

    if "BAN" in title.upper() or "EXPULSION" in title.upper():
        severity = "Critical"
    elif "RESTRICTION" in title.upper():
        severity = "High"
    elif "WARNING" in title.upper():
        severity = "Moderate"

    if "DIRECTIVE:" in text:
        after_dir = text.split("DIRECTIVE:")[1]
        directive = (
            after_dir.split("RIGHT OF APPEAL:")[0].strip()
            if "RIGHT OF APPEAL:" in after_dir
            else after_dir.strip()
        )

    date_str = (
        date_created.strftime("%B %d, %Y")
        if hasattr(date_created, "strftime")
        else str(date_created or "Recent")
    )
    return {
        "case_ref": ref,
        "title": title,
        "subtitle": subtitle,
        "severity": severity,
        "policy_clause": policy,
        "sanction_summary": sanction,
        "directive": directive,
        "student_name": student_name,
        "institution_id": institution_id or "Not Registered",
        "student_email": email,
        "message_excerpt": "[Archived incident record]",
        "confidence_pct": 90.0,
        "incident_date_str": date_str,
        "decision_date_str": date_str,
        "admin_authority": "Office of Student Affairs & Conduct",
        "formal_text": text,
    }