import unittest

from message_policy import (
    format_blocked_notification,
    get_admin_action_suggestions,
    get_admin_decision,
    get_admin_enforcement_result,
    get_delivery_decision,
    is_account_blocked,
    is_banned_status,
    requires_admin_review,
)


class MessageDeliveryPolicyTests(unittest.TestCase):
    def test_cyberbullying_message_is_blocked_from_destination(self):
        decision = get_delivery_decision("Cyberbullying", 0.91, 42)

        self.assertFalse(decision["delivery_allowed"])
        self.assertIsNone(decision["recipient_id"])
        self.assertEqual(decision["status"], "blocked_admin_review")
        self.assertIn("91.00%", decision["notification_message"])
        self.assertIn("administrator must approve and enforce", decision["notification_message"].lower())

    def test_non_cyberbullying_message_is_delivered(self):
        decision = get_delivery_decision("Not Cyberbullying", 0.20, 42)

        self.assertTrue(decision["delivery_allowed"])
        self.assertEqual(decision["recipient_id"], 42)
        self.assertEqual(decision["status"], "checked")

    def test_blocked_notification_includes_the_original_message(self):
        notification = format_blocked_notification(
            "This message was detected as cyberbullying by AI.",
            "Please stop this behaviour.",
        )

        self.assertIn("This message was detected as cyberbullying by AI.", notification)
        self.assertIn("Blocked message: Please stop this behaviour.", notification)

    def test_banned_status_is_normalized_for_login_and_listing(self):
        self.assertTrue(is_banned_status("Banned"))
        self.assertTrue(is_banned_status(" banned "))
        self.assertFalse(is_banned_status("active"))

    def test_temporarily_restricted_status_is_blocked(self):
        self.assertTrue(is_account_blocked("TEMPORARILY_RESTRICTED"))
        self.assertTrue(is_account_blocked(" banned "))
        self.assertFalse(is_account_blocked("active"))

    def test_admin_may_enforce_a_decision(self):
        decision = get_admin_decision("Cyberbullying", 0.97)

        self.assertFalse(decision["auto_ban"])
        self.assertEqual(decision["action"], "admin_review_required")
        self.assertIn("administration", decision["notification_message"].lower())
        self.assertIn("disciplinary", decision["notification_message"].lower())

    def test_ai_review_is_required_for_cyberbullying_only(self):
        self.assertTrue(requires_admin_review("Cyberbullying", 0.91))
        self.assertFalse(requires_admin_review("Not Cyberbullying", 0.20))

    def test_extremity_suggestions_are_admin_approval_guidance_only(self):
        low = get_admin_action_suggestions(0.60)
        medium = get_admin_action_suggestions(0.80)
        high = get_admin_action_suggestions(0.93)

        self.assertEqual(low["recommended_action"], "review_and_warn")
        self.assertEqual(medium["recommended_action"], "temporary_restriction")
        self.assertEqual(high["recommended_action"], "account_ban")
        self.assertTrue(low["requires_admin_approval"])
        self.assertFalse(high["auto_enforce"])

    def test_four_admin_actions_are_enforced_and_notified(self):
        actions = [
            "notify_only",
            "warning",
            "temporary_restriction",
            "account_ban",
        ]

        for action in actions:
            result = get_admin_enforcement_result(action, 0.93)
            self.assertTrue(result["requires_admin_approval"])
            self.assertTrue(result["notification_message"])
            self.assertTrue(result["status_update"])


if __name__ == "__main__":
    unittest.main()
