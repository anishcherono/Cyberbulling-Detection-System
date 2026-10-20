CYBERBULLY_RESULT_PREFIX = "Cyberbullying"


def is_banned_status(status):
    """Return whether a database status represents a banned account."""
    return str(status or "").strip().lower() == "banned"


def is_account_blocked(status):
    """Return whether an account status prevents authenticated access."""
    normalized_status = str(status or "").strip().lower()
    return normalized_status in {"banned", "temporarily_restricted"}


def format_blocked_notification(notification_message, blocked_message):
    """Return the complete message shown to a sender after an AI block."""
    return f"{notification_message} Blocked message: {blocked_message}"


def get_delivery_decision(detection_result, confidence, destination_user_id):
    """Block cyberbullying messages using the AI verdict and confidence."""
    is_cyberbullying = str(detection_result).startswith(CYBERBULLY_RESULT_PREFIX)

    if is_cyberbullying:
        confidence_percentage = float(confidence) * 100
        return {
            "delivery_allowed": False,
            "recipient_id": None,
            "status": "blocked_admin_review",
            "notification_message": (
                f"This message was detected as cyberbullying by AI at "
                f"{confidence_percentage:.2f}%. It was blocked and was not delivered. "
                "No disciplinary action has been applied yet. An administrator "
                "must approve and enforce any action."
            ),
        }

    return {
        "delivery_allowed": True,
        "recipient_id": destination_user_id,
        "status": "checked",
        "notification_message": None,
    }


def requires_admin_review(detection_result, confidence):
    """Return whether the AI result requires administrator review."""
    return str(detection_result).startswith(CYBERBULLY_RESULT_PREFIX)


def get_admin_action_suggestions(confidence):
    """Return severity guidance only; administrators must approve all actions."""
    confidence_value = max(0.0, min(1.0, float(confidence)))
    if confidence_value < 0.60:
        recommended_action = "review_and_warn"
        action_description = "Review the content and notify the sender without a punitive action."
    elif confidence_value < 0.80:
        recommended_action = "review_and_warn"
        action_description = "Review the content and issue a formal warning after administrator approval."
    elif confidence_value < 0.90:
        recommended_action = "temporary_restriction"
        action_description = "Consider a temporary account restriction after administrator approval."
    else:
        recommended_action = "account_ban"
        action_description = "Consider an account ban after administrator approval and documented review."

    return {
        "recommended_action": recommended_action,
        "action_description": action_description,
        "requires_admin_approval": True,
        "auto_enforce": False,
    }


def get_admin_enforcement_result(action, confidence):
    """Return an explicit, admin-approved outcome and student notification."""
    action_messages = {
        "notify_only": (
            "Administration reviewed the flagged message. No disciplinary action "
            "has been applied."
        ),
        "warning": (
            "Administration has approved a formal warning for this cyberbullying "
            "incident. Your account remains active."
        ),
        "temporary_restriction": (
            "Administration has approved a temporary account restriction for this "
            "cyberbullying incident. The restriction expires on the date shown by "
            "administration."
        ),
        "account_ban": (
            "Administration has approved and enforced an account ban because of "
            "this cyberbullying incident."
        ),
    }
    status_update = {
        "notify_only": "reviewed",
        "warning": "warning_issued",
        "temporary_restriction": "restricted",
        "account_ban": "banned",
    }
    return {
        "action": action,
        "requires_admin_approval": True,
        "auto_enforce": False,
        "notification_message": action_messages[action],
        "status_update": status_update[action],
        "confidence": max(0.0, min(1.0, float(confidence))),
    }


def get_admin_decision(detection_result, confidence):
    """Return administrator review data without auto-enforcing a ban."""
    return {
        "action": "admin_review_required",
        "auto_ban": False,
        "notification_message": (
            "AI detected possible cyberbullying at "
            f"{float(confidence) * 100:.2f}%. Administration must approve and "
            "enforce the appropriate disciplinary action."
        ),
        "is_cyberbullying": requires_admin_review(detection_result, confidence),
    }
