import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from extensions import configure_app
from routes.donations import donations_bp


class TestDonationsBlueprint(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        configure_app(self.app)
        self.app.register_blueprint(donations_bp)
        self.client = self.app.test_client()

    @patch("routes.donations.database_cursor")
    def test_donate_page_renders(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5000, 12)
        mock_cursor.fetchall.return_value = [("Alice", 500, None)]
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        response = self.client.get("/donate")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Donate via M-Pesa", response.data)
        self.assertIn(b"Select Amount (KES)", response.data)
        self.assertIn(b"50", response.data)
        self.assertIn(b"100", response.data)
        self.assertIn(b"500", response.data)

    @patch("routes.donations.database_cursor")
    @patch("routes.donations.initiate_stk_push")
    def test_initiate_donation_success(self, mock_initiate, mock_db):
        mock_initiate.return_value = {
            "success": True,
            "checkout_request_id": "ws_CO_12345",
            "merchant_request_id": "M_12345",
            "customer_message": "Prompt sent",
            "phone_number": "254712345678",
            "amount": 100,
            "is_mock": True,
        }
        mock_cursor = MagicMock()
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        csrf_val = "test-csrf-token-12345"
        self.client.set_cookie("csrf_token", csrf_val)
        csrf_token = csrf_val

        response = self.client.post(
            "/donate/initiate",
            data={
                "phone_number": "0712345678",
                "amount": "100",
                "donor_name": "Test Donor",
                "csrf_token": csrf_token or "",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["checkout_request_id"], "ws_CO_12345")
        self.assertEqual(data["phone_number"], "254712345678")

    @patch("routes.donations.database_cursor")
    def test_check_status_endpoint(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("COMPLETED", "NLJ7RT61SV", "Success", 100.0, "Test Donor")
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        response = self.client.get("/donate/status/ws_CO_12345")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["receipt"], "NLJ7RT61SV")

    @patch("routes.donations.database_cursor")
    def test_callback_bypasses_csrf_and_accepts(self, mock_db):
        mock_cursor = MagicMock()
        mock_db.return_value.__enter__.return_value = (None, mock_cursor)

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "29115-34620561-1",
                    "CheckoutRequestID": "ws_CO_191220191020363925",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 100.00},
                            {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }

        # Notice: no CSRF token provided in this POST, as Safaricom does not send one
        response = self.client.post("/donations/callback", json=callback_payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("ResultCode"), 0)
        self.assertEqual(data.get("ResultDesc"), "Accepted")


if __name__ == "__main__":
    unittest.main()
