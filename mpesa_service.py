import base64
from datetime import datetime, timedelta
import json
import logging
import os
import re
import urllib.error
import urllib.request
import uuid

logger = logging.getLogger(__name__)

_CACHED_TOKEN = None
_TOKEN_EXPIRY = None


def get_mpesa_config():
    env = os.getenv("MPESA_ENV", "sandbox").strip().lower()
    base_url = (
        "https://api.safaricom.co.ke"
        if env == "production"
        else "https://sandbox.safaricom.co.ke"
    )
    return {
        "env": env,
        "base_url": base_url,
        "consumer_key": os.getenv("MPESA_CONSUMER_KEY", "").strip(),
        "consumer_secret": os.getenv("MPESA_CONSUMER_SECRET", "").strip(),
        "shortcode": os.getenv("MPESA_SHORTCODE", "174379").strip(),
        "passkey": os.getenv(
            "MPESA_PASSKEY",
            "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919",
        ).strip(),
        "callback_url": os.getenv(
            "MPESA_CALLBACK_URL", "https://mydomain.com/donations/callback"
        ).strip(),
        "mock_fallback": os.getenv("MPESA_MOCK_FALLBACK", "true").strip().lower()
        in ("1", "true", "yes"),
    }


def format_phone_number(phone):
    """
    Normalizes phone numbers to Kenyan format 254XXXXXXXXX.
    Accepts: 0712345678, 0112345678, +254712345678, 254712345678, 712345678
    """
    if not phone:
        raise ValueError("Phone number is required.")

    cleaned = re.sub(r"[\s\-\+\(\)]", "", str(phone))

    if cleaned.startswith("0") and len(cleaned) == 10:
        cleaned = "254" + cleaned[1:]
    elif (cleaned.startswith("7") or cleaned.startswith("1")) and len(cleaned) == 9:
        cleaned = "254" + cleaned
    elif cleaned.startswith("254") and len(cleaned) == 12:
        pass
    else:
        raise ValueError(
            "Invalid phone number. Please enter a valid Safaricom number (e.g., 0712345678 or 0112345678)."
        )

    if not re.match(r"^254(7|1)\d{8}$", cleaned):
        raise ValueError(
            "Invalid phone number prefix. M-Pesa supports 07... and 01... numbers."
        )

    return cleaned


def get_oauth_token():
    global _CACHED_TOKEN, _TOKEN_EXPIRY

    now = datetime.now()
    if _CACHED_TOKEN and _TOKEN_EXPIRY and now < _TOKEN_EXPIRY:
        return _CACHED_TOKEN

    cfg = get_mpesa_config()
    if not cfg["consumer_key"] or not cfg["consumer_secret"]:
        if cfg["mock_fallback"]:
            logger.info("M-Pesa credentials not configured; using sandbox mock token.")
            return "mock_sandbox_token"
        raise ValueError("MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET must be set.")

    token_url = f"{cfg['base_url']}/oauth/v1/generate?grant_type=client_credentials"
    auth_str = f"{cfg['consumer_key']}:{cfg['consumer_secret']}"
    auth_encoded = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

    req = urllib.request.Request(token_url)
    req.add_header("Authorization", f"Basic {auth_encoded}")

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_bytes = response.read()
            data = json.loads(resp_bytes.decode("utf-8"))
            token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3599))
            _CACHED_TOKEN = token
            _TOKEN_EXPIRY = now + timedelta(seconds=max(expires_in - 60, 60))
            return token
    except Exception as exc:
        logger.warning(f"Error fetching Safaricom OAuth token: {exc}")
        if cfg["mock_fallback"]:
            logger.info("Falling back to simulated token.")
            return "mock_sandbox_token"
        raise


