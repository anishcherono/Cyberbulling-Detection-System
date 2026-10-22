import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from extensions import configure_app
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.student import student_bp
from routes.teacher import teacher_bp


class TestPrintableReports(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.secret_key = "test_secret_key"
        self.app.register_blueprint(admin_bp)
        self.app.register_blueprint(auth_bp)
        self.app.register_blueprint(student_bp)
        self.app.register_blueprint(teacher_bp)
        self.client = self.app.test_client()

    @patch("routes.admin.database_cursor")
    def test_admin_printable_report(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (
                1,
                10,
                "Threatening test message",
                "Jane Doe",
                "Harassment reason",
                None,
                "Warning issued",
                "Resolved",
                "John Doe",
                "Jane Doe",
                "Cyberbullying",
                0.95,
                "flagged",
            )
        ]
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        with self.client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_name"] = "Chief Admin"

        response = self.client.get("/admin/report/print")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Nish Institution", response.data)
        self.assertIn(b"OFFICIAL CYBERBULLYING INCIDENT", response.data)
        self.assertIn(b"Jane Doe", response.data)
        self.assertIn(b"Threatening test message", response.data)
        self.assertIn(b"window.print()", response.data)

    @patch("routes.student.database_cursor")
    def test_student_printable_report(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ("active",),  # account status check in _student_required
            ("Student Alice", "NISH-STU-001", "alice@nish.ac.ke"),  # user info
        ]
        mock_cursor.fetchall.return_value = [
            (
                101,
                None,
                "Student Alice",
                "Student Bob",
                "Hello Bob, are you going to class?",
                "Not Cyberbullying",
                0.02,
                "checked",
                None,
                None,
                None,
            )
        ]
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        with self.client.session_transaction() as sess:
            sess["student_logged_in"] = True
            sess["student_user_id"] = 5
            sess["student_name"] = "Student Alice"

        response = self.client.get("/student/report/print")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OFFICIAL STUDENT DIGITAL COMMUNICATION", response.data)
        self.assertIn(b"Student Alice", response.data)
        self.assertIn(b"NISH-STU-001", response.data)
        self.assertIn(b"window.print()", response.data)

    @patch("routes.teacher.database_cursor")
    def test_teacher_printable_report(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ("active",),  # account status check in _teacher_required
            ("Dr. Smith", "FACULTY-007", "smith@nish.ac.ke"),  # user info
        ]
        mock_cursor.fetchall.side_effect = [
            [(1, "Exam Notice", "Please prepare for the exam", "Not Cyberbullying", 0.01, None, "published")],
            [(2, None, "Student Charlie", "Thank you Professor!", "checked")],
        ]
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        with self.client.session_transaction() as sess:
            sess["teacher_logged_in"] = True
            sess["teacher_user_id"] = 2
            sess["teacher_name"] = "Dr. Smith"

        response = self.client.get("/teacher/report/print")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OFFICIAL COURSE DISCUSSION", response.data)
        self.assertIn(b"Dr. Smith", response.data)
        self.assertIn(b"Exam Notice", response.data)
        self.assertIn(b"window.print()", response.data)

    @patch("routes.admin.database_cursor")
    def test_admin_print_students(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (
                10,
                "Alice Johnson",
                "NISH-STU-001",
                "alice@nish.ac.ke",
                "active",
                None,
            ),
            (
                11,
                "Bob Smith",
                "NISH-STU-002",
                "bob@nish.ac.ke",
                "temporarily_restricted",
                None,
            ),
        ]
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        with self.client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_name"] = "Registrar Officer"

        response = self.client.get("/admin/students/print")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OFFICIAL ENROLLED STUDENTS DIRECTORY", response.data)
        self.assertIn(b"Alice Johnson", response.data)
        self.assertIn(b"NISH-STU-001", response.data)
        self.assertIn(b"Bob Smith", response.data)
        self.assertIn(b"Restricted", response.data)
        self.assertIn(b"window.print()", response.data)

    @patch("routes.admin.database_cursor")
    def test_admin_print_lecturers(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (
                20,
                "Dr. Kelvin Thorne",
                "FAC-001",
                "thorne@nish.ac.ke",
                "lecturer",
                "active",
                None,
            )
        ]
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        with self.client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_name"] = "Faculty Admin"

        response = self.client.get("/admin/lecturers/print")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OFFICIAL FACULTY &amp; LECTURERS DIRECTORY", response.data)
        self.assertIn(b"Dr. Kelvin Thorne", response.data)
        self.assertIn(b"FAC-001", response.data)
        self.assertIn(b"window.print()", response.data)

    @patch("routes.admin.database_cursor")
    def test_admin_print_cyberbullying_messages(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (
                105,
                "You are an idiot and should leave.",
                "Student Bully",
                "STU-666",
                "Victim Student",
                "Cyberbullying",
                0.965,
                "flagged",
                None,
            )
        ]
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        with self.client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_name"] = "Safety Officer"

        response = self.client.get("/admin/cyberbullying-messages/print")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OFFICIAL AI CYBERBULLYING DETECTION &amp; FLAGGED MESSAGES LOG", response.data)
        self.assertIn(b"Student Bully", response.data)
        self.assertIn(b"You are an idiot and should leave.", response.data)
        self.assertIn(b"CYBERBULLYING", response.data)
        self.assertIn(b"window.print()", response.data)

    @patch("routes.admin.database_cursor")
    def test_admin_print_all_users(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("System Admin", None, "admin@nish.edu", "Administrator", "active", None),
            ("Dr. Kelvin Thorne", "FAC-001", "thorne@lecturers.nish.edu", "Teacher", "active", None),
            ("Jane Wanjiku", "STU-2026-0001", "jane@students.nish.edu", "Student", "banned", None),
        ]
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        with self.client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_name"] = "Registrar"

        response = self.client.get("/admin/users/print")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OFFICIAL REGISTERED USERS DIRECTORY", response.data)
        self.assertIn(b"Jane Wanjiku", response.data)
        self.assertIn(b"Dr. Kelvin Thorne", response.data)
        self.assertIn(b"Lecturer", response.data)
        self.assertIn(b"Banned", response.data)
        self.assertIn(b"window.print()", response.data)

    def test_admin_print_unauthorized_redirect(self):
        for endpoint in [
            "/admin/users/print",
            "/admin/students/print",
            "/admin/lecturers/print",
            "/admin/cyberbullying-messages/print",
        ]:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 302)


if __name__ == "__main__":
    unittest.main()

