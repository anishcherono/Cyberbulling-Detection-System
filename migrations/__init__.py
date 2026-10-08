from extensions import close_database, get_connection
from migrations.versions import (
    v0001_initial_schema,
    v0002_messaging_and_report_targets,
    v0003_admin_decisions,
)

MIGRATIONS = (
    (1, "Create initial application schema", v0001_initial_schema.upgrade),
    (2, "Add messaging and report targets", v0002_messaging_and_report_targets.upgrade),
    (3, "Add administrator account decisions", v0003_admin_decisions.upgrade),
)
MIGRATION_LOCK_NAME = "cyberbullying_schema_migrations"


def run_migrations():
    connection = get_connection()
    cursor = connection.cursor()
    lock_acquired = False
    try:
        cursor.execute("SELECT GET_LOCK(%s, 30)", (MIGRATION_LOCK_NAME,))
        lock_result = cursor.fetchone()
        if not lock_result or lock_result[0] != 1:
            raise RuntimeError("Could not acquire the database migration lock.")
        lock_acquired = True

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_version INT PRIMARY KEY,
                description VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()

        cursor.execute("SELECT migration_version FROM schema_migrations")
        applied_versions = {row[0] for row in cursor.fetchall()}

        for version, description, upgrade in MIGRATIONS:
            if version in applied_versions:
                continue
            upgrade()
            cursor.execute(
                """
                INSERT INTO schema_migrations (migration_version, description)
                VALUES (%s, %s)
                """,
                (version, description),
            )
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            if lock_acquired:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (MIGRATION_LOCK_NAME,))
                cursor.fetchone()
        finally:
            close_database(connection, cursor)
