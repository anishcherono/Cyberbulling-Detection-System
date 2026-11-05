from datetime import datetime
import os
import re
import urllib.parse
from contextlib import contextmanager

from dotenv import load_dotenv
from flask import request
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

MESSAGE_MAX_LENGTH = 2000
REPORT_REASON_MAX_LENGTH = 1000

DATABASE_URL = os.getenv("DATABASE_URL", "mysql://root:anish123@localhost:3306/Cyberbulling_system")


def parse_database_url(url):
    parsed = urllib.parse.urlparse(url)
    return {
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "database": parsed.path.lstrip("/") or "Cyberbulling_system",
    }


def configure_app(app):
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "nish-institution-secret-key")

    @app.context_processor
    def csrf_context():
        return {"csrf_token": lambda: ""}


def ensure_database_exists():
    """Ensure the target MySQL schema exists before connecting."""
    db_config = parse_database_url(DATABASE_URL)
    db_name = db_config["database"]
    try:
        conn = mysql.connector.connect(
            host=db_config["host"],
            user=db_config["user"],
            password=db_config["password"],
            port=db_config["port"],
            autocommit=True,
        )
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cur.close()
        conn.close()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Could not auto-create database '%s': %s", db_name, exc)


def get_connection():
    db_config = parse_database_url(DATABASE_URL)
    try:
        conn = mysql.connector.connect(
            host=db_config["host"],
            user=db_config["user"],
            password=db_config["password"],
            database=db_config["database"],
            port=db_config["port"],
            autocommit=False,
        )
        return conn
    except mysql.connector.Error as err:
        # If database does not exist (1049), auto-create and reconnect
        if err.errno == 1049:
            ensure_database_exists()
            conn = mysql.connector.connect(
                host=db_config["host"],
                user=db_config["user"],
                password=db_config["password"],
                database=db_config["database"],
                port=db_config["port"],
                autocommit=False,
            )
            return conn
        raise


class MySQLCursorWrapper:
    """Transparent cursor wrapper providing compatibility for queries."""

    def __init__(self, cursor):
        self._cursor = cursor

    def _convert_sql(self, sql):
        # Convert any strftime('...', col) to DATE_FORMAT(col, '...')
        converted = re.sub(
            r"strftime\s*\(\s*'%Y-%m-%d\s+%H:%M'\s*,\s*([a-zA-Z0-9_.]+)\s*\)",
            r"DATE_FORMAT(\1, '%Y-%m-%d %H:%i')",
            sql,
            flags=re.IGNORECASE,
        )
        converted = re.sub(
            r"strftime\s*\(\s*'%Y-%m-%d'\s*,\s*([a-zA-Z0-9_.]+)\s*\)",
            r"DATE_FORMAT(\1, '%Y-%m-%d')",
            converted,
            flags=re.IGNORECASE,
        )
        converted = re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT IGNORE", converted, flags=re.IGNORECASE)
        converted = converted.replace("?", "%s")
        return converted

    def execute(self, sql, params=None):
        sql = self._convert_sql(sql)
        if params is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        sql = self._convert_sql(sql)
        return self._cursor.executemany(sql, seq_of_params)

    def __getattr__(self, item):
        return getattr(self._cursor, item)


@contextmanager
def database_cursor(commit=False):
    connection = get_connection()
    raw_cursor = connection.cursor()
    cursor = MySQLCursorWrapper(raw_cursor)
    try:
        yield connection, cursor
        if commit:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        close_database(connection, raw_cursor)


def init_db():
    """Ensure all MySQL tables exist."""
    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(200) NOT NULL,
                institution_id VARCHAR(100) NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                username VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'active',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Messages (
                message_id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                recipient_id INT NULL,
                message_text TEXT NOT NULL,
                detection_result VARCHAR(100) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'checked',
                date_sent TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES Users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (recipient_id) REFERENCES Users(user_id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Announcements (
                announcement_id INT AUTO_INCREMENT PRIMARY KEY,
                teacher_id INT NOT NULL,
                title VARCHAR(150) NOT NULL,
                content TEXT NOT NULL,
                detection_result VARCHAR(100) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'published',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES Users(user_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS DiscussionReplies (
                reply_id INT AUTO_INCREMENT PRIMARY KEY,
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Alerts (
                alert_id INT AUTO_INCREMENT PRIMARY KEY,
                message_id INT NOT NULL,
                alert_type VARCHAR(50) NOT NULL,
                alert_message TEXT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'unread',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES Messages(message_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Reports (
                report_id INT AUTO_INCREMENT PRIMARY KEY,
                message_id INT NULL,
                announcement_id INT NULL,
                reply_id INT NULL,
                reported_by INT NOT NULL,
                reason TEXT NOT NULL,
                action_taken VARCHAR(100) NOT NULL DEFAULT 'Pending',
                status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                date_reported TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES Messages(message_id) ON DELETE SET NULL,
                FOREIGN KEY (announcement_id) REFERENCES Announcements(announcement_id) ON DELETE CASCADE,
                FOREIGN KEY (reply_id) REFERENCES DiscussionReplies(reply_id) ON DELETE CASCADE,
                FOREIGN KEY (reported_by) REFERENCES Users(user_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Notifications (
                notification_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                notification_message TEXT NOT NULL,
                is_read BOOLEAN NOT NULL DEFAULT FALSE,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Donations (
                donation_id INT AUTO_INCREMENT PRIMARY KEY,
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_donations_status (status),
                INDEX idx_donations_checkout (checkout_request_id),
                INDEX idx_donations_merchant (merchant_request_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
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
        try:
            cursor.fetchall()
        except Exception:
            pass
        try:
            cursor.close()
        except Exception:
            pass
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass


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