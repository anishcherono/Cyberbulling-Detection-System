import logging
from flask import Blueprint, jsonify, render_template, request

from extensions import database_cursor
from mpesa_service import (
    format_phone_number,
    initiate_stk_push,
    process_stk_callback,
)

logger = logging.getLogger(__name__)

donations_bp = Blueprint("donations", __name__)


@donations_bp.route("/donate", methods=["GET"])
def donate():
    total_raised = 0
    donor_count = 0
    recent_donations = []

    try:
        with database_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0), COUNT(*)
                FROM Donations
                WHERE status = 'COMPLETED'
                """
            )
            row = cursor.fetchone()
            if row:
                total_raised, donor_count = row

            cursor.execute(
                """
                SELECT donor_name, amount, created_at
                FROM Donations
                WHERE status = 'COMPLETED'
                ORDER BY donation_id DESC
                LIMIT 5
                """
            )
            recent_donations = cursor.fetchall()
    except Exception as exc:
        logger.warning(f"Could not load donations summary (table might be initializing): {exc}")

    return render_template(
        "donate.html",
        total_raised=total_raised,
        donor_count=donor_count,
        recent_donations=recent_donations,
    )


@donations_bp.route("/donate/initiate", methods=["POST"])
def initiate_donation():
    donor_name = request.form.get("donor_name", "").strip() or "Anonymous"
    phone_number = request.form.get("phone_number", "").strip()
    amount_raw = request.form.get("amount", "").strip()

    if not phone_number:
        return jsonify({"success": False, "error": "Phone number is required."}), 400

    try:
        amount = int(float(amount_raw))
        if amount < 1:
            return jsonify({"success": False, "error": "Amount must be at least KES 1."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Please provide a valid numeric amount."}), 400

    try:
        formatted_phone = format_phone_number(phone_number)
    except ValueError as err:
        return jsonify({"success": False, "error": str(err)}), 400

    stk_result = initiate_stk_push(
        phone_number=formatted_phone,
        amount=amount,
        account_reference="NishSystem",
        transaction_desc="Donation",
    )

    if not stk_result.get("success"):
        return jsonify({
            "success": False,
            "error": stk_result.get("error", "Failed to initiate M-Pesa prompt. Please try again."),
        }), 400

    checkout_request_id = stk_result.get("checkout_request_id")
    merchant_request_id = stk_result.get("merchant_request_id")

    try:
        with database_cursor(commit=True) as (_, cursor):
            cursor.execute(
                """
                INSERT INTO Donations (
                    donor_name, phone_number, amount,
                    merchant_request_id, checkout_request_id, status
                ) VALUES (?, ?, ?, ?, ?, 'PENDING')
                """,
                (donor_name, formatted_phone, amount, merchant_request_id, checkout_request_id),
            )
    except Exception as exc:
        logger.exception("Database error recording donation: %s", exc)
        return jsonify({"success": False, "error": "Failed to save donation record."}), 500

    return jsonify({
        "success": True,
        "checkout_request_id": checkout_request_id,
        "message": stk_result.get("customer_message"),
        "phone_number": formatted_phone,
        "amount": amount,
    })


@donations_bp.route("/donate/status/<checkout_request_id>", methods=["GET"])
def check_status(checkout_request_id):
    if not checkout_request_id:
        return jsonify({"status": "UNKNOWN", "error": "Checkout Request ID is required."}), 400

    with database_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT status, mpesa_receipt_number, result_desc, amount, donor_name
            FROM Donations
            WHERE checkout_request_id = ?
            """,
            (checkout_request_id,),
        )
        row = cursor.fetchone()

    if not row:
        return jsonify({"status": "NOT_FOUND"}), 404

    status, receipt, desc, amount, donor = row
    return jsonify({
        "status": status,
        "receipt": receipt,
        "description": desc,
        "amount": float(amount) if amount else 0,
        "donor_name": donor,
    })


@donations_bp.route("/donations/callback", methods=["POST"])
def mpesa_callback():
    data = request.get_json(silent=True) or {}
    logger.info("Received M-Pesa Callback: %s", data)

    parsed = process_stk_callback(data)
    checkout_request_id = parsed.get("checkout_request_id")
    merchant_request_id = parsed.get("merchant_request_id")
    status = parsed.get("status")
    result_code = parsed.get("result_code")
    result_desc = parsed.get("result_desc")
    receipt_number = parsed.get("receipt_number")

    if checkout_request_id or merchant_request_id:
        try:
            with database_cursor(commit=True) as (_, cursor):
                cursor.execute(
                    """
                    UPDATE Donations
                    SET status = ?,
                        result_code = ?,
                        result_desc = ?,
                        mpesa_receipt_number = COALESCE(?, mpesa_receipt_number)
                    WHERE checkout_request_id = ? OR merchant_request_id = ?
                    """,
                    (status, result_code, result_desc, receipt_number, checkout_request_id, merchant_request_id),
                )
        except Exception as exc:
            logger.exception("Failed to update donation from M-Pesa callback: %s", exc)

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})
