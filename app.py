from flask import Flask, render_template, request, session, redirect, url_for
import mysql.connector
from ai_detector import detect_with_ai

app = Flask(__name__)

app.secret_key = "cyberbullying-secret-key"


def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="anish123",
        database="Cyberbulling_system",
        use_pure=True
    )


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT user_id, full_name, username, password, role
            FROM Users
            WHERE username = %s
        """, (username,))

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user is not None:

            stored_password = user[3]
            role = user[4]

            if password == stored_password and role == "Administrator":

                session["admin_logged_in"] = True
                session["admin_user_id"] = user[0]
                session["admin_name"] = user[1]

                return redirect(url_for("dashboard"))

        return """
        <h2>Invalid username or password</h2>
        <a href="/login">Try Again</a>
        """

    return render_template("login.html")


@app.route("/student-login", methods=["GET", "POST"])
def student_login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT user_id, full_name, username, password, role
            FROM Users
            WHERE username = %s
            AND role = 'Student'
        """, (username,))

        student = cursor.fetchone()

        cursor.close()
        connection.close()

        if student is not None:

            stored_password = student[3]

            if password == stored_password:

                session["student_logged_in"] = True
                session["student_user_id"] = student[0]
                session["student_name"] = student[1]

                return redirect(url_for("student_dashboard"))

        return """
        <h2>Invalid student username or password</h2>
        <a href="/student-login">Try Again</a>
        """

    return render_template("student_login.html")


@app.route("/student-dashboard")
def student_dashboard():

    if not session.get("student_logged_in"):
        return redirect(url_for("student_login"))

    student_id = session.get("student_user_id")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            message_id,
            message_text,
            detection_result,
            confidence,
            date_sent
        FROM Messages
        WHERE sender_id = %s
        ORDER BY message_id DESC
        LIMIT 10
    """, (student_id,))

    posts = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "student_dashboard.html",
        student_name=session.get("student_name"),
        posts=posts
    )


@app.route("/student-post", methods=["POST"])
def student_post():

    if not session.get("student_logged_in"):
        return redirect(url_for("student_login"))

    message = request.form.get("message")

    student_id = session.get("student_user_id")

    result, confidence = detect_with_ai(message)

    print("Student ID:", student_id)
    print("Student message:", message)
    print("AI Detection result:", result)
    print("AI Confidence:", confidence)

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO Messages
        (sender_id, message_text, detection_result, confidence, status)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        student_id,
        message,
        result,
        confidence,
        "checked"
    ))

    message_id = cursor.lastrowid

    if "Cyberbullying" in result:

        cursor.execute("""
            INSERT INTO Alerts
            (message_id, alert_type, alert_message, status)
            VALUES (%s, %s, %s, %s)
        """, (
            message_id,
            "Cyberbullying",
            "Cyberbullying detected in a student post.",
            "unread"
        ))

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("student_dashboard"))


@app.route("/student-logout")
def student_logout():

    session.pop("student_logged_in", None)
    session.pop("student_user_id", None)
    session.pop("student_name", None)

    return redirect(url_for("student_login"))


@app.route("/check", methods=["POST"])
def check_message():

    message = request.form.get("message")

    print("Message received:", message)

    result, confidence = detect_with_ai(message)

    print("AI Detection result:", result)
    print("AI Confidence:", confidence)

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO Messages
        (sender_id, message_text, detection_result, confidence, status)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        1,
        message,
        result,
        confidence,
        "checked"
    ))

    message_id = cursor.lastrowid

    if "Cyberbullying" in result:

        cursor.execute("""
            INSERT INTO Alerts
            (message_id, alert_type, alert_message, status)
            VALUES (%s, %s, %s, %s)
        """, (
            message_id,
            result,
            "Cyberbullying detected in a message.",
            "unread"
        ))

    connection.commit()

    cursor.close()
    connection.close()

    return render_template(
        "result.html",
        message=message,
        result=result,
        confidence=confidence,
        message_id=message_id
    )


@app.route("/dashboard")
def dashboard():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    connection = get_connection()
    cursor = connection.cursor()

    # Total users
    cursor.execute("SELECT COUNT(*) FROM Users")
    total_users = cursor.fetchone()[0]

    # Total messages
    cursor.execute("SELECT COUNT(*) FROM Messages")
    total_messages = cursor.fetchone()[0]

    # Total alerts
    cursor.execute("SELECT COUNT(*) FROM Alerts")
    total_alerts = cursor.fetchone()[0]

    # Analytics: All cyberbullying messages
    cursor.execute("""
        SELECT COUNT(*)
        FROM Messages
        WHERE detection_result LIKE 'Cyberbullying%'
    """)
    cyberbullying_messages = cursor.fetchone()[0]

    # Analytics: Normal messages
    cursor.execute("""
        SELECT COUNT(*)
        FROM Messages
        WHERE detection_result = 'Not Cyberbullying'
    """)
    normal_messages = cursor.fetchone()[0]

    # Unread alerts
    cursor.execute("""
        SELECT COUNT(*)
        FROM Alerts
        WHERE status = 'unread'
    """)
    unread_alerts = cursor.fetchone()[0]

    # Recent student messages
    cursor.execute("""
        SELECT
            Messages.message_id,
            Users.full_name,
            Messages.message_text,
            Messages.detection_result,
            Messages.confidence,
            Messages.status
        FROM Messages
        JOIN Users
            ON Messages.sender_id = Users.user_id
        ORDER BY Messages.message_id DESC
        LIMIT 10
    """)

    recent_messages = cursor.fetchall()

    # Recent cyberbullying alerts
    cursor.execute("""
        SELECT
            Alerts.alert_id,
            Alerts.message_id,
            Users.full_name,
            Alerts.alert_type,
            Alerts.alert_message,
            Alerts.date_created,
            Alerts.status
        FROM Alerts
        JOIN Messages
            ON Alerts.message_id = Messages.message_id
        JOIN Users
            ON Messages.sender_id = Users.user_id
        ORDER BY Alerts.alert_id DESC
        LIMIT 10
    """)

    recent_alerts = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "dashboard.html",
        total_users=total_users,
        total_messages=total_messages,
        total_alerts=total_alerts,
        unread_alerts=unread_alerts,
        cyberbullying_messages=cyberbullying_messages,
        normal_messages=normal_messages,
        recent_messages=recent_messages,
        recent_alerts=recent_alerts
    )


@app.route("/mark-alert-read/<int:alert_id>", methods=["POST"])
def mark_alert_read(alert_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE Alerts
        SET status = 'read'
        WHERE alert_id = %s
    """, (alert_id,))

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("dashboard"))


