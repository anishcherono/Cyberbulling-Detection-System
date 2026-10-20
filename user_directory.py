def normalize_role(role):
    """Normalize legacy role names used by the application."""
    normalized = str(role or "").strip().lower()
    if normalized == "teacher":
        return "Lecturer"
    return normalized.title()


def seed_student_ids(users):
    """Return student rows with missing institution IDs filled sequentially."""
    assigned_ids = {
        (institution_id or "").strip()
        for _, institution_id, role in users
        if normalize_role(role) == "Student" and (institution_id or "").strip()
    }
    next_id = 1
    seeded_users = []

    for user_id, institution_id, role in users:
        if normalize_role(role) != "Student":
            seeded_users.append((user_id, institution_id, role))
            continue

        existing_id = (institution_id or "").strip()
        if existing_id:
            seeded_users.append((user_id, existing_id, role))
            continue

        while True:
            generated_id = f"STU-{next_id:04d}"
            next_id += 1
            if generated_id not in assigned_ids:
                seeded_users.append((user_id, generated_id, role))
                assigned_ids.add(generated_id)
                break

    return seeded_users


def seed_student_ids_in_database(cursor):
    """Persist generated student IDs for existing student accounts."""
    cursor.execute(
        """
        SELECT user_id, institution_id, role
        FROM Users
        WHERE LOWER(role) = 'student'
        ORDER BY user_id ASC
        """
    )
    users = seed_student_ids(cursor.fetchall())
    for user_id, institution_id, _ in users:
        if institution_id is not None and institution_id.strip():
            cursor.execute(
                """
                UPDATE Users
                SET institution_id = %s
                WHERE user_id = %s AND LOWER(role) = 'student'
                  AND (institution_id IS NULL OR TRIM(institution_id) = '')
                """,
                (institution_id, user_id),
            )
