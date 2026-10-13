import unittest
from unittest.mock import MagicMock, patch

from mpesa_service import (
    format_phone_number,
    generate_password,
    get_mpesa_config,
    initiate_stk_push,
    process_stk_callback,
)


class TestMpesaService(unittest.TestCase):
    def test_format_phone_number(self):
        self.assertEqual(format_phone_number("0712345678"), "254712345678")
        self.assertEqual(format_phone_number("+254712345678"), "254712345678")
        self.assertEqual(format_phone_number("254712345678"), "254712345678")
        self.assertEqual(format_phone_number("0112345678"), "254112345678")
        self.assertEqual(format_phone_number("712345678"), "254712345678")

    def test_format_phone_number_invalid(self):
        with self.assertRaises(ValueError):
            format_phone_number("12345")
        with self.assertRaises(ValueError):
            format_phone_number("0512345678")  # Invalid prefix
        with self.assertRaises(ValueError):
            format_phone_number("")

    def test_generate_password(self):
        shortcode = "174379"
        passkey = "test_passkey"
        timestamp = "20261013120000"
        password = generate_password(shortcode, passkey, timestamp)
        self.assertTrue(isinstance(password, str))
        self.assertGreater(len(password), 10)

    def test_initiate_stk_push_mock_fallback(self):
        with patch.dict("os.environ", {"MPESA_MOCK_FALLBACK": "true", "MPESA_CONSUMER_KEY": ""}):
            result = initiate_stk_push("0712345678", 100)
            self.assertTrue(result["success"])
            self.assertTrue(result["is_mock"])
            self.assertEqual(result["amount"], 100)
            self.assertEqual(result["phone_number"], "254712345678")
            self.assertTrue("checkout_request_id" in result)

    def test_process_stk_callback_success(self):
        sample_callback = {
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
                            {"Name": "Balance"},
                            {"Name": "TransactionDate", "Value": 20191219102115},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        res = process_stk_callback(sample_callback)
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["result_code"], 0)
        self.assertEqual(res["receipt_number"], "NLJ7RT61SV")
        self.assertEqual(res["amount"], 100.00)

    def test_process_stk_callback_cancelled(self):
        sample_callback = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "29115-34620561-1",
                    "CheckoutRequestID": "ws_CO_191220191020363925",
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user",
                }
            }
        }
        res = process_stk_callback(sample_callback)
        self.assertEqual(res["status"], "CANCELLED")
        self.assertEqual(res["result_code"], 1032)


if __name__ == "__main__":
    unittest.main()
