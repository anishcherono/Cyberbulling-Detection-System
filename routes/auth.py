from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from extensions import database_cursor, verify_password
from message_policy import is_account_blocked, is_banned_status

auth_bp = Blueprint("auth", __name__)
STUDENT_EMAIL_DOMAIN = "@students.nish.edu"
LECTURER_EMAIL_DOMAIN = "@lecturers.nish.edu"


def _registration_data():
    return {
        "full_name": (request.form.get("full_name") or "").strip(),
        "institution_id": (request.form.get("institution_id") or "").strip(),
        "email": (request.form.get("email") or "").strip().lower(),
        "password": request.form.get("password") or "",
        "confirm_password": request.form.get("confirm_password") or "",
    }


def _empty_registration_data():
    return {
        "full_name": "",
        "institution_id": "",
        "email": "",
        "password": "",
        "confirm_password": "",
    }


def _login_identifier():
    return (
        request.form.get("identifier")
        or request.form.get("username")
        or ""
    ).strip().lower()


def _find_user(identifier, role, include_restricted=False):
    status_filter = (
        ""
        if include_restricted
        else "AND status NOT IN ('banned', 'temporarily_restricted')"
    )
    with database_cursor() as (_, cursor):
        cursor.execute(
            f"""
            SELECT user_id, full_name, username, password, role, status
            FROM Users
            WHERE (LOWER(email) = %s OR LOWER(username) = %s)
              AND LOWER(role) = %s
              {status_filter}
            """,
            (identifier, identifier, role.lower()),
        )
        return cursor.fetchone()


def _set_authenticated_session(role, user):
    for key in (
        "admin_logged_in", "admin_user_id", "admin_name",
        "student_logged_in", "student_user_id", "student_name",
        "teacher_logged_in", "teacher_user_id", "teacher_name",
    ):
        session.pop(key, None)
    prefix = "teacher" if role == "teacher" else role
    session[f"{prefix}_logged_in"] = True
    session[f"{prefix}_user_id"] = user[0]
    session[f"{prefix}_name"] = user[1]