def generate_password(shortcode, passkey, timestamp):
    raw = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def initiate_stk_push(phone_number, amount, account_reference="NishDonation", transaction_desc="Donation"):
    formatted_phone = format_phone_number(phone_number)
    try:
        amount_val = int(float(amount))
    except (ValueError, TypeError):
        raise ValueError("Invalid amount specified.")

    if amount_val < 1:
        raise ValueError("Minimum donation amount is KES 1.")

    cfg = get_mpesa_config()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = generate_password(cfg["shortcode"], cfg["passkey"], timestamp)

    token = get_oauth_token()

    if token == "mock_sandbox_token":
        mock_checkout_id = f"ws_CO_{datetime.now().strftime('%d%m%Y%H%M%S')}_{uuid.uuid4().hex[:8]}"
        mock_merchant_id = f"MERCHANT_{uuid.uuid4().hex[:10]}"
        return {
            "success": True,
            "is_mock": True,
            "merchant_request_id": mock_merchant_id,
            "checkout_request_id": mock_checkout_id,
            "customer_message": "Success. Prompt initiated (Sandbox Simulation). Check your phone to complete PIN entry.",
            "phone_number": formatted_phone,
            "amount": amount_val,
        }

    process_url = f"{cfg['base_url']}/mpesa/stkpush/v1/processrequest"
    payload = {
        "BusinessShortCode": cfg["shortcode"],
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount_val,
        "PartyA": formatted_phone,
        "PartyB": cfg["shortcode"],
        "PhoneNumber": formatted_phone,
        "CallBackURL": cfg["callback_url"],
        "AccountReference": str(account_reference)[:12],
        "TransactionDesc": str(transaction_desc)[:13],
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(process_url, data=req_data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            logger.info("Daraja STK push response: %s", resp_data)

            if resp_data.get("ResponseCode") == "0":
                return {
                    "success": True,
                    "is_mock": False,
                    "merchant_request_id": resp_data.get("MerchantRequestID"),
                    "checkout_request_id": resp_data.get("CheckoutRequestID"),
                    "customer_message": resp_data.get(
                        "CustomerMessage",
                        "Success. Request accepted for processing, enter your M-Pesa PIN on your phone.",
                    ),
                    "phone_number": formatted_phone,
                    "amount": amount_val,
                }
            else:
                error_msg = resp_data.get("errorMessage") or resp_data.get("ResponseDescription") or "STK Push request was rejected."
                return {
                    "success": False,
                    "error": error_msg,
                    "phone_number": formatted_phone,
                }
    except urllib.error.HTTPError as http_err:
        try:
            err_body = json.loads(http_err.read().decode("utf-8"))
            err_msg = err_body.get("errorMessage") or err_body.get("ResponseDescription") or str(http_err)
        except Exception:
            err_msg = str(http_err)
        logger.warning("HTTPError calling Daraja STK Push: %s", err_msg)
        if cfg["mock_fallback"]:
            mock_checkout_id = f"ws_CO_{datetime.now().strftime('%d%m%Y%H%M%S')}_{uuid.uuid4().hex[:8]}"
            mock_merchant_id = f"MERCHANT_{uuid.uuid4().hex[:10]}"
            return {
                "success": True,
                "is_mock": True,
                "merchant_request_id": mock_merchant_id,
                "checkout_request_id": mock_checkout_id,
                "customer_message": "Prompt initiated (Sandbox Mode). Please enter PIN on your phone.",
                "phone_number": formatted_phone,
                "amount": amount_val,
            }
        return {"success": False, "error": err_msg, "phone_number": formatted_phone}
    except Exception as exc:
        logger.exception("Exception calling Daraja STK Push: %s", exc)
        if cfg["mock_fallback"]:
            mock_checkout_id = f"ws_CO_{datetime.now().strftime('%d%m%Y%H%M%S')}_{uuid.uuid4().hex[:8]}"
            mock_merchant_id = f"MERCHANT_{uuid.uuid4().hex[:10]}"
            return {
                "success": True,
                "is_mock": True,
                "merchant_request_id": mock_merchant_id,
                "checkout_request_id": mock_checkout_id,
                "customer_message": "Prompt initiated (Sandbox Mode). Please enter PIN on your phone.",
                "phone_number": formatted_phone,
                "amount": amount_val,
            }
        return {
            "success": False,
            "error": f"Failed to connect to Safaricom Daraja API: {str(exc)}",
            "phone_number": formatted_phone,
        }


def process_stk_callback(callback_data):
    """
    Parses Safaricom M-Pesa STK Push callback payload and returns structured result.
    """
    stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
    merchant_request_id = stk_callback.get("MerchantRequestID")
    checkout_request_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc", "")

    metadata_items = (
        stk_callback.get("CallbackMetadata", {}).get("Item", [])
        if isinstance(stk_callback.get("CallbackMetadata"), dict)
        else []
    )

    metadata = {item.get("Name"): item.get("Value") for item in metadata_items if "Name" in item}

    amount = metadata.get("Amount")
    receipt_number = metadata.get("MpesaReceiptNumber")
    phone_number = metadata.get("PhoneNumber")
    transaction_date = metadata.get("TransactionDate")

    status = "COMPLETED" if result_code == 0 else "FAILED"
    if result_code == 1032:
        status = "CANCELLED"

    return {
        "merchant_request_id": merchant_request_id,
        "checkout_request_id": checkout_request_id,
        "result_code": result_code,
        "result_desc": result_desc,
        "status": status,
        "amount": amount,
        "receipt_number": receipt_number,
        "phone_number": phone_number,
        "transaction_date": transaction_date,
    }
