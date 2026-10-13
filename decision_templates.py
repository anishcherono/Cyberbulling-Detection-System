from datetime import datetime


DECISION_METADATA = {
    "warning": {
        "title": "FORMAL DISCIPLINARY WARNING",
        "subtitle": "Notice of Violation of Institutional Digital Communication Policy",
        "severity": "Moderate",
        "policy_clause": "Section 4.2 (Anti-Cyberbullying and Harassment Provisions)",
        "sanction_summary": "Formal warning recorded in student disciplinary profile; account remains active under observation.",
        "directive": (
            "You are hereby officially warned regarding the hostile and unacceptable nature of your digital communication. "
            "A formal notation has been entered into your institutional record. You are instructed to immediately cease and desist "
            "from sending or posting any derogatory, threatening, or harassing content. Any subsequent violation of institutional "
            "communication policies will result in immediate suspension and referral to the Disciplinary Tribunal."
        ),
        "status_update": "warning_issued",
        "account_status": "warning_issued",
    },
    "temporary_restriction": {
        "title": "NOTICE OF TEMPORARY ACCOUNT RESTRICTION",
        "subtitle": "Order of Immediate Communication Suspension Pending Conduct Review",
        "severity": "High",
        "policy_clause": "Section 4.2 & Section 5.1 (Severe Hostile Digital Conduct)",
        "sanction_summary": "Portal communication privileges suspended for 14 calendar days; mandatory counseling required.",
        "directive": (
            "Pursuant to the findings of the Digital Safety Review Board, your institutional portal account has been placed under "
            "an immediate temporary restriction for a duration of 14 calendar days. During this period, your authorization to send direct messages, "
            "author discussion posts, or submit public comments is revoked. You are required to schedule an appointment with the Office of Student "
            "Counseling & Welfare within five (5) business days before account privileges may be reviewed for reinstatement."
        ),
        "status_update": "restricted",
        "account_status": "temporarily_restricted",
    },
    "account_ban": {
        "title": "NOTICE OF ACCOUNT EXPULSION & INDEFINITE ACCESS REVOCATION",
        "subtitle": "Final Administrative Sanction for Critical Cyberbullying Breach",
        "severity": "Critical",
        "policy_clause": "Section 4.2, Section 6.0 (Zero-Tolerance Cyberbullying & Malicious Harassment)",
        "sanction_summary": "Indefinite termination of student communication portal privileges; referral to Academic Disciplinary Tribunal.",
        "directive": (
            "Following extensive review and automated verification of critical cyberbullying conduct, the Administration has enforced "
            "an indefinite expulsion of your account from the Nish Institution Digital Communication Platform. Your credentials to participate "
            "in online student interactions have been revoked. This matter has been formally submitted to the Dean of Students and the "
            "Academic Disciplinary Tribunal for comprehensive disciplinary hearing and potential academic suspension."
        ),
        "status_update": "banned",
        "account_status": "banned",
    },
    "notify_only": {
        "title": "ADMINISTRATIVE CONTENT ADVISORY",
        "subtitle": "Informational Notification of Content Moderation Review",
        "severity": "Low / Advisory",
        "policy_clause": "Section 3.1 (Digital Etiquette and Responsible Communication)",
        "sanction_summary": "Content flagged and reviewed; no punitive sanctions recorded at this time.",
        "directive": (
            "Administration has completed a review of content submitted from your account that was flagged by automated detection filters. "
            "While no formal punitive disciplinary measure has been enforced on this occasion, you are reminded that all digital communications "
            "within Nish Institution must remain respectful, collegial, and aligned with acceptable usage guidelines."
        ),
        "status_update": "reviewed",
        "account_status": "active",
    },
}


