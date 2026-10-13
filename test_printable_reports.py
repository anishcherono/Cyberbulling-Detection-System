import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from extensions import configure_app
from routes.admin import admin_bp
from routes.student import student_bp
from routes.teacher import teacher_bp


class TestPrintableReports(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.secret_key = "test_secret_key"
        self.app.register_blueprint(admin_bp)
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


if __name__ == "__main__":
    unittest.main()
