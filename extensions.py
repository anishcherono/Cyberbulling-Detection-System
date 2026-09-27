import hmac
import logging
import os
import secrets
from contextlib import contextmanager

from dotenv import load_dotenv
import mysql.connector
from flask import request
from werkzeug.security import check_password_hash

load_dotenv()

MESSAGE_MAX_LENGTH = 2000
REPORT_REASON_MAX_LENGTH = 1000
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def configure_app(app):
    app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv(
        "FLASK_SESSION_COOKIE_SECURE", "0"
    ) == "1"

    @app.context_processor
    def csrf_context():
        return {"csrf_token": get_csrf_token}

    @app.before_request
    def validate_csrf():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            submitted = request.form.get("csrf_token", "")
            expected = request.cookies.get("csrf_token", "")
            if not submitted or not expected or not hmac.compare_digest(
                submitted, expected
            ):
                from flask import abort

                abort(400, description="Invalid or missing CSRF token.")


def get_csrf_token():
    from flask import current_app

    token = request.cookies.get("csrf_token")
    if token:
        return token
    token = secrets.token_urlsafe(32)
    current_app.after_request_funcs.setdefault(None, []).append(
        lambda response: _set_csrf_cookie(response, token)
    )
    return token


def _set_csrf_cookie(response, token):
    response.set_cookie(
        "csrf_token",
        token,
        httponly=True,
        samesite="Lax",
        secure=os.getenv("FLASK_SESSION_COOKIE_SECURE", "0") == "1",
    )
    return response


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "Cyberbulling_system"),
        use_pure=True,
    )


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


def verify_password(password, stored_password):
    if not isinstance(password, str) or not isinstance(stored_password, str):
        return False
    try:
        if check_password_hash(stored_password, password):
            return True
    except (ValueError, TypeError):
        pass
    return hmac.compare_digest(password, stored_password)


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