def build_formal_decision_notice(
    student_name,
    institution_id,
    student_email,
    action,
    message_excerpt,
    confidence,
    incident_date=None,
    alert_id=None,
    admin_name="Office of Student Welfare & Discipline",
):
    action_key = action.strip().lower() if action else "notify_only"
    meta = DECISION_METADATA.get(action_key, DECISION_METADATA["notify_only"])

    now = datetime.now()
    case_ref = f"NISH/DISC/{now.strftime('%Y')}/AL-{alert_id or 1001:04d}"
    inst_id = institution_id or "Not Registered"
    conf_pct = float(confidence) * 100 if confidence is not None else 0.0

    inc_date_str = (
        incident_date.strftime("%B %d, %Y at %H:%M")
        if hasattr(incident_date, "strftime")
        else str(incident_date or now.strftime("%B %d, %Y"))
    )

    formal_text = (
        f"--- OFFICIAL ADMINISTRATIVE DECISION ---\n"
        f"REF: {case_ref}\n"
        f"ISSUED TO: {student_name} (ID: {inst_id}) | {student_email}\n"
        f"DATE: {now.strftime('%B %d, %Y')}\n"
        f"DECISION: {meta['title']}\n"
        f"POLICY: {meta['policy_clause']}\n"
        f"INCIDENT: Flagged content sent on {inc_date_str} (AI Detection: {conf_pct:.2f}%)\n"
        f"SANCTION: {meta['sanction_summary']}\n\n"
        f"DIRECTIVE:\n{meta['directive']}\n\n"
        f"RIGHT OF APPEAL: You have the right to petition the Office of the Dean of Students within seven (7) academic days.\n"
        f"AUTHORITY: {admin_name}, Nish Institution."
    )

    return {
        "case_ref": case_ref,
        "action": action_key,
        "title": meta["title"],
        "subtitle": meta["subtitle"],
        "severity": meta["severity"],
        "policy_clause": meta["policy_clause"],
        "sanction_summary": meta["sanction_summary"],
        "directive": meta["directive"],
        "status_update": meta["status_update"],
        "account_status": meta["account_status"],
        "student_name": student_name,
        "institution_id": inst_id,
        "student_email": student_email,
        "message_excerpt": message_excerpt or "[Flagged communication]",
        "confidence_pct": conf_pct,
        "incident_date_str": inc_date_str,
        "decision_date_str": now.strftime("%B %d, %Y"),
        "admin_authority": admin_name,
        "formal_text": formal_text,
    }


def notice_from_notification_row(notification_id, raw_text, date_created, student_name, institution_id, email):
    """Reconstructs a formal notice dictionary from a Notification row."""
    text = str(raw_text or "")
    lines = text.splitlines()

    ref = f"NISH/DISC/NOTICE-{notification_id:04d}"
    title = "OFFICIAL DISCIPLINARY DECISION"
    subtitle = "Formal Notice of Conduct Review"
    severity = "Formal Review"
    policy = "Section 4.2 (Anti-Cyberbullying Policy)"
    sanction = "Administrative decision on record."
    directive = text
    excerpt = "[Archived incident record]"
    conf_pct = 90.0

    for line in lines:
        if line.startswith("REF:"):
            ref = line.replace("REF:", "").strip()
        elif line.startswith("DECISION:"):
            title = line.replace("DECISION:", "").strip()
        elif line.startswith("POLICY:"):
            policy = line.replace("POLICY:", "").strip()
        elif line.startswith("SANCTION:"):
            sanction = line.replace("SANCTION:", "").strip()

    # Determine severity based on title
    if "BAN" in title.upper() or "EXPULSION" in title.upper():
        severity = "Critical"
        subtitle = "Final Administrative Sanction for Critical Cyberbullying Breach"
    elif "RESTRICTION" in title.upper():
        severity = "High"
        subtitle = "Order of Immediate Communication Suspension"
    elif "WARNING" in title.upper():
        severity = "Moderate"
        subtitle = "Notice of Violation of Institutional Digital Communication Policy"

    # Extract directive block if present
    if "DIRECTIVE:" in text:
        parts = text.split("DIRECTIVE:")
        after_dir = parts[1]
        if "RIGHT OF APPEAL:" in after_dir:
            directive = after_dir.split("RIGHT OF APPEAL:")[0].strip()
        else:
            directive = after_dir.strip()

    date_str = (
        date_created.strftime("%B %d, %Y")
        if hasattr(date_created, "strftime")
        else str(date_created or "Recent")
    )

    return {
        "case_ref": ref,
        "title": title,
        "subtitle": subtitle,
        "severity": severity,
        "policy_clause": policy,
        "sanction_summary": sanction,
        "directive": directive,
        "student_name": student_name,
        "institution_id": institution_id or "Not Registered",
        "student_email": email,
        "message_excerpt": excerpt,
        "confidence_pct": conf_pct,
        "incident_date_str": date_str,
        "decision_date_str": date_str,
        "admin_authority": "Office of Student Affairs & Conduct",
        "formal_text": text,
    }
