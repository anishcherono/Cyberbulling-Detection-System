import os
import threading
import webbrowser

from dotenv import load_dotenv
from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

from extensions import (
    configure_app,
    database_cursor,
    ensure_discussion_schema,
    ensure_messaging_schema,
)
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.discussion import discussion_bp
from routes.student import student_bp
from routes.teacher import teacher_bp

load_dotenv()


def create_app():
    application = Flask(__name__)
    configure_app(application)
    ensure_discussion_schema()
    ensure_messaging_schema()
    application.register_blueprint(auth_bp)
    application.register_blueprint(student_bp)
    application.register_blueprint(teacher_bp)
    application.register_blueprint(admin_bp)
    application.register_blueprint(discussion_bp)

    @application.route("/")
    def home():
        with database_cursor() as (_, cursor):
            cursor.execute("SELECT COUNT(*) FROM Messages")
            total_messages = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM Messages "
                "WHERE detection_result LIKE 'Cyberbullying%'"
            )
            cyberbullying_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM Messages "
                "WHERE detection_result = 'Not Cyberbullying'"
            )
            not_cyberbullying_count = cursor.fetchone()[0]
        detection_rate = (
            round(cyberbullying_count / total_messages * 100, 1)
            if total_messages
            else 0
        )
        return render_template(
            "index.html",
            total_messages=total_messages,
            cyberbullying_count=cyberbullying_count,
            not_cyberbullying_count=not_cyberbullying_count,
            detection_rate=detection_rate,
        )

    @application.errorhandler(Exception)
    def handle_error(error):
        if isinstance(error, HTTPException):
            return error
        application.logger.exception("Unhandled application error", exc_info=error)
        return "An internal server error occurred.", 500

    return application


app = create_app()


if __name__ == "__main__":
    url = "http://127.0.0.1:5000/"
    print("")
    print("==============================================")
    print("        NISH INSTITUTION PORTAL")
    print("==============================================")
    print("")
    print("System is running on:")
    print("Home:             http://127.0.0.1:5000/")
    print("Student Login:    http://127.0.0.1:5000/student-login")
    print("Admin Login:      http://127.0.0.1:5000/login")
    print("Student Portal:   http://127.0.0.1:5000/student-dashboard")
    print("Admin Dashboard:  http://127.0.0.1:5000/dashboard")
    print("Reports:          http://127.0.0.1:5000/reports")
    print("")
    print("Opening Nish Institution home page in Firefox...")
    print("==============================================")
    print("")

    def open_browser():
        firefox_paths = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ]
        for path in firefox_paths:
            if os.path.exists(path):
                webbrowser.register("firefox", None, webbrowser.BackgroundBrowser(path))
                webbrowser.get("firefox").open(url)
                return
        webbrowser.open(url)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.5, open_browser).start()
    app.run(debug=True)