@app.route("/reports")
def reports():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            Reports.report_id,
            Reports.message_id,
            Users.full_name,
            Reports.reason,
            Reports.date_reported,
            Reports.action_taken,
            Reports.status
        FROM Reports
        JOIN Users
            ON Reports.reported_by = Users.user_id
        ORDER BY Reports.report_id DESC
    """)

    reports = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "reports.html",
        reports=reports
    )


@app.route("/report", methods=["POST"])
def report_message():

    if not session.get("student_logged_in"):
        return redirect(url_for("student_login"))

    message_id = request.form.get("message_id")
    reason = request.form.get("reason")

    student_id = session.get("student_user_id")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO Reports
        (message_id, reported_by, reason, action_taken, status)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        message_id,
        student_id,
        reason,
        "Pending",
        "Pending"
    ))

    connection.commit()

    cursor.close()
    connection.close()

    return """
    <h2>Message Reported Successfully</h2>
    <p>The message has been reported to the administrator.</p>
    <a href="/student-dashboard">Back to Student Dashboard</a>
    """


@app.route("/update-report/<int:report_id>", methods=["POST"])
def update_report(report_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    action_taken = request.form.get("action_taken")
    status = request.form.get("status")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE Reports
        SET action_taken = %s,
            status = %s
        WHERE report_id = %s
    """, (
        action_taken,
        status,
        report_id
    ))

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("reports"))


@app.route("/logout")
def logout():

    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)
    session.pop("admin_name", None)

    return redirect(url_for("login"))


@app.errorhandler(Exception)
def handle_error(error):

    return f"Error: {error}", 500


if __name__ == "__main__":

    import webbrowser
    import threading
    import os

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
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
        ]

        for path in firefox_paths:

            if os.path.exists(path):

                webbrowser.register(
                    "firefox",
                    None,
                    webbrowser.BackgroundBrowser(path)
                )

                webbrowser.get("firefox").open(url)

                return

        webbrowser.open(url)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":

        threading.Timer(
            1.5,
            open_browser
        ).start()

    app.run(debug=True)