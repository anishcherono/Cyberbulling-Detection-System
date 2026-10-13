import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from decision_templates import (
    build_formal_decision_notice,
    notice_from_notification_row,
)


class TestFormalDecisions(unittest.TestCase):
    def test_build_formal_decision_warning(self):
        notice = build_formal_decision_notice(
            student_name="John Doe",
            institution_id="NISH-STU-001",
            student_email="john@nish.ac.ke",
            action="warning",
            message_excerpt="You are so stupid",
            confidence=0.88,
            incident_date=datetime(2026, 10, 13, 14, 30),
            alert_id=42,
        )

        self.assertEqual(notice["action"], "warning")
        self.assertEqual(notice["student_name"], "John Doe")
        self.assertEqual(notice["institution_id"], "NISH-STU-001")
        self.assertEqual(notice["student_email"], "john@nish.ac.ke")
        self.assertIn("NISH/DISC/2026/AL-0042", notice["case_ref"])
        self.assertIn("FORMAL DISCIPLINARY WARNING", notice["title"])
        self.assertIn("Section 4.2", notice["policy_clause"])
        self.assertIn("88.00%", notice["formal_text"])
        self.assertIn("--- OFFICIAL ADMINISTRATIVE DECISION ---", notice["formal_text"])
        self.assertEqual(notice["account_status"], "warning_issued")

    def test_build_formal_decision_ban(self):
        notice = build_formal_decision_notice(
            student_name="Jane Doe",
            institution_id="NISH-STU-002",
            student_email="jane@nish.ac.ke",
            action="account_ban",
            message_excerpt="I will attack you tomorrow",
            confidence=0.99,
            alert_id=50,
        )

        self.assertEqual(notice["action"], "account_ban")
        self.assertIn("EXPULSION", notice["title"])
        self.assertEqual(notice["account_status"], "banned")
        self.assertEqual(notice["severity"], "Critical")

    def test_build_formal_decision_temporary_restriction(self):
        notice = build_formal_decision_notice(
            student_name="Bob Smith",
            institution_id="NISH-STU-003",
            student_email="bob@nish.ac.ke",
            action="temporary_restriction",
            message_excerpt="Shut up ugly",
            confidence=0.85,
            alert_id=12,
        )

        self.assertEqual(notice["action"], "temporary_restriction")
        self.assertEqual(notice["account_status"], "temporarily_restricted")
        self.assertEqual(notice["severity"], "High")

    def test_notice_from_notification_row(self):
        sample_text = (
            "--- OFFICIAL ADMINISTRATIVE DECISION ---\n"
            "REF: NISH/DISC/2026/AL-0099\n"
            "ISSUED TO: Alice Wonder (ID: NISH-STU-009) | alice@nish.ac.ke\n"
            "DATE: October 13, 2026\n"
            "DECISION: FORMAL DISCIPLINARY WARNING\n"
            "POLICY: Section 4.2\n"
            "SANCTION: Warning recorded.\n\n"
            "DIRECTIVE:\nYou are officially warned.\n\n"
            "RIGHT OF APPEAL: 7 days."
        )

        reconstructed = notice_from_notification_row(
            notification_id=99,
            raw_text=sample_text,
            date_created=datetime(2026, 10, 13),
            student_name="Alice Wonder",
            institution_id="NISH-STU-009",
            email="alice@nish.ac.ke",
        )

        self.assertEqual(reconstructed["case_ref"], "NISH/DISC/2026/AL-0099")
        self.assertEqual(reconstructed["title"], "FORMAL DISCIPLINARY WARNING")
        self.assertEqual(reconstructed["student_name"], "Alice Wonder")
        self.assertEqual(reconstructed["institution_id"], "NISH-STU-009")
        self.assertEqual(reconstructed["directive"], "You are officially warned.")


if __name__ == "__main__":
    unittest.main()