def _register(role):
    data = _registration_data()
    account_type = "Student" if role == "Student" else "Lecturer"
    action = (
        url_for("auth.student_signup")
        if role == "Student"
        else url_for("auth.lecturer_signup")
    )
    required = ("full_name", "email", "password")
    if role == "Student":
        required += ("institution_id",)
    if any(not data[field] for field in required):
        error = "All registration fields are required."
        return render_template(
            "signup.html",
            account_type=account_type,
            action=action,
            error=error,
            form_data=data,
        ), 400
    if data["password"] != data["confirm_password"]:
        error = "Passwords do not match."
        return render_template(
            "signup.html",
            account_type=account_type,
            action=action,
            error=error,
            form_data=data,
        ), 400
    if len(data["password"]) < 8:
        error = "Password must be at least 8 characters."
        return render_template(
            "signup.html",
            account_type=account_type,
            action=action,
            error=error,
            form_data=data,
        ), 400
    required_domain = (
        STUDENT_EMAIL_DOMAIN if role == "Student" else LECTURER_EMAIL_DOMAIN
    )
    if not data["email"].endswith(required_domain):
        error = f"Use an institution email ending in {required_domain}."
        return render_template(
            "signup.html",
            account_type=account_type,
            action=action,
            error=error,
            form_data=data,
        ), 400

    with database_cursor(commit=True) as (_, cursor):
        cursor.execute(
            """
            SELECT user_id FROM Users
            WHERE username = %s OR institution_id = %s OR email = %s
            """,
            (data["email"], data["institution_id"], data["email"]),
        )
        if cursor.fetchone() is not None:
            error = "Username, institution ID, or email is already registered."
            return render_template(
                "signup.html",
                account_type=account_type,
                action=action,
                error=error,
                form_data=data,
            ), 409
        cursor.execute(
            """
            INSERT INTO Users
            (full_name, institution_id, email, username, password, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                data["full_name"],
                data["institution_id"],
                data["email"],
                data["email"],
                generate_password_hash(data["password"]),
                role,
            ),
        )
    return redirect(url_for("auth.student_login" if role == "Student" else "auth.lecturer_login"))


@auth_bp.route("/student-signup", methods=["GET", "POST"])
def student_signup():
    if request.method == "POST":
        return _register("Student")
    return render_template(
        "signup.html",
        account_type="Student",
        action=url_for("auth.student_signup"),
        form_data=_empty_registration_data(),
    )


@auth_bp.route("/lecturer-signup", methods=["GET", "POST"])
def lecturer_signup():
    if request.method == "POST":
        return _register("Teacher")
    return render_template(
        "signup.html",
        account_type="Lecturer",
        action=url_for("auth.lecturer_signup"),
        form_data=_empty_registration_data(),
    )


@auth_bp.route("/teacher-signup")
def legacy_teacher_signup():
    return redirect(url_for("auth.lecturer_signup"))


@auth_bp.route("/lecturer-login", methods=["GET", "POST"])
def lecturer_login():
    if request.method == "POST":
        identifier = _login_identifier()
        password = request.form.get("password") or ""
        teacher = _find_user(identifier, "Teacher")
        if teacher is not None and verify_password(password, teacher[3]):
            _set_authenticated_session("teacher", teacher)
            return redirect(url_for("teacher.teacher_dashboard"))
        return render_template(
            "login.html",
            login_title="Lecturer login",
            login_action=url_for("auth.lecturer_login"),
            login_description="Lecturer area",
            login_identifier_label="Institution email",
            signup_action=url_for("auth.lecturer_signup"),
            error="Invalid lecturer email or password.",
            identifier=request.form.get("identifier", ""),
        ), 401
    return render_template(
        "login.html",
        login_title="Lecturer login",
        login_action="/lecturer-login",
        login_description="Lecturer area",
        login_identifier_label="Institution email",
        signup_action="/lecturer-signup",
    )


@auth_bp.route("/teacher-login")
def legacy_teacher_login():
    return redirect(url_for("auth.lecturer_login"))


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        identifier = _login_identifier()
        password = request.form.get("password")
        user = _find_user(identifier, "Administrator")
        if user is not None and verify_password(password, user[3]):
            _set_authenticated_session("admin", user)
            return redirect(url_for("admin.admin_dashboard"))
        return render_template(
            "login.html",
            login_title="Administrator login",
            login_action=url_for("auth.admin_login"),
            login_identifier_label="Administrator email",
            login_description="Administrator area",
            error="Invalid administrator email or password.",
            identifier=request.form.get("identifier", ""),
        ), 401
    return render_template(
        "login.html",
        login_title="Administrator login",
        login_identifier_label="Administrator email",
        login_description="Administrator area",
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def legacy_admin_login():
    return redirect(url_for("auth.admin_login"))


@auth_bp.route("/student-login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        identifier = _login_identifier()
        password = request.form.get("password")
        student = _find_user(identifier, "Student", include_restricted=True)
        if student is not None and is_banned_status(student[5]):
            error = "Account banned. Contact admin."
        elif student is not None and verify_password(password, student[3]):
            _set_authenticated_session("student", student)
            return redirect(url_for("student.student_dashboard"))
        else:
            error = "Invalid student email or password."
        return render_template(
            "student_login.html",
            error=error,
            identifier=request.form.get("identifier", ""),
        ), 401
    return render_template("student_login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)
    session.pop("admin_name", None)
    return redirect(url_for("auth.admin_login"))


@auth_bp.route("/student-logout")
def student_logout():
    session.pop("student_logged_in", None)
    session.pop("student_user_id", None)
    session.pop("student_name", None)
    return redirect(url_for("auth.student_login"))


@auth_bp.route("/teacher-logout")
def teacher_logout():
    return lecturer_logout()


@auth_bp.route("/lecturer-logout")
def lecturer_logout():
    session.pop("teacher_logged_in", None)
    session.pop("teacher_user_id", None)
    session.pop("teacher_name", None)
    return redirect(url_for("auth.lecturer_login"))
